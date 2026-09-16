"""Bureaucracy Navigator API — week-1 surface.

GET  /health                 liveness + which keys are configured
GET  /forms                  schemas available
GET  /forms/{form}           full schema (fields, why, cites, risks)
GET  /rules/{form}           live RuleSnapshot from uscis.gov via Tavily
POST /explain/{form}/{field} plain-language "why does this field exist" via Nemotron
"""
from __future__ import annotations

import os
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from packages.agents import nebius
from packages.rules.snapshot import RuleSnapshot, build_snapshot
from packages.schemas.loader import available_forms, load_schema

app = FastAPI(title="Bureaucracy Navigator", version="0.1.0")

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
