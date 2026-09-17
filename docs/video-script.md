# 3-minute demo video — shot list & script

Recording: screen capture of the web UI at 1280×800, Spanish mode for the interview beats, English voice-over (or bilingual). Keep the cursor slow. Total ≤ 2:55.

| Time | On screen | Voice-over |
|---|---|---|
| 0:00–0:20 | Title card, then a real USCIS rejection notice (blurred) | "Every year families lose months — sometimes a whole year — to immigration forms rejected for reasons that have nothing to do with eligibility. A typed signature. A fee that changed last month. The wrong edition date. Since July 2026, USCIS can even deny an accepted case over the signature and keep the fee. I'm an attorney; I've seen it. This is Bureaucracy Navigator." |
| 0:20–0:40 | App opens. Pick **I-765**, switch to **Español**. Rule card populates with the green *en vivo* badge. Hover the "source" links. | "Before the first question, Tavily reads uscis.gov and the G-1055 fee schedule PDF — right now, not at training time. Accepted edition, paper fee, online fee, a new-edition alert, where to file. Every number has a source and a timestamp." |
| 0:40–1:10 | Click **Comenzar entrevista**. Answer 4–5 questions: reason (renewal), name, address. Open **¿Por qué existe este campo?** on the A-Number question. | "The interview asks one thing at a time, in the applicant's language. And every field explains itself — why it exists, and the regulation behind it. This is the open dataset we're releasing: field, PDF widget, statute, risk rule." |
| 1:10–1:35 | Reach category **(c)(8)**. Open the why panel. Then the *Before you mail* section: fee, separate-payment question. | "Here's the field that decides everything for a work permit: the category. It sets the fee, the filing address, and — for asylum applicants — a separate non-waivable payment under Public Law 119-21. Our first draft had an old $85 biometrics rule here. The live G-1055 showed it's gone. The product caught our own mistake." |
| 1:35–2:05 | Finish. **Simulador de rechazo** appears: red *Riesgo de denegación* (typed signature), orange *Rechazo* (combined fee), blue *Aviso* (new edition). Point at citations. | "Then the rejection simulator. Deterministic checks first — required items, fee against today's schedule, edition drift, the signature rule. Then Nemotron 3 Super on Nebius reviews the whole packet for cross-field problems. The model can add a finding, never remove one, and every finding it adds must cite an authority or it's dropped." |
| 2:05–2:20 | Click **Descargar PDF completado**. Show the official I-765 page 1 and page 3 filled; zoom on the empty signature box. | "The official PDF, filled — checkboxes, comb boxes, the right edition. The one thing we never fill is the signature. The form itself says it can't be signed electronically." |
| 2:20–2:45 | **Tiempo de procesamiento** card, type a filing date, dates update. **Vigilante de plazos**: enter EAD expiry, click *Vigilar mis plazos*; deadlines list with 8 CFR cites. | "After filing, the clocks start. Predicted processing window for this exact category. And the Deadline Sentinel: renewal window, expiry with the 540-day auto-extension, RFE due date — each with its rule — emailed when they're close." |
| 2:45–2:55 | Stack slide: Nebius Token Factory · NVIDIA Nemotron 3 · Tavily · open source, CC-BY schemas. Repo URL. "Not legal advice." | "Nebius, Nemotron, Tavily. Open source, open schemas. Three forms today, in English and Spanish. Bureaucracy Navigator." |

## Capture checklist
- [ ] `.env` with NEBIUS_API_KEY + TAVILY_API_KEY so the *en vivo* badge and "Nemotron review ✓" both appear
- [ ] `rm -rf .cache` before recording so the rule card fetch is visibly live
- [ ] Seed answers: tests/fixtures/i765_answers.json (typed signature + combined fee → the two red/orange findings)
- [ ] Record once in Spanish, once in English; cut the Spanish interview + English findings if time is short
- [ ] Blur any real names on the rejection-notice prop; use the fixture names on screen
