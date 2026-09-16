# Bureaucracy Navigator

*Government forms, explained like a lawyer would — filled, checked, and tracked in your language.*

Entry for the [Nebius x NVIDIA Global AI Hackathon](https://nebiusglobalaihackathon.devpost.com/) by Banksy AI LLC.
Built on **Nebius Token Factory** (NVIDIA **Nemotron 3**) with **Tavily** keeping every fee, edition date, and filing address live from uscis.gov.

**Not legal advice.** This tool explains and checks forms; it does not give legal advice or predict eligibility. / *No es asesoría legal.*

## What it does (v1 scope: I-130, I-765, N-400 · EN/ES)

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
```

Then:

```powershell
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/rules/i-765          # live from uscis.gov via Tavily
curl http://127.0.0.1:8000/forms/i-765          # schema with why + cites + risks
curl -X POST http://127.0.0.1:8000/explain/i-765/category -H "content-type: application/json" -d "{\"lang\":\"es\"}"
```

## Layout

```
apps/api/app/main.py      FastAPI: /health /forms /rules /explain  (interview, fill, adjudicate → weeks 2-4)
packages/schemas/*.yaml   field → pdf_field → statute → risk, EN/ES  (CC-BY-4.0 open dataset)
packages/rules/           Tavily RuleSnapshot + uscis.gov parsers + 24h cache
packages/agents/          Nebius/Nemotron client (reasoning + fast tiers, structured output)
packages/forms/           official USCIS PDFs + AcroForm inspector
tests/                    offline parser + API tests
```

## Roadmap

| Week | Deliverable |
|---|---|
| 1 | Scaffold, Nebius client, Tavily RuleSnapshot, I-765 schema (EN) ✅ |
| 2 | Interview agent on I-765; pypdf fill of the official PDF |
| 3 | Explainer + citations; Spanish for I-765; N-400 schema |
| 4 | Adjudicator agent + deterministic checks; I-130 schema + fill |
| 5 | Processing-time predictor; Deadline Sentinel |
| 6 | Polish, 3-minute video, hosted demo, Devpost submission |

## License

Apache-2.0 (code). Form schemas in `packages/schemas/` are CC-BY-4.0.
