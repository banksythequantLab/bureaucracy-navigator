"""Interview agent.

Control flow is deterministic (schema order + required_when), so the model can
never skip a required item or invent one. Nemotron is used for two narrow jobs:
  phrase()  — turn a field into one friendly question in the user's language
  parse()   — turn free-text into the field's typed value (JSON mode)
Both degrade gracefully without NEBIUS_API_KEY: phrase() falls back to the
schema label, parse() to a simple typed coercion. That keeps the interview
runnable offline and the tests hermetic.
"""
from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from packages.agents import nebius
from packages.rules.checks import evaluate
from packages.schemas.loader import FieldDef, FormSchema, load_schema

SESSION_DIR = Path(os.getenv("BN_SESSION_DIR", ".cache/sessions"))

Lang = Literal["en", "es"]


class Question(BaseModel):
    field_id: str
    section: str
    type: str
    options: list[str] | None = None
    text: str
    why: str | None = None
    cite: list[str] = Field(default_factory=list)
    required: bool = True


class Session(BaseModel):
    id: str
    form: str
    lang: Lang = "en"
    answers: dict[str, Any] = Field(default_factory=dict)
    skipped: list[str] = Field(default_factory=list)
    created_at: str
    updated_at: str

    def save(self) -> None:
        SESSION_DIR.mkdir(parents=True, exist_ok=True)
        self.updated_at = datetime.now(timezone.utc).isoformat()
        (SESSION_DIR / f"{self.id}.json").write_text(self.model_dump_json(indent=2), encoding="utf-8")

    @classmethod
    def load(cls, sid: str) -> "Session":
        p = SESSION_DIR / f"{sid}.json"
        if not p.exists():
            raise KeyError(sid)
        return cls.model_validate_json(p.read_text(encoding="utf-8"))


def start(form: str, lang: Lang = "en") -> Session:
    now = datetime.now(timezone.utc).isoformat()
    s = Session(id=uuid.uuid4().hex[:12], form=form, lang=lang, created_at=now, updated_at=now)
    s.save()
    return s


# ---------------------------------------------------------------- control flow
def _applies(field: FieldDef, answers: dict[str, Any]) -> bool:
    if field.required_when is None:
        return True
    return evaluate(field.required_when, answers)


def next_field(schema: FormSchema, s: Session) -> tuple[FieldDef, str] | None:
    for sec in schema.sections:
        for f in sec.fields:
            if f.id in s.answers or f.id in s.skipped:
                continue
            if not _applies(f, s.answers):
                continue
            return f, sec.title_en if s.lang == "en" else (sec.title_es or sec.title_en)
    return None


def progress(schema: FormSchema, s: Session) -> dict[str, int]:
    applicable = [f for f in schema.all_fields() if _applies(f, s.answers)]
    done = [f for f in applicable if f.id in s.answers or f.id in s.skipped]
    return {"answered": len(done), "total": len(applicable)}


# ---------------------------------------------------------------- phrasing
def phrase(field: FieldDef, lang: Lang, answers: dict[str, Any]) -> str:
    label = field.label_en if lang == "en" else (field.label_es or field.label_en)
    if not os.getenv("NEBIUS_API_KEY"):
        return label
    lang_name = "Spanish" if lang == "es" else "English"
    system = (
        f"You are a calm, plain-language interviewer helping someone complete USCIS Form. "
        f"Ask exactly ONE question in {lang_name}, one or two sentences, no legal advice, "
        "no eligibility predictions. If the item has options, list them briefly."
    )
    user = (
        f"Item label: {label}\nType: {field.type}\nOptions: {field.options or 'n/a'}\n"
        f"Already known about the applicant: {json.dumps({k: v for k, v in answers.items() if k in ('reason', 'category')})}"
    )
    try:
        return nebius.chat(system, user, model=nebius.FAST_MODEL, temperature=0.3).strip() or label
    except Exception:  # noqa: BLE001
        return label


def question_for(schema: FormSchema, s: Session) -> Optional[Question]:
    nf = next_field(schema, s)
    if not nf:
        return None
    f, section = nf
    why = f.why_en if s.lang == "en" else (f.why_es or f.why_en)
    return Question(field_id=f.id, section=section, type=f.type, options=f.options,
                    text=phrase(f, s.lang, s.answers), why=why, cite=f.cite,
                    required=f.required if f.required_when is None else True)


# ---------------------------------------------------------------- parsing
_YES = {"yes", "y", "true", "si", "sí", "1"}
_NO = {"no", "n", "false", "0"}


class _Parsed(BaseModel):
    value: Any
    confident: bool = True


def parse(field: FieldDef, raw: Any, lang: Lang) -> Any:
    """Coerce a raw answer (already-typed JSON or free text) into the field's type."""
    if not isinstance(raw, str):
        return raw  # UI sent a typed value (dict/list/bool) — trust it
    t = raw.strip()
    if field.type == "bool":
        low = t.lower()
        if low in _YES:
            return True
        if low in _NO:
            return False
    if field.type == "choice" and field.options:
        low = t.lower()
        for o in field.options:
            if low == o.lower() or low == o.replace("_", " ").lower():
                return o
    if field.type == "date":
        m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", t)
        if m:
            return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", t):
            return t
    if field.type == "category":
        m = re.search(r"\(?\s*([a-cA-C])\s*\)?\s*\(?\s*(\d{1,2})\s*\)?\s*(\(?\s*([ivx]+)\s*\)?)?", t)
        if m:
            base = f"({m.group(1).lower()})({m.group(2)})"
            return base + (f"({m.group(4)})" if m.group(4) else "")
    if field.type == "int":
        m = re.search(r"-?\d+", t.replace(",", ""))
        return int(m.group(0)) if m else t
    if field.type in ("text",):
        return t
    # Composite or ambiguous → ask the model if we can, else return raw text
    if os.getenv("NEBIUS_API_KEY"):
        try:
            system = ("Extract the answer into JSON. Types: name→{family,given,middle}; "
                      "address→{in_care_of,street,unit_type(apt|ste|flr|''),unit,city,state(2-letter),zip}; "
                      "place→{city,state,country}; passport→{number,country,expires(YYYY-MM-DD)}; "
                      "list→[...]; bool→true/false; date→YYYY-MM-DD; choice→one of the options exactly. "
                      "Return {\"value\": <typed>, \"confident\": <bool>}.")
            user = f"Field type: {field.type}\nItem type: {field.item_type}\nOptions: {field.options}\nAnswer text: {t}"
            return nebius.structured(system, user, _Parsed, model=nebius.FAST_MODEL).value
        except Exception:  # noqa: BLE001
            pass
    return t


def answer(schema: FormSchema, s: Session, field_id: str, raw: Any, *, skip: bool = False) -> Session:
    f = next((x for x in schema.all_fields() if x.id == field_id), None)
    if not f:
        raise KeyError(field_id)
    if skip:
        if f.required and f.required_when is None:
            raise ValueError(f"{field_id} is required")
        s.skipped.append(field_id)
    else:
        s.answers[field_id] = parse(f, raw, s.lang)
    s.save()
    return s


def schema_for(s: Session) -> FormSchema:
    return load_schema(s.form)
