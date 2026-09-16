# Bureaucracy Navigator — task tracker
_Nebius x NVIDIA Global AI Hackathon · deadline Oct 30 2026 10:00 PDT · Notion: 🧭 Nebius x NVIDIA Hackathon 2026 — Bureaucracy Navigator_

## Done 2026-09-16 — Week 1 scaffold
- [x] Context7 pull: openai-python, tavily-python, pypdf
- [x] Repo D:\bureaucracy-navigator → https://github.com/banksythequantLab/bureaucracy-navigator (public, Apache-2.0; schemas CC-BY-4.0)
- [x] Nebius client (reasoning + fast tiers), Tavily RuleSnapshot (form page + G-1055 PDF), I-765 schema, FastAPI, 9 tests
- [x] Fact fix: dropped stale $85 biometrics rules; added Pub. L. 119-21 separate-payment + I-485-pending $260 risks

## Done 2026-09-16 PM — Week 2 (ahead of schedule)
- [x] Official I-765 PDF (edition 08/21/25) downloaded on Vesper (uscis.gov CDN blocks cloud egress); 180 AcroForm fields dumped → packages/forms/pdf/i-765.fields.txt
- [x] USCIS PDFs are AES-encrypted → `cryptography` added to requirements
- [x] packages/forms/maps/i_765.py — answers → 100+ PDF fields (names, addresses w/ APT/STE/FLR widgets, category comb boxes, checkboxes); signature field in NEVER_FILL
- [x] packages/forms/fill.py — fill + read_back; rendered pages 1 & 3 visually verified (text, checkboxes, edition footer)
- [x] I-765 schema v2: 35 questions across Parts 1–3 + "Before You Mail" filing section; ES labels on every field; required_when branching
- [x] packages/rules/checks.py — deterministic adjudicator: schema risks, required/required_when, edition drift, fee drift vs live G-1055
- [x] packages/agents/interview.py — deterministic order; Nemotron phrase/parse optional; session store
- [x] API: /interview/start, /{sid}, /{sid}/answer, /{sid}/check, /{sid}/fill
- [x] packages/rules/known/i-765.json — last live snapshot; served flagged `stale` when Tavily fails
- [x] E2E (offline model, live Tavily): 35 Qs in Spanish → findings deny×1 (typed signature), reject×1 (PL 119-21 fee combined), info×1 (09/15/26 edition alert) → 519 KB filled PDF
- [x] 19/19 tests

## Blockers
- [ ] NEBIUS_API_KEY not yet created → phrase/parse/explain fall back to labels (works, just not conversational)
- [ ] TAVILY_API_KEY — keyless monthly limit was hit during dev; live snapshots intermittent until a key is set
- [ ] Confirm Nemotron 3 Nano model ID in Token Factory console
- [ ] Devpost rules: one team, two entries?

## Next (Week 3)
- [ ] With keys: run the Spanish interview with Nemotron phrasing; tune prompts; cache explanations
- [ ] N-400 schema + PDF map (download PDF on Vesper, inspect, map) ; I-130 after
- [ ] Live RuleSnapshot for I-130 / N-400 (`python -m packages.rules.snapshot n-400 --save-known`)
- [ ] Next.js UI (EN/ES) over the interview API
- [ ] Re-run inspector when the 09/15/26 I-765 edition posts; diff field names
