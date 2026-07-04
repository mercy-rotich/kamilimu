# Problem Statement — DIRA

## Background

Kenya's capitation (per-learner government funding — Ksh 1,420/year
primary, Ksh 22,244/year secondary) is disbursed termly to public schools
under the Free Primary Education and Free Day Secondary Education
programmes. The Auditor-General's 2025 Special Audit, covering financial
years 2020/21–2023/24, exposed the scale of leakage: Ksh 3.7 billion
disbursed to 33 non-existent "ghost schools," a Ksh 117 billion capitation
shortfall against approved allocations, ghost learners in 723 of 1,039
sampled schools, and discrepancies spanning 32 counties. The Ministry of
Education's subsequent nationwide verification (covering ~53,000
institutions and 11 million learners) named ghost schools county by
county — including Bisanavi, Eldara and Kambi Otha in Isiolo County, and
Loiwat High and Maji Mazuri Mixed in Baringo — and identified 87,000
learners with no traceable presence in any institution.

Capitation is computed from enrollment data held in closed government
systems (NEMIS, now transitioning to KEMIS). No citizen can see or
dispute the record their school's funding is based on — so falsifying a
registry entry carries near-zero detection risk. The fraud ran for four
consecutive audit years before a single special audit exposed it.

## The Problem

Boards of Management (BOMs) and parents of public schools in Kenya's
marginalized counties have no way to verify whether their school received
its allocated capitation — or whether schools receiving funds in their
community's name even exist. The one group that can physically verify a
school — its own community — has no channel into the records, leaving
ghost schools, shortfalls, and unexplained excess disbursements
undetected until an audit surfaces them, years later.

## Target User

**Primary user:** a Board of Management member of a public school —
holder of a statutory oversight mandate under the Basic Education Act,
one board per school. **Secondary beneficiaries:** parents and community
members. Our pilot user lives in Isiolo County, dials USSD menus daily
for M-Pesa on a basic feature phone, has no data bundle, and communicates
in Swahili — while the records that determine his school's funding sit in
a scanned English PDF and a login-only government portal.

## Current Alternatives & Their Shortcomings

1. **The Auditor-General's audit** — published as a 100-page *scanned*
   PDF with no searchable text. Its per-school details are deferred to
   Annexures 35–38, which are not included in the published document.
   We verified this directly: our OCR pipeline processed every page —
   the findings are aggregate only ("14 schools, Ksh 16,683,215 —
   details in Annexure 35"). Even the audit of hidden schools hides
   the schools.
2. **NEMIS/KEMIS** — internal, credential-locked systems. KEMIS
   (rolling out since January 2026) improves the government's own data
   but remains government-facing, with no citizen verification channel.
3. **Existing civic-tech** — Mzalendo (parliamentary monitoring) and
   PesaYetu (county data) are web-based and aggregate-level. No Kenyan
   civic-tech tool delivers school-level capitation verification via
   USSD/SMS to offline BOM members and parents.
4. **County education office visits** — travel, cost, and even then,
   per-school disbursement records are not public.

## Our Approach

DIRA ("vision" in Swahili) is a USSD application — any phone, no
internet — that lets a BOM member or parent dial a short code, select
their school, and instantly see: allocated vs. disbursed amounts for the
term, and the school's verification status across four states (matched,
shortfall, excess, ghost/unverified). If the record doesn't match the
ground truth, they report the discrepancy on the spot — anonymously by
design: no names or numbers stored. Reports accumulate per school;
repeated flags surface a "Chini ya ukaguzi / Under review" tag on
subsequent lookups, closing the loop between citizen and oversight. An
AI pipeline (OCR + LLM extraction) converts the government's scanned
documents into the structured per-school records the service queries —
the capability that makes citizen-facing verification feasible at the
scale of 53,000 schools. AI flags patterns; humans verify — protecting
legitimate pastoralist mobile schools from ever being auto-declared
ghosts.

## Impact Hypothesis

If a school's community can verify its capitation record in under 30
seconds, in their own language, fraud becomes visible in term time
rather than years later: communities confirm honest disbursements,
dispute false ones, and patterns of discrepancy escalate to the
Auditor-General and civil society. This operationalizes Article 35 of
the Constitution (access to information) in service of Article 43 (the
right to education) — converting 11 million learners' communities from
passive victims of registry fraud into a continuous, distributed
verification layer.

---

*Mozilla Foundation × KamiLimu — Democracy & AI Buildathon, July 4, 2026*