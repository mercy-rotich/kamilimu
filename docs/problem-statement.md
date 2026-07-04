# Problem Statement — Hakikisha Shule

## Background

Kenya's capitation (per-learner government funding) is disbursed termly to
public primary and secondary schools under the Free Primary Education (FPE)
and Free Day Secondary Education (FDSE) programmes. The Auditor-General's
reports have repeatedly flagged "ghost schools" — entities that received
capitation disbursements despite not appearing in the Ministry of
Education's verified institution registry — alongside cases of under- and
over-disbursement relative to what was officially allocated. Isiolo County,
like many arid and semi-arid counties, has limited last-mile oversight:
parents, teachers, and community members have no direct, low-bandwidth way
to check whether their school's funding record is legitimate.

## The Problem

Parents, teachers, and community members in rural Kenya have no accessible
way to verify whether their school actually received its allocated
capitation funds, or whether the school is even a verified institution —
leaving fraud (ghost schools, shortfalls, unexplained excess disbursements)
undetected until an audit surfaces it, years later.

## Target User

A parent or teacher in Isiolo County with a basic feature phone — no
smartphone, no internet data — who is already comfortable with USSD menus
(used daily for M-Pesa) but has no way to read a 200-page English audit PDF
or navigate a web dashboard.

## Current Alternatives & Their Shortcomings

1. **Auditor-General reports** — published as lengthy English PDFs, often
   years after the fact, requiring a desktop browser and advanced literacy.
2. **County education office visits** — requires travel, time, and knowing
   exactly who to ask.
3. **No existing tool** lets an ordinary citizen check a specific school's
   funding status in real time, from any phone, in their own language.

## Our Approach

Hakikisha Shule ("Verify the School" in Swahili) is a USSD application —
works on any phone, no internet or smartphone required — that lets anyone
dial a short code, pick their school from a list, and instantly see: the
amount allocated vs. disbursed for the current term, whether the school is
verified in county records, and — if funds don't match or the school
doesn't exist — anonymously report the discrepancy on the spot. Reports
accumulate against a school, so repeated flags surface a
"Chini ya ukaguzi / Under review" tag on subsequent lookups, closing the
loop between citizen and oversight body.

## Impact Hypothesis

If citizens can verify capitation records in under 30 seconds from any
phone, in their own language, ghost-school and misallocation fraud becomes
visible in near real time instead of surfacing years later in an audit —
restoring a direct accountability feedback loop between rural communities
and county education officials, and making it materially harder for funds
to be siphoned through non-existent institutions.

---

*Part of the Mozilla Foundation × KamiLimu Democracy & AI Hackathon — July 4th, 2026*
