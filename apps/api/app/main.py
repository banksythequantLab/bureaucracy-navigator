"""Bureaucracy Navigator API.

GET  /health                        liveness + which keys are configured
GET  /forms                         schemas available
GET  /forms/{form}                  full schema (fields, why, cites, risks)
GET  /rules/{form}                  live RuleSnapshot from uscis.gov via Tavily
POST /explain/{form}/{field}        plain-language "why does this field exist" via Nemotron
POST /interview/start               {form, lang} → session + first question
GET  /interview/{sid}               state + next question + progress
POST /interview/{sid}/answer        {field_id, value | skip} → next question
POST /interview/{sid}/check         deterministic findings (+ live snapshot)
GET  /interview/{sid}/fill          filled official PDF (signature never filled)
GET  /interview/{sid}/timeline      predicted processing window (live via Tavily, else committed table)
POST /interview/{sid}/sentinel      opt in to deadline watch → case + computed deadlines
GET  /sentinel/{cid} · DELETE       view / delete a case
POST /sentinel/run                  run the notifier (dry_run=true by default)
"""
from __future__ import annotations

import os
from typing import Any, Literal

from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel

from packages.agents import adjudicator
from packages.agents import interview as iv
from packages.agents import nebius
from packages.forms.fill import fill_pdf
from packages.rules.checks import Finding, run_checks
from packages.rules.snapshot import RuleSnapshot, build_snapshot
from packages.schemas.loader import available_forms, load_schema

app = FastAPI(title="Bureaucracy Navigator", version="0.3.0")
WEB_INDEX = Path(__file__).resolve().parents[2] / "web" / "index.html"


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(WEB_INDEX)

DISCLAIMER_EN = "This tool explains and checks forms. It is not legal advice."
DISCLAIMER_ES = "Esta herramienta explica y revisa formularios. No es asesoría legal."


@app.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "nebius_key": bool(os.getenv("NEBIUS_API_KEY")),
        "tavily_key": bool(os.getenv("TAVILY_API_KEY")),
        "forms": available_forms(),
    }


@app.get("/forms")
def forms() -> dict:
    return {"forms": available_forms()}


@app.get("/forms/{form}")
def form_schema(form: str) -> dict:
    try:
        return load_schema(form).model_dump()
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e


@app.get("/rules/{form}", response_model=RuleSnapshot)
def rules(form: str, refresh: bool = False) -> RuleSnapshot:
    try:
        return build_snapshot(form, use_cache=not refresh)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Tavily lookup failed: {e}") from e


class ExplainRequest(BaseModel):
    lang: Literal["en", "es"] = "en"
    reading_level: Literal["plain", "detailed"] = "plain"


class ExplainResponse(BaseModel):
    field: str
    lang: str
    explanation: str
    cites: list[str]
    disclaimer: str


@app.post("/explain/{form}/{field_id}", response_model=ExplainResponse)
def explain(form: str, field_id: str, req: ExplainRequest) -> ExplainResponse:
    schema = load_schema(form)
    field = next((f for f in schema.all_fields() if f.id == field_id), None)
    if not field:
        raise HTTPException(404, f"No field '{field_id}' on {form}")
    lang_name = "Spanish" if req.lang == "es" else "English"
    system = (
        "You explain U.S. government form fields to ordinary people. "
        f"Answer in {lang_name}, at a {req.reading_level} reading level, in 2-4 sentences. "
        "Explain WHY the field exists and the most common mistake. Never give legal advice or "
        "predict eligibility. Cite only the authorities provided."
    )
    user = (
        f"Form: {schema.title_en} ({schema.form.upper()})\n"
        f"Field: {field.label_en}\n"
        f"Drafted rationale: {field.why_en or ''}\n"
        f"Authorities: {'; '.join(field.cite) or 'none'}"
    )
    try:
        text = nebius.chat(system, user, model=nebius.FAST_MODEL)
    except nebius.MissingKeyError as e:
        raise HTTPException(503, str(e)) from e
    return ExplainResponse(
        field=field.id,
        lang=req.lang,
        explanation=text.strip(),
        cites=field.cite,
        disclaimer=DISCLAIMER_ES if req.lang == "es" else DISCLAIMER_EN,
    )


# ----------------------------------------------------------------- interview
class StartRequest(BaseModel):
    form: str = "i-765"
    lang: Literal["en", "es"] = "en"


class InterviewState(BaseModel):
    session_id: str
    form: str
    lang: str
    progress: dict[str, int]
    question: iv.Question | None
    done: bool
    answers: dict[str, Any]


def _state(s: iv.Session) -> InterviewState:
    schema = load_schema(s.form)
    q = iv.question_for(schema, s)
    return InterviewState(session_id=s.id, form=s.form, lang=s.lang, progress=iv.progress(schema, s),
                          question=q, done=q is None, answers=s.answers)


def _session(sid: str) -> iv.Session:
    try:
        return iv.Session.load(sid)
    except KeyError as e:
        raise HTTPException(404, f"no session {sid}") from e


@app.post("/interview/start", response_model=InterviewState)
def interview_start(req: StartRequest) -> InterviewState:
    if req.form not in available_forms():
        raise HTTPException(404, f"no schema for {req.form}")
    return _state(iv.start(req.form, req.lang))


