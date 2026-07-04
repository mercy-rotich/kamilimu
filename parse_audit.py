"""
Extract school capitation records from Kenya's OAG "Special Audit Report on
Capitation and Infrastructure Grants in Schools 2025" (docs/audit.pdf) using
DeepSeek, for the Hakikisha Shule USSD project.

The PDF has no text layer (it's scanned page images), so this script renders
the requested pages to images with pypdfium2 and OCRs them with pytesseract
before sending the text to DeepSeek for structured extraction.

Requires the `tesseract` binary installed system-wide (not a pip package):
  sudo apt install tesseract-ocr        # Debian/Ubuntu/Parrot
  brew install tesseract                # macOS

This report describes irregularities in aggregate/summary form (e.g. "14
schools... Kshs X... Details in Annexure 35") without naming individual
schools in the body text — school-level detail is deferred to Annexures
that aren't included in the published PDF. Because of that, --mode schools
will usually return an empty or near-empty result; --mode findings extracts
the aggregate findings themselves instead (finding, schools affected,
amount, which annexure the names were deferred to).

Usage:
  python parse_audit.py --pages 12-15                        # schools mode: OCR + DeepSeek + save + print
  python parse_audit.py --pages 12-15 --dump                 # OCR only -> ocr_output.txt, no API call
  python parse_audit.py --pages 12-15 --merge                # schools mode + merge into src/schools.json
  python parse_audit.py --pages 88 --mode findings           # findings mode -> extracted_findings.json
"""

import argparse
import json
import os
import re
import sys

import pytesseract
import pypdfium2 as pdfium
import requests
from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
PDF_PATH = os.path.join(PROJECT_ROOT, "docs", "audit.pdf")
OCR_DUMP_PATH = os.path.join(PROJECT_ROOT, "ocr_output.txt")
EXTRACTED_SCHOOLS_PATH = os.path.join(PROJECT_ROOT, "extracted_schools.json")
EXTRACTED_FINDINGS_PATH = os.path.join(PROJECT_ROOT, "extracted_findings.json")
SCHOOLS_JSON_PATH = os.path.join(PROJECT_ROOT, "src", "schools.json")

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"

SYSTEM_PROMPT_SCHOOLS = """You are a financial-audit data extraction engine. You will be given \
OCR'd text from a few pages of Kenya's Office of the Auditor-General "Special Audit \
Report on Capitation and Infrastructure Grants in Schools 2025". The OCR may contain \
minor character errors, broken table columns, and mixed prose/tabular layout.

Extract EVERY individual school mentioned in the text that has any associated \
financial detail (an allocated amount, a disbursed amount, or a verification \
finding). Do not summarize, and do not skip a school just because it only has \
partial information — include it with null for whatever fields are missing.

Return ONLY a raw JSON array (no markdown code fences, no explanation, no \
leading or trailing text) where each element has exactly this shape:

{
  "name": string,
  "county": string or null,
  "allocated_ksh": number or null,
  "disbursed_ksh": number or null,
  "verified": boolean,
  "notes": string
}

Rules:
- "verified" must be false if the text states or implies the school could not \
be found, could not be traced, could not be verified, does not exist, or is not \
registered/recognized. Otherwise true.
- "notes" is a short (under 25 words) direct paraphrase of the key finding for \
that school.
- If a numeric field (allocated_ksh / disbursed_ksh) or county is not explicitly \
stated for that school, use null. Never estimate or invent a value.
- If the text mentions no individual schools at all, return an empty array: []
"""

SYSTEM_PROMPT_FINDINGS = """You are a financial-audit findings extraction engine. You will be given \
OCR'd text from a few pages of Kenya's Office of the Auditor-General "Special Audit \
Report on Capitation and Infrastructure Grants in Schools 2025". This report mostly \
describes irregularities in aggregate/summary form (e.g. "14 schools received \
capitation totalling Kshs X... Details in Annexure 35") without naming individual \
schools in the body text — school-level detail is deferred to Annexures not \
included in this text.

Extract EVERY distinct audit finding in the text that involves one or more schools \
and a financial figure (capitation, textbooks, infrastructure grants, or similar). \
One element per distinct finding/paragraph, not one per school. Do not skip a \
finding just because it lacks some fields — use null for anything not explicitly \
stated.

Return ONLY a raw JSON array (no markdown code fences, no explanation, no \
leading or trailing text) where each element has exactly this shape:

{
  "finding": string,
  "schools_affected": number or null,
  "amount_ksh": number or null,
  "county": string or null,
  "annexure_ref": number or null,
  "verified_public": boolean
}

Rules:
- "finding" is a short (under 25 words) direct paraphrase of the irregularity described.
- "annexure_ref" is the Annexure number the underlying school-level detail is \
deferred to, if the text states one (e.g. "Annexure 35" -> 35). Otherwise null.
- "verified_public" is false if the finding explicitly defers school-level detail \
to an annexure/appendix not included in this text. It is true only if the finding \
itself is fully stated with no deferred reference.
- If a number or county is not explicitly stated, use null. Never estimate or invent a value.
- If the text contains no findings involving schools and money, return an empty array: []
"""


