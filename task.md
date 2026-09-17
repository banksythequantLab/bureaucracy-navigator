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

## Done 2026-09-16 late — Week 3 (ahead of schedule)
- [x] N-400 + I-130 official PDFs downloaded on Vesper (ed. 01/20/25 and 04/01/24); AcroForm dumps + tooltips committed
- [x] packages/schemas/n-400.yaml — 40 questions: eligibility basis, identity, residence, trips, GMC core (false claim, voting, taxes, nonresident filing, Selective Service), contact, fee options; risks for 90-day early filing, 6-month/1-year trips, physical presence, reduced-fee-online, N-648
- [x] packages/forms/maps/n_400.py — Part 1/2/4/8/9/11 fields incl. A-Number on every page, trip rows (row-1 box is misnamed P9_Line1_Countries1), leading-space state quirk; 5 signature widgets in NEVER_FILL
- [x] N-400 fill verified visually (pages 1 and 6)
- [x] `int` field type (interview parser + checks)
- [x] known snapshots: n-400 (live, verified) and i-130 (fees from G-1055; edition from PDF footer, flagged unverified)
- [x] apps/web/index.html — bilingual single-file UI: live rule card w/ sources + live/stale badge, one-question interview with type-aware inputs, ¿Por qué? panel with cites, findings by severity, PDF download; Playwright-driven E2E in Spanish (3 findings)
- [x] 24/24 tests

## Done 2026-09-17 — Week 4 (ahead of schedule)
- [x] I-130 (ed. 04/01/24, 481 fields): 41-question schema written bilingual; risks for LPR-petitioning-parent/sibling (deny), petitioner under 21, adoptee petitioning birth family, concurrent I-485 lockbox + online-filing rejects, prior-marriage termination docs, relationship/status evidence
- [x] packages/forms/maps/i_130.py — Parts 1/2/4/6 incl. per-block APT on-state quirks ("/APT " vs "/APT"), P4Line5a misnomer; fill verified visually (pages 1 and 5)
- [x] Spanish sidecars packages/schemas/es/{i-765,n-400}.es.yaml — every why + every risk; loader merges at load; tests/test_spanish_coverage.py enforces 100% for all forms
- [x] Snapshot-derived findings (edition drift, fee mismatch) now bilingual
- [x] packages/agents/adjudicator.py — Nemotron review with structured output; drops uncited findings; merge() keeps deterministic severity on collision; /check?model=true; offline → no-op
- [x] UI: I-130 option, certificate input, rule-card race fix (stale response could overwrite a newer form's card)
- [x] i-130 known snapshot now live-verified (edition 04/01/24, $675/$625, addresses URL)
- [x] E2E I-130 in Spanish: 41 Qs → reject×3 (online+concurrent, wrong lockbox, $675 vs $625 online) + rfe×1
- [x] 33/33 tests

## Done 2026-09-17 — Week 5 (ahead of schedule)
- [x] packages/rules/timeline.py + known/processing_times.json — per-form/category ranges (Sep 2026 table), earliest/latest/inquiry dates from filing date; Tavily live path when key exists
- [x] packages/agents/sentinel.py — Case store, 7 deadline rules with authorities (RFE 87-day default, EAD 180-day window + 540-day auto-extension, I-94, N-400 90-day window, outside-normal-processing, monthly Visa Bulletin), bilingual nudges (Nemotron rewrite optional), SMTP via env, 7-day throttle, `python -m packages.agents.sentinel [--dry-run]`
- [x] API: /interview/{sid}/timeline, /interview/{sid}/sentinel, /sentinel/{cid} GET/DELETE, /sentinel/run
- [x] UI: timeline card with editable filing date; Sentinel opt-in card → deadline list with urgency colors + delete
- [x] Dockerfile + docker-compose.yml (api + daily sentinel worker, shared /data volume)
- [x] docs/devpost.md (full submission draft) + docs/video-script.md (3-min shot list)
- [x] E2E: I-765 ES → timeline (c)(8) 3.5–12 mo → sentinel 4 deadlines → runner dry-run emails 1 case
- [x] 37/37 tests

## Done 2026-09-17 — Nebius key live
- [x] Key validated against Token Factory; 17 models listed; Nano ID corrected to `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` (Super ID was right)
- [x] .env written on Vesper (gitignored, never synced/committed); .env.example rewritten with verified IDs + SMTP + dirs
- [x] Live: interview phrasing (35 Qs ES in 72 s), free-text parsing (Spanish double surnames fixed via prompt), /explain ES, adjudicator on all 3 fixtures (Super 120B, 15–22 s), sentinel nudge rewrite (Nano)
- [x] Adjudicator prompt tuned from real output: planned signature_date not flagged; `_attached` = checklist; day-count tolerance 60 d
- [x] Model findings that landed: missing I-589 receipt evidence for (c)(8), interpreter Part 4 unsigned (I-765); missing lawful-entry evidence + conditional-residence note (I-130) — all cited, all correct
- [x] UI tags model findings "· Nemotron"; E2E with key: model_used=true, 5 findings (2 from Nemotron)

## Blockers
- [ ] TAVILY_API_KEY — keyless monthly limit was hit during dev; live snapshots intermittent until a key is set
- [ ] Devpost rules: one team, two entries?

## Next (Week 6)
- [ ] TAVILY_API_KEY → .env (last live-vs-stale gap)
- [ ] Derek: review Spanish (packages/schemas/es/*.es.yaml, i-130.yaml, sentinel strings)
- [ ] `docker compose up --build` on Vesper; pick a public host (VPS/Nebius VM) and put the URL in docs/devpost.md
- [ ] Record the video per docs/video-script.md; submit on Devpost (deadline Oct 30 10:00 PDT)
- [ ] Optional polish: N-400 remaining parts; Nemotron phrasing QA in Spanish
- [ ] Re-run inspector when the 09/15/26 I-765 edition posts; diff field names
