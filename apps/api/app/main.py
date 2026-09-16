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
"""
from __future__ import annotations

import os
from typing import Any, Literal

from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel

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
    disclaimer: str


@app.post("/interview/{sid}/check", response_model=CheckResponse)
def interview_check(sid: str, live: bool = True) -> CheckResponse:
    s = _session(sid)
    schema = load_schema(s.form)
    snap = None
    if live:
        try:
            snap = build_snapshot(s.form)
        except Exception:  # noqa: BLE001 - checks still run without the live layer
            snap = None
    findings = run_checks(schema, s.answers, snap)
    counts: dict[str, int] = {}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1
    return CheckResponse(findings=findings, counts=counts,
                         snapshot_fetched_at=snap.fetched_at if snap else None,
                         snapshot_stale=snap.stale if snap else False,
                         snapshot_warnings=snap.warnings if snap else [],
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