def parse_page_range(spec, total_pages):
    match = re.match(r"^(\d+)(?:-(\d+))?$", spec.strip())
    if not match:
        sys.exit(
            "Error: --pages must look like '12-15' or a single page like '12', "
            "got '{}'".format(spec)
        )
    start = int(match.group(1))
    end = int(match.group(2)) if match.group(2) else start
    if start < 1 or end < start:
        sys.exit("Error: invalid page range {}-{}".format(start, end))
    if end > total_pages:
        sys.exit(
            "Error: page {} is out of range — audit.pdf has {} pages total".format(
                end, total_pages
            )
        )
    return start, end


def ocr_pages(start, end):
    if not os.path.exists(PDF_PATH):
        sys.exit("Error: PDF not found at {}".format(PDF_PATH))

    pdf = pdfium.PdfDocument(PDF_PATH)

    chunks = []
    for page_num in range(start, end + 1):
        page = pdf[page_num - 1]
        bitmap = page.render(scale=2.5)
        image = bitmap.to_pil()
        text = pytesseract.image_to_string(image).strip()
        print("  OCR'd page {}: {} characters".format(page_num, len(text)))
        chunks.append("--- Page {} ---\n{}".format(page_num, text))

    return "\n\n".join(chunks)


def strip_code_fences(text):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return text.strip()


def call_deepseek(ocr_text, api_key, mode):
    system_prompt = SYSTEM_PROMPT_FINDINGS if mode == "findings" else SYSTEM_PROMPT_SCHOOLS
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": ocr_text},
        ],
        "temperature": 0,
        "stream": False,
    }
    headers = {
        "Authorization": "Bearer {}".format(api_key),
        "Content-Type": "application/json",
    }

    response = requests.post(DEEPSEEK_URL, headers=headers, json=payload, timeout=120)
    if response.status_code != 200:
        sys.exit(
            "Error: DeepSeek API returned {} — {}".format(
                response.status_code, response.text[:500]
            )
        )

    content = response.json()["choices"][0]["message"]["content"]
    cleaned = strip_code_fences(content)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        print("Error: could not parse DeepSeek's response as JSON ({})".format(e))
        print("--- raw response ---")
        print(content)
        sys.exit(1)

    if isinstance(parsed, dict):
        for key in ("schools", "findings", "results", "data"):
            if key in parsed and isinstance(parsed[key], list):
                parsed = parsed[key]
                break
        else:
            sys.exit(
                "Error: DeepSeek returned a JSON object with no recognizable "
                "list inside it:\n{}".format(json.dumps(parsed, indent=2)[:500])
            )

    if not isinstance(parsed, list):
        sys.exit("Error: expected a JSON array, got: {}".format(type(parsed)))

    return parsed


def print_table(schools):
    if not schools:
        print("No schools extracted.")
        return

    headers = ["Name", "County", "Allocated", "Disbursed", "Verified"]
    rows = []
    for s in schools:
        rows.append([
            str(s.get("name") or "—"),
            str(s.get("county") or "—"),
            "{:,}".format(s["allocated_ksh"]) if s.get("allocated_ksh") is not None else "—",
            "{:,}".format(s["disbursed_ksh"]) if s.get("disbursed_ksh") is not None else "—",
            "Yes" if s.get("verified") else "No",
        ])

    widths = [
        max(len(headers[i]), max((len(r[i]) for r in rows), default=0))
        for i in range(len(headers))
    ]

    def fmt_row(row):
        return " | ".join(cell.ljust(widths[i]) for i, cell in enumerate(row))

    print(fmt_row(headers))
    print("-+-".join("-" * w for w in widths))
    for row in rows:
        print(fmt_row(row))


def print_findings_table(findings):
    if not findings:
        print("No findings extracted.")
        return

    headers = ["Finding", "Schools", "Amount (Ksh)", "County", "Annexure", "Public"]
    rows = []
    for f in findings:
        finding_text = str(f.get("finding") or "—")
        if len(finding_text) > 60:
            finding_text = finding_text[:57] + "..."
        rows.append([
            finding_text,
            str(f["schools_affected"]) if f.get("schools_affected") is not None else "—",
            "{:,}".format(f["amount_ksh"]) if f.get("amount_ksh") is not None else "—",
            str(f.get("county") or "—"),
            str(f["annexure_ref"]) if f.get("annexure_ref") is not None else "—",
            "Yes" if f.get("verified_public") else "No",
        ])

    widths = [
        max(len(headers[i]), max((len(r[i]) for r in rows), default=0))
        for i in range(len(headers))
    ]

    def fmt_row(row):
        return " | ".join(cell.ljust(widths[i]) for i, cell in enumerate(row))

    print(fmt_row(headers))
    print("-+-".join("-" * w for w in widths))
    for row in rows:
        print(fmt_row(row))


