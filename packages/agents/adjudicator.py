"""Nemotron adjudicator — the fuzzy layer on top of packages/rules/checks.py.

Contract:
  * Deterministic findings are computed first and passed in; the model may ADD
    findings but never remove or downgrade one (we re-merge and keep the
    deterministic severity when ids collide).
  * The model only sees the schema's field labels/why/cites and the answers —
    i.e. the same open dataset — plus the live RuleSnapshot. No hidden rules.
  * Output is structured (Pydantic via JSON schema); every model finding must
    cite something from the provided authorities or it is dropped.
  * Without NEBIUS_API_KEY this returns [] so the product still works offline.
"""
from __future__ import annotations

import json
import os
from typing import Any, Literal

from pydantic import BaseModel, Field

from packages.agents import nebius
from packages.rules.checks import Finding
from packages.rules.snapshot import RuleSnapshot
from packages.schemas.loader import FormSchema

Severity = Literal["deny", "reject", "rfe", "info"]


class ModelFinding(BaseModel):
    id: str = Field(description="snake_case, unique, e.g. inconsistent_entry_dates")
    severity: Severity
    field: str | None = Field(default=None, description="field id from the schema, if one applies")
    text_en: str
    text_es: str
    cite: list[str] = Field(default_factory=list, description="only authorities that appear in the provided list")
    reasoning: str = Field(description="one sentence: which answers triggered this")


class ModelReview(BaseModel):
    findings: list[ModelFinding] = Field(default_factory=list)
    overall_note_en: str = ""
    overall_note_es: str = ""


SYSTEM = """You are a USCIS intake officer and adjudicator doing a pre-filing review of ONE form packet.
You receive: the form's field schema (label, why the field exists, authorities), the applicant's answers,
the live rule snapshot (edition, fees), and findings already produced by deterministic checks.

Your job: find ADDITIONAL problems the deterministic checks could not — cross-field inconsistencies
(dates that cannot both be true, a status that contradicts a category, an address history gap),
missing evidence implied by the answers, and eligibility red flags. Do not repeat findings already listed.
Do not invent rules: every finding must cite an authority from the list provided. If nothing is wrong, return no findings.
Severity: deny = likely denial or bar; reject = rejected at intake; rfe = likely Request for Evidence; info = heads-up.
Conventions: `signature_date` is the date the applicant PLANS to sign and mail; it may be in the future — never flag it.
Answers ending in `_attached` are the applicant's own checklist; treat False as "not yet attached", not as a lie.
Day counts (days_as_lpr, days_at_current_address, total_days_outside) are applicant estimates; flag only contradictions larger than 60 days.
Never give legal advice or predict the outcome; describe the problem and the fix. Write text_en in plain English and
text_es in plain Spanish. Return JSON only."""


def _compact_schema(schema: FormSchema) -> list[dict[str, Any]]:
    return [
        {"id": f.id, "label": f.label_en, "why": (f.why_en or "")[:300], "cite": f.cite}
        for f in schema.all_fields()
    ]


def _authorities(schema: FormSchema) -> set[str]:
    return {c for f in schema.all_fields() for c in f.cite}


def review(schema: FormSchema, answers: dict[str, Any], deterministic: list[Finding],
           snapshot: RuleSnapshot | None) -> tuple[list[Finding], dict[str, str]]:
    """Return (model findings as Finding objects, {en,es} overall notes). Empty when no key."""
    if not os.getenv("NEBIUS_API_KEY"):
        return [], {}
    authorities = sorted(_authorities(schema))
    user = json.dumps({
        "form": schema.form,
        "schema": _compact_schema(schema),
        "authorities": authorities,
        "answers": answers,
        "rule_snapshot": snapshot.model_dump(exclude={"fee_table_excerpt", "raw_sources"}) if snapshot else None,
        "deterministic_findings": [f.model_dump(include={"id", "severity", "field", "text_en"}) for f in deterministic],
    }, ensure_ascii=False)
    try:
        out = nebius.structured(SYSTEM, user, ModelReview, model=nebius.REASONING_MODEL)
    except Exception:  # noqa: BLE001 - the model layer is best-effort
        return [], {}
    allowed = set(authorities)
    existing = {f.id for f in deterministic}
    findings: list[Finding] = []
    for m in out.findings:
        cites = [c for c in m.cite if c in allowed]
        if not cites or m.id in existing:
            continue  # uncited or duplicate → dropped, by contract
        findings.append(Finding(id=m.id, severity=m.severity, field=m.field, text_en=m.text_en,
                                text_es=m.text_es, cite=cites, source="model"))
    return findings, {"en": out.overall_note_en, "es": out.overall_note_es}


def merge(deterministic: list[Finding], model: list[Finding]) -> list[Finding]:
    """Deterministic wins on id collision; model findings appended; sorted by severity."""
    from packages.rules.checks import SEVERITY_ORDER

    seen = {f.id for f in deterministic}
    out = list(deterministic) + [f for f in model if f.id not in seen]
    out.sort(key=lambda f: (SEVERITY_ORDER.get(f.severity, 9), f.id))
    return out
