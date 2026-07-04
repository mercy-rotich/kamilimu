"""
Hakikisha Shule — USSD school-funds (capitation) verification service.
Built for the Africa's Talking sandbox / simulator.

One POST route at /ussd. Africa's Talking sends form-encoded fields:
  sessionId, serviceCode, phoneNumber, text
`text` is the full input path so far, e.g. "" -> "1" -> "1*2" -> "1*2*1".

Responses are plain text:
  "CON ..." -> session continues (show another menu)
  "END ..." -> session ends (final screen)

Each school is classified into one of four states from its data:
  GHOST      verified == false
  MATCHED    verified == true and disbursed == allocated
  SHORTFALL  verified == true and disbursed < allocated
  EXCESS     verified == true and disbursed > allocated

The input path is replayed as a small state machine on every request
(USSD is stateless — Africa's Talking sends the whole history each time),
which is what lets "0. Back" work at any level without extra bookkeeping.
"""

import json
import os
from datetime import datetime, timezone

from flask import Flask, request, Response

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCHOOLS_PATH = os.path.join(BASE_DIR, "schools.json")
REPORTS_PATH = os.path.join(BASE_DIR, "reports.json")

with open(SCHOOLS_PATH, encoding="utf-8") as f:
    SCHOOLS = json.load(f)["schools"]

# Language codes: "1" = Kiswahili (sw), "2" = English (en)
LANG = {"1": "sw", "2": "en"}

# Status tags are shown identically regardless of chosen language — they
# read as official bilingual terminology, like the "Under review" tag.
STATUS_MATCHED = "✓ IMELINGANA (Matched)"
STATUS_SHORTFALL = "⚠ PUNGUFU (Shortfall)"
STATUS_EXCESS = "🚩 ZIADA (Excess)"
UNDER_REVIEW_LINE = "Chini ya ukaguzi / Under review"

# report_type -> counts toward the "under review" flag on a school
UNDER_REVIEW_TYPES = ("does_not_exist", "discrepancy")

# Maps (state, menu choice) -> report_type written to reports.json
REPORT_TYPE_MAP = {
    "MATCHED": {"1": "confirm_received", "2": "discrepancy"},
    "SHORTFALL": {"1": "received_less", "2": "confirm_received"},
    "EXCESS": {"1": "discrepancy", "2": "confirm_received"},
    "GHOST": {"1": "does_not_exist", "2": "record_wrong"},
}

STRINGS = {
    "sw": {
        "pick_school": "Chagua shule yako:",
        "term": "Muhula wa 1, 2026",
        "allocated": "Imetengwa",
        "disbursed": "Imetolewa",
        "status": "Hali",
        "diff": "Tofauti",
        "ghost_warning": (
            "⚠ Shule hii ilipokea fedha lakini HAIKUTHIBITISHWA "
            "na maafisa wa elimu wa kaunti"
        ),
        "opt_confirm_received": "Thibitisha shule imepokea",
        "opt_report_discrepancy": "Ripoti tofauti",
        "opt_back": "Rudi",
        "opt_report_less": "Ripoti: tulipokea pungufu zaidi",
        "opt_confirm_amount": "Thibitisha tulipokea {amt}",
        "opt_confirm_amount_excess": "Thibitisha kiasi kilichopokelewa",
        "opt_report_not_exist": "Ripoti: shule hii haipo",
        "opt_report_wrong": "Ripoti: shule ipo, rekodi si sahihi",
        "thank_you": (
            "Asante. Jibu lako limepokelewa bila kutambulisha jina lako. "
            "Maafisa wa elimu wa kaunti watapitia taarifa hii."
        ),
        "invalid": "Chaguo si sahihi. Jaribu tena.",
    },
    "en": {
        "pick_school": "Choose your school:",
        "term": "Term 1, 2026",
        "allocated": "Allocated",
        "disbursed": "Disbursed",
        "status": "Status",
        "diff": "Difference",
        "ghost_warning": (
            "⚠ This school received funds but was NOT VERIFIED "
            "by county education officials"
        ),
        "opt_confirm_received": "Confirm school received it",
        "opt_report_discrepancy": "Report a discrepancy",
        "opt_back": "Back",
        "opt_report_less": "Report: we received even less",
        "opt_confirm_amount": "Confirm we received {amt}",
        "opt_confirm_amount_excess": "Confirm amount received",
        "opt_report_not_exist": "Report: this school does not exist",
        "opt_report_wrong": "Report: school exists, record is wrong",
        "thank_you": (
            "Thank you. Your response has been recorded anonymously. "
            "County education officials will review this."
        ),
        "invalid": "Invalid choice. Please try again.",
    },
}

WELCOME_TEXT = (
    "Karibu Hakikisha Shule / Welcome\n"
    "Chagua lugha / Choose language:\n"
    "1. Kiswahili\n"
    "2. English"
)


def ksh(amount):
    """Format an integer amount as 'Ksh 1,234,567'."""
    return "Ksh {:,}".format(amount)