def merge_into_schools_json(schools):
    if not os.path.exists(SCHOOLS_JSON_PATH):
        sys.exit("Error: {} not found — cannot merge".format(SCHOOLS_JSON_PATH))

    with open(SCHOOLS_JSON_PATH, encoding="utf-8") as f:
        data = json.load(f)

    existing = data["schools"]
    existing_names = {s["name"].strip().lower() for s in existing}
    next_id = max((s["id"] for s in existing), default=0) + 1

    added, skipped_dup, skipped_incomplete = [], [], []

    for s in schools:
        name = (s.get("name") or "").strip()
        if not name:
            continue
        if name.lower() in existing_names:
            skipped_dup.append(name)
            continue
        allocated = s.get("allocated_ksh")
        disbursed = s.get("disbursed_ksh")
        if allocated is None or disbursed is None:
            skipped_incomplete.append(name)
            continue

        existing.append({
            "id": next_id,
            "name": name,
            "allocated": int(allocated),
            "disbursed": int(disbursed),
            "verified": bool(s.get("verified", False)),
        })
        existing_names.add(name.lower())
        next_id += 1
        added.append(name)

    with open(SCHOOLS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print("\nMerged into {}:".format(SCHOOLS_JSON_PATH))
    print("  Added: {}".format(len(added)))
    for n in added:
        print("    + {}".format(n))
    if skipped_dup:
        print("  Skipped (already present): {}".format(len(skipped_dup)))
    if skipped_incomplete:
        print("  Skipped (missing allocated/disbursed amount): {}".format(len(skipped_incomplete)))
        for n in skipped_incomplete:
            print("    - {}".format(n))


def main():
    parser = argparse.ArgumentParser(description="Extract school funding records from audit.pdf via OCR + DeepSeek")
    parser.add_argument("--pages", required=True, help="Page range to parse, e.g. 12-15 or 12")
    parser.add_argument("--dump", action="store_true", help="OCR only, save to ocr_output.txt, skip the DeepSeek call")
    parser.add_argument("--merge", action="store_true", help="Merge extracted schools into src/schools.json (schools mode only)")
    parser.add_argument(
        "--mode", choices=["schools", "findings"], default="schools",
        help="'schools' extracts individual named schools (default). 'findings' extracts "
             "aggregate audit findings instead — use this for narrative/summary pages that "
             "don't name individual schools (e.g. page 88's ghost-school findings)."
    )
    args = parser.parse_args()

    if args.merge and args.mode == "findings":
        sys.exit("Error: --merge only applies to --mode schools (findings can't be merged into schools.json)")

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not args.dump and not api_key:
        sys.exit(
            "Error: DEEPSEEK_API_KEY environment variable is not set.\n"
            "  Linux/macOS:      export DEEPSEEK_API_KEY=your-key-here\n"
            "  Windows PowerShell: $env:DEEPSEEK_API_KEY = 'your-key-here'\n"
            "(Use --dump if you only want to test OCR without calling the API.)"
        )

    if not os.path.exists(PDF_PATH):
        sys.exit("Error: PDF not found at {}".format(PDF_PATH))

    pdf = pdfium.PdfDocument(PDF_PATH)
    total_pages = len(pdf)
    start, end = parse_page_range(args.pages, total_pages)

    print("OCR'ing pages {}-{} of {} ({} total pages)...".format(start, end, PDF_PATH, total_pages))
    ocr_text = ocr_pages(start, end)

    if len(ocr_text.strip()) < 50:
        print("Warning: almost no text was extracted from this page range. "
              "These pages may be blank, a cover/section divider, or OCR failed.")

    if args.dump:
        with open(OCR_DUMP_PATH, "w", encoding="utf-8") as f:
            f.write(ocr_text)
        print("Saved raw OCR text to {} ({} characters). No API call made.".format(
            OCR_DUMP_PATH, len(ocr_text)
        ))
        return

    print("Sending OCR text to DeepSeek ({}, mode={})...".format(DEEPSEEK_MODEL, args.mode))
    results = call_deepseek(ocr_text, api_key, args.mode)

    if args.mode == "findings":
        with open(EXTRACTED_FINDINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print("Saved {} extracted finding(s) to {}\n".format(len(results), EXTRACTED_FINDINGS_PATH))
        print_findings_table(results)
        return

    with open(EXTRACTED_SCHOOLS_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("Saved {} extracted school(s) to {}\n".format(len(results), EXTRACTED_SCHOOLS_PATH))

    print_table(results)

    if args.merge:
        merge_into_schools_json(results)


if __name__ == "__main__":
    main()
