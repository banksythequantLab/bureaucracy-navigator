# Bureaucracy Navigator

*Government forms, explained like a lawyer would — filled, checked, and tracked in your language.*

Entry for the [Nebius x NVIDIA Global AI Hackathon](https://nebiusglobalaihackathon.devpost.com/) by Banksy AI LLC.
Built on **Nebius Token Factory** (NVIDIA **Nemotron 3**) with **Tavily** keeping every fee, edition date, and filing address live from uscis.gov.

**Not legal advice.** This tool explains and checks forms; it does not give legal advice or predict eligibility. / *No es asesoría legal.*

## What it does (v1 scope: I-130, I-765, N-400 · EN/ES) — I-765 and N-400 fill today; I-130 next

1. **Live rule check** — Tavily extracts today's edition date, fee (paper vs online), biometrics rule, and filing address; nothing is hardcoded.
2. **Interview** — Nemotron asks one plain-language question at a time and branches (e.g., I-765 category decides fee, biometrics, address).
3. **"Why does this field exist?"** — every field carries its legal basis (INA / 8 CFR / Fed. Reg.) and its known failure modes.
4. **Fill** — official USCIS AcroForm PDFs populated with pypdf.
5. **Rejection Simulator** — an adjudicator pass scores the packet: hard rejects, likely RFEs, denial risks (e.g., the July 10 2026 signature rule), each with a cited fix.
6. **Deadline Sentinel** — tracks renewal windows, RFE due dates, Visa Bulletin movement.

## Quick start (Windows PowerShell)

```powershell
git clone https://github.com/banksythequantlab/bureaucracy-navigator.git
cd bureaucracy-navigator
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env   # then paste NEBIUS_API_KEY (and TAVILY_API_KEY)
pytest -q                     # offline tests, no keys needed
uvicorn apps.api.app.main:app --reload
# open http://127.0.0.1:8000/  ← bilingual web UI (rule card → interview → rejection simulator → PDF)
```

Then:

```powershell
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/rules/i-765          # live from uscis.gov via Tavily
curl http://127.0.0.1:8000/forms/i-765          # schema with why + cites + risks
curl -X POST http://127.0.0.1:8000/explain/i-765/category -H "content-type: application/json" -d "{\"lang\":\"es\"}"

# Interview → check → fill (works offline; Nemotron only phrases/parses when NEBIUS_API_KEY is set)
curl -X POST http://127.0.0.1:8000/interview/start -H "content-type: application/json" -d "{\"form\":\"i-765\",\"lang\":\"es\"}"
curl -X POST http://127.0.0.1:8000/interview/<sid>/answer -H "content-type: application/json" -d "{\"field_id\":\"reason\",\"value\":\"renewal\"}"
curl -X POST http://127.0.0.1:8000/interview/<sid>/check      # deny / reject / rfe / info findings, cited
curl -o i-765.filled.pdf http://127.0.0.1:8000/interview/<sid>/fill
```

The filler never writes the signature field: the official PDF says it "can not be signed electronically", and a typed name there is a denial trigger under the July 2026 signature rule.

## Layout

```
apps/web/index.html       single-file EN/ES UI served at /
apps/api/app/main.py      FastAPI: /health /forms /rules /explain /interview/* (start, answer, check, fill)
packages/schemas/*.yaml   field → statute → risk, EN/ES, required_when branching  (CC-BY-4.0 open dataset)
packages/rules/snapshot   Tavily RuleSnapshot: uscis.gov form page + G-1055 PDF → edition, fee, addresses; 24h cache;
                          falls back to packages/rules/known/*.json (flagged stale) if the live lookup fails
packages/rules/checks     deterministic adjudicator core: schema risks, required_when, edition drift, fee drift
packages/agents/nebius    Nebius/Nemotron client (reasoning + fast tiers, structured output)
packages/agents/interview deterministic question order; Nemotron phrases questions + parses free text (optional)
packages/forms/           official USCIS PDFs, AcroForm inspector, answers→field maps, pypdf filler
tests/                    24 offline tests incl. real-PDF fill + read-back and a seeded bad packet
```

## Roadmap

| Week | Deliverable |
|---|---|
| 1 | Scaffold, Nebius client, Tavily RuleSnapshot, I-765 schema (EN) ✅ |
| 2 | Interview agent on I-765; pypdf fill of the official PDF; deterministic adjudicator core ✅ |
| 3 | N-400 schema + PDF fill; web UI (EN/ES); known-snapshot fallback for all 3 forms ✅ — Spanish why/finding text + Nemotron phrasing pending keys |
| 4 | Adjudicator agent + deterministic checks; I-130 schema + fill |
| 5 | Processing-time predictor; Deadline Sentinel |
| 6 | Polish, 3-minute video, hosted demo, Devpost submission |

## License

Apache-2.0 (code). Form schemas in `packages/schemas/` are CC-BY-4.0.
