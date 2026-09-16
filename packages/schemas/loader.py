"""Load and validate form schemas from packages/schemas/*.yaml."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

SCHEMA_DIR = Path(__file__).parent


class Risk(BaseModel):
    id: str
    severity: str  # reject | rfe | deny
    when: str
    text_en: str
    text_es: str | None = None


class FieldDef(BaseModel):
    id: str
    type: str
    label_en: str
    label_es: str | None = None
    why_en: str | None = None
    why_es: str | None = None
    required: bool = True
    required_when: str | None = None  # python-ish expression over answers; see rules/checks.py
    options: list[str] | None = None
    pattern: str | None = None
    item_type: str | None = None
    max_items: int | None = None
    pdf_field: str | None = None
    cite: list[str] = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)


class Section(BaseModel):
    id: str
    title_en: str
    title_es: str | None = None
    fields: list[FieldDef]


class FormSchema(BaseModel):
    form: str
    title_en: str
    title_es: str | None = None
    official_url: str
    pdf: str | None = None
    pdf_edition: str | None = None
    license: str = "CC-BY-4.0"
    sections: list[Section]
    fees: dict[str, Any] = Field(default_factory=dict)

    def all_fields(self) -> list[FieldDef]:
        return [f for s in self.sections for f in s.fields]

    def all_risks(self) -> list[Risk]:
        return [r for f in self.all_fields() for r in f.risks]


def load_schema(form: str) -> FormSchema:
    p = SCHEMA_DIR / f"{form.lower()}.yaml"
    if not p.exists():
        raise FileNotFoundError(f"No schema for form '{form}' at {p}")
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    return FormSchema.model_validate(data)


def available_forms() -> list[str]:
    return sorted(p.stem for p in SCHEMA_DIR.glob("*.yaml"))
