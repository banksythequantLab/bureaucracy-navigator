# Bureaucracy Navigator — task tracker
_Nebius x NVIDIA Global AI Hackathon · deadline Oct 30 2026 10:00 PDT · Notion: 🧭 Nebius x NVIDIA Hackathon 2026 — Bureaucracy Navigator_

## Done 2026-09-16 (Cowork/Fable) — Week 1 scaffold
- [x] Context7 pull: openai-python (base_url + chat.completions.parse), tavily-python (search/extract params, keyless mode), pypdf (get_fields/update_page_form_field_values)
- [x] Repo scaffold D:\bureaucracy-navigator → https://github.com/banksythequantLab/bureaucracy-navigator (public, Apache-2.0; schemas CC-BY-4.0)
- [x] packages/agents/nebius.py — Token Factory client, reasoning + fast tiers, structured() with json_schema→json_object fallback
- [x] packages/rules/snapshot.py — Tavily Extract of uscis.gov form page + G-1055 PDF → edition dates, new-edition alert, paper/online fee, where-to-file, 24h cache
- [x] packages/schemas/i-765.yaml + loader.py — field → why → cite → risks (EN; ES slots)
- [x] apps/api/app/main.py — /health /forms /forms/{form} /rules/{form} /explain/{form}/{field}
- [x] tests: 9 passing (cloud + Vesper venv)
- [x] Live smoke (keyless Tavily): I-765 edition 08/21/25, alert 09/15/26, $520/$470, G-1055 ed 09/09/26, where-to-file URL, 0 warnings
- [x] Fact fix: dropped stale $85 biometrics rules; added Pub. L. 119-21 separate-payment + I-485-pending $260 risks

## Blockers
- [ ] NEBIUS_API_KEY not yet created → /explain returns 503 by design until set
- [ ] Confirm Nemotron 3 Nano model ID in Token Factory console (env default is a guess)
- [ ] Devpost rules: can one team submit both this and Bottle Tree appraiser?

## Next (Week 2, Sep 24–30)
- [ ] Download official I-765 PDF → `python -m packages.forms.inspect` → map pdf_field in schema
- [ ] Interview agent (Super 120B, structured output) on I-765
- [ ] /fill endpoint with pypdf; smoke: filled PDF opens in Acrobat
- [ ] RuleSnapshot for I-130 and N-400 (parsers already handle their G-1055 rows — tested)
