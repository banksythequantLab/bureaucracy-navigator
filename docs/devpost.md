# Devpost submission draft — Bureaucracy Navigator

**Tagline (≤ 60 chars):** Government forms, explained like a lawyer would — in your language.

**Tracks:** Best Apps & Agents · Best Use of Tavily

## Inspiration
Every immigration lawyer has watched a family lose a year to a rejection that had nothing to do with eligibility: a typed name on a signature line, a $50 fee difference between paper and online, an edition date that changed last Tuesday, a check that should have been two checks. Since July 10, 2026 USCIS can *deny* an already-accepted filing for an invalid signature and keep the fee. Most of the people this hits are reading the form in their second language. We built the assistant we wish every community center had.

## What it does
Bureaucracy Navigator turns USCIS Forms I-765, N-400 and I-130 into a bilingual (EN/ES) conversation.

1. **Live rule card.** Before the first question, Tavily Extract reads the uscis.gov form page and the G-1055 fee-schedule PDF and shows today's accepted edition, the paper vs. online fee, any "new edition" alert, and the where-to-file link — each with its source and timestamp. Nothing is hardcoded; when the live lookup fails, the last verified snapshot is shown and flagged *stale*.
2. **The form explains itself.** Every field carries *why it exists* and its legal basis (INA §, 8 CFR §, Federal Register, Policy Manual) in both languages. Tap ¿Por qué? on any question.
3. **Fills the official PDF** — the real AcroForm, correct edition, checkboxes and comb boxes included. The signature field is never touched: the PDF itself says it "can not be signed electronically."
4. **Rejection Simulator.** A deterministic adjudicator runs first (missing required items, schema risks, edition drift, fee drift against the live G-1055), then NVIDIA Nemotron 3 Super on Nebius Token Factory reviews the packet for cross-field problems and adds *cited* findings. The model can add findings but can never remove or downgrade a deterministic one; any model finding without a cited authority is dropped.
5. **Predicted processing time** for the applicant's exact category, with earliest/latest decision dates from the filing date.
6. **Deadline Sentinel.** Opt in and every clock that matters is computed with its rule — EAD renewal window (180 days), EAD expiry with the 540-day auto-extension note, I-94 expiry, RFE due (87-day default), the N-400 90-day early-filing window, "outside normal processing" inquiry date, monthly Visa Bulletin check — and emailed when close. Delete anytime.

## How we built it
- **Nebius Token Factory** hosts two Nemotron tiers behind the OpenAI-compatible endpoint: `nvidia/nemotron-3-super-120b-a12b` for the adjudicator review and interview reasoning, Nemotron 3 Nano for question phrasing, free-text parsing and nudge rewriting. Structured output via JSON schema with a json_object fallback.
- **Tavily Extract** is on the critical path: uscis.gov form pages, the G-1055 PDF (yes, Extract reads the PDF cleanly), the filing-address pages, processing-time pages. Search restricted to `uscis.gov`, `ecfr.gov`, `federalregister.gov`.
- **Form schemas** (YAML, CC-BY-4.0): field → PDF widget → statute → risk rule, EN/ES, with `required_when` branching. This is the open-data contribution; it outlives the hackathon.
- **pypdf** fills the AES-encrypted official PDFs; a field inspector diffs new editions in seconds.
- FastAPI + a single-file bilingual web UI; Docker Compose with a sentinel worker.

## Challenges we ran into
- The USCIS web fee page is a JS lookup with no static amounts; the G-1055 **PDF** is the authoritative schedule, and Tavily Extract turned out to read it well enough to parse per-form rows and even the I-765 "Appendix C" fee exceptions.
- Our own first draft carried a stale "$85 biometrics fee" rule for I-765 from a cached page. The live G-1055 showed it no longer exists — replaced by a separate, non-waivable Pub. L. 119-21 fee. The product caught our mistake before a user could; that became the demo.
- PDF quirks: per-page A-Number widgets, a misnamed trip-row field, checkbox on-states that differ *within the same form* ("/APT " vs "/APT"), tooltip part numbers that disagree with the printed form.

## Accomplishments we're proud of
- All three forms fill correctly from a Spanish interview, verified page by page.
- 100% EN/ES parity for every field explanation and every finding, enforced by a test.
- A model layer that is honest by construction: cited or dropped, additive only.

## What we learned
Live grounding is not a nice-to-have for government forms — fees, editions and addresses change monthly, and the cost of being wrong is a lost fee and a lost year.

## What's next
Remaining N-400 parts (marital/children/employment/full GMC questionnaire), I-485 and I-864 (the natural companions), Haitian Creole and Chinese, a kiosk mode for libraries and legal-aid clinics, and a data feed so nonprofits can watch edition changes.

## Built with
python · fastapi · nebius-token-factory · nvidia-nemotron · tavily · pypdf · pydantic · docker

## Links
- Repo: https://github.com/banksythequantLab/bureaucracy-navigator
- Demo: (hosted URL)
- Video: (≤ 3 min)

*Not legal advice. Banksy AI LLC.*