def variance_str(allocated, disbursed):
    """Signed variance + percentage, e.g. '-Ksh 1,112,200 (-20.0%)'."""
    variance = disbursed - allocated
    pct = (variance / allocated * 100) if allocated else 0
    sign = "+" if variance > 0 else "-"
    return "{}{} ({}{:.1f}%)".format(sign, ksh(abs(variance)), sign, abs(pct))


def con(text):
    return Response("CON " + text, mimetype="text/plain")


def end(text):
    return Response("END " + text, mimetype="text/plain")


def compute_state(school):
    if not school["verified"]:
        return "GHOST"
    if school["disbursed"] == school["allocated"]:
        return "MATCHED"
    if school["disbursed"] < school["allocated"]:
        return "SHORTFALL"
    return "EXCESS"


def load_reports():
    if not os.path.exists(REPORTS_PATH):
        return []
    with open(REPORTS_PATH, encoding="utf-8") as f:
        return json.load(f)


def append_report(school_id, report_type):
    reports = load_reports()
    reports.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "school_id": school_id,
        "report_type": report_type,
    })
    with open(REPORTS_PATH, "w", encoding="utf-8") as f:
        json.dump(reports, f, indent=2)


def is_under_review(school_id, reports):
    return any(
        r["school_id"] == school_id and r["report_type"] in UNDER_REVIEW_TYPES
        for r in reports
    )


def school_menu(lang):
    """Level 1: numbered list of schools in the chosen language."""
    t = STRINGS[lang]
    lines = [t["pick_school"]]
    for i, s in enumerate(SCHOOLS, start=1):
        lines.append("{}. {}".format(i, s["name"]))
    return "\n".join(lines)


def school_detail_screen(lang, school, reports):
    """Level 2: a school's record + state-specific options."""
    t = STRINGS[lang]
    state = compute_state(school)

    lines = [
        school["name"],
        t["term"],
        "{}: {}".format(t["allocated"], ksh(school["allocated"])),
        "{}: {}".format(t["disbursed"], ksh(school["disbursed"])),
    ]

    if state == "GHOST":
        lines.append(t["ghost_warning"])
    elif state == "SHORTFALL":
        lines.append("{}: {}".format(
            t["diff"], variance_str(school["allocated"], school["disbursed"])
        ))
        lines.append("{}: {}".format(t["status"], STATUS_SHORTFALL))
    elif state == "EXCESS":
        lines.append("{}: {}".format(
            t["diff"], variance_str(school["allocated"], school["disbursed"])
        ))
        lines.append("{}: {}".format(t["status"], STATUS_EXCESS))
    else:
        lines.append("{}: {}".format(t["status"], STATUS_MATCHED))

    if is_under_review(school["id"], reports):
        lines.append(UNDER_REVIEW_LINE)

    lines.append("")

    if state == "MATCHED":
        lines += [
            "1. {}".format(t["opt_confirm_received"]),
            "2. {}".format(t["opt_report_discrepancy"]),
            "0. {}".format(t["opt_back"]),
        ]
    elif state == "SHORTFALL":
        lines += [
            "1. {}".format(t["opt_report_less"]),
            "2. {}".format(t["opt_confirm_amount"].format(amt=ksh(school["disbursed"]))),
            "0. {}".format(t["opt_back"]),
        ]
    elif state == "EXCESS":
        lines += [
            "1. {}".format(t["opt_report_discrepancy"]),
            "2. {}".format(t["opt_confirm_amount_excess"]),
            "0. {}".format(t["opt_back"]),
        ]
    else:  # GHOST
        lines += [
            "1. {}".format(t["opt_report_not_exist"]),
            "2. {}".format(t["opt_report_wrong"]),
            "0. {}".format(t["opt_back"]),
        ]

    return "\n".join(lines)


@app.route("/ussd", methods=["POST"])
def ussd():
    text = (request.form.get("text") or "").strip()
    parts = text.split("*") if text else []

    reports = load_reports()
    level = 0       # 0=language, 1=school list, 2=school detail, 3=action taken
    lang = None
    school = None
    choice = None
    invalid = False

    for token in parts:
        if invalid:
            break

        if level == 0:
            picked = LANG.get(token)
            if picked is None:
                invalid = True
            else:
                lang = picked
                level = 1

        elif level == 1:
            if token == "0":
                level = 0
            elif token.isdigit() and 1 <= int(token) <= len(SCHOOLS):
                school = SCHOOLS[int(token) - 1]
                level = 2
            else:
                invalid = True

        elif level == 2:
            if token == "0":
                level = 1
                school = None
            elif token in ("1", "2"):
                choice = token
                level = 3
            else:
                invalid = True

        else:  # level == 3, nothing further expected
            invalid = True

    if invalid:
        t = STRINGS[lang or "en"]
        return end(t["invalid"])

    if level == 0:
        return con(WELCOME_TEXT)

    if level == 1:
        return con(school_menu(lang))

    if level == 2:
        return con(school_detail_screen(lang, school, reports))

    # level == 3: record the report/confirmation and close the session
    state = compute_state(school)
    report_type = REPORT_TYPE_MAP[state][choice]
    append_report(school["id"], report_type)
    return end(STRINGS[lang]["thank_you"])


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