@app.get("/interview/{sid}", response_model=InterviewState)
def interview_get(sid: str) -> InterviewState:
    return _state(_session(sid))


class AnswerRequest(BaseModel):
    field_id: str
    value: Any = None
    skip: bool = False


@app.post("/interview/{sid}/answer", response_model=InterviewState)
def interview_answer(sid: str, req: AnswerRequest) -> InterviewState:
    s = _session(sid)
    try:
        iv.answer(load_schema(s.form), s, req.field_id, req.value, skip=req.skip)
    except KeyError as e:
        raise HTTPException(404, f"no field {req.field_id}") from e
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    return _state(s)


class CheckResponse(BaseModel):
    findings: list[Finding]
    counts: dict[str, int]
    snapshot_fetched_at: str | None
    snapshot_stale: bool = False
    snapshot_warnings: list[str] = []
    model_used: bool = False
    model_note: str = ""
    disclaimer: str


@app.post("/interview/{sid}/check", response_model=CheckResponse)
def interview_check(sid: str, live: bool = True, model: bool = True) -> CheckResponse:
    """Deterministic checks always run; the Nemotron adjudicator adds findings when a key is configured."""
    s = _session(sid)
    schema = load_schema(s.form)
    snap = None
    if live:
        try:
            snap = build_snapshot(s.form)
        except Exception:  # noqa: BLE001 - checks still run without the live layer
            snap = None
    det = run_checks(schema, s.answers, snap)
    findings, note = det, {}
    used = False
    if model and os.getenv("NEBIUS_API_KEY"):
        extra, note = adjudicator.review(schema, s.answers, det, snap)
        findings = adjudicator.merge(det, extra)
        used = True
    counts: dict[str, int] = {}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1
    return CheckResponse(findings=findings, counts=counts,
                         snapshot_fetched_at=snap.fetched_at if snap else None,
                         snapshot_stale=snap.stale if snap else False,
                         snapshot_warnings=snap.warnings if snap else [],
                         model_used=used, model_note=note.get(s.lang, "") if note else "",
                         disclaimer=DISCLAIMER_ES if s.lang == "es" else DISCLAIMER_EN)


@app.get("/interview/{sid}/fill")
def interview_fill(sid: str) -> Response:
    s = _session(sid)
    try:
        data = fill_pdf(s.form, s.answers)
    except FileNotFoundError as e:
        raise HTTPException(503, f"official PDF not present on server: {e}") from e
    except KeyError as e:
        raise HTTPException(500, str(e)) from e
    return Response(content=data, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{s.form}-{s.id}.pdf"'})


# ----------------------------------------------------------------- timeline + sentinel
from packages.agents import sentinel  # noqa: E402
from packages.rules.timeline import Timeline, predict  # noqa: E402


@app.get("/interview/{sid}/timeline", response_model=Timeline)
def interview_timeline(sid: str, filed_on: str | None = None) -> Timeline:
    s = _session(sid)
    return predict(s.form, s.answers, filed_on)


class SentinelOptIn(BaseModel):
    email: str | None = None
    filed_on: str | None = None
    receipt_number: str | None = None
    ead_expires: str | None = None
    i94_expires: str | None = None
    rfe_received_on: str | None = None
    rfe_due_on: str | None = None
    lpr_since: str | None = None
    basis: str | None = None
    priority_date: str | None = None


class SentinelCase(BaseModel):
    case_id: str
    form: str
    lang: str
    deadlines: list[sentinel.Deadline]


def _case_view(c: sentinel.Case) -> SentinelCase:
    return SentinelCase(case_id=c.id, form=c.form, lang=c.lang, deadlines=sentinel.compute_deadlines(c))


@app.post("/interview/{sid}/sentinel", response_model=SentinelCase)
def sentinel_optin(sid: str, req: SentinelOptIn) -> SentinelCase:
    """Create an opt-in deadline-watch case from an interview. Dates that the interview already knows are pre-filled."""
    s = _session(sid)
    a = s.answers
    fields = req.model_dump(exclude_none=True)
    fields.setdefault("lpr_since", a.get("lpr_date"))
    fields.setdefault("basis", a.get("basis"))
    if s.form == "i-765" and a.get("days_until_ead_expiry") and not fields.get("ead_expires"):
        from datetime import date, timedelta
        fields["ead_expires"] = (date.today() + timedelta(days=int(a["days_until_ead_expiry"]))).isoformat()
    c = sentinel.new_case(s.form, s.lang, answers=a, **{k: v for k, v in fields.items() if v is not None})
    return _case_view(c)


@app.get("/sentinel/{cid}", response_model=SentinelCase)
def sentinel_get(cid: str) -> SentinelCase:
    try:
        return _case_view(sentinel.Case.load(cid))
    except KeyError as e:
        raise HTTPException(404, f"no case {cid}") from e


@app.delete("/sentinel/{cid}")
def sentinel_delete(cid: str) -> dict:
    try:
        sentinel.Case.load(cid).delete()
    except KeyError as e:
        raise HTTPException(404, f"no case {cid}") from e
    return {"deleted": cid}


@app.post("/sentinel/run")
def sentinel_run(dry_run: bool = True) -> list[dict]:
    """Manual trigger for the runner (cron calls `python -m packages.agents.sentinel`)."""
    return sentinel.run_once(dry_run=dry_run)
