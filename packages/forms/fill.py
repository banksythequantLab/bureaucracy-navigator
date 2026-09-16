"""Fill an official USCIS AcroForm PDF from interview answers.

USCIS PDFs ship AES-encrypted with an empty user password; pypdf needs the
`cryptography` package to open them (it is in requirements.txt).
"""
from __future__ import annotations

import io
import importlib
from pathlib import Path
from typing import Any

from pypdf import PdfReader, PdfWriter

from packages.schemas.loader import load_schema

MAPS = {"i-765": "packages.forms.maps.i_765"}


def field_values(form: str, answers: dict[str, Any]) -> dict[str, str]:
    mod = importlib.import_module(MAPS[form])
    return mod.map_answers(answers)


def fill_pdf(form: str, answers: dict[str, Any], out: str | Path | None = None) -> bytes:
    """Return the filled PDF bytes (and write to `out` if given)."""
    schema = load_schema(form)
    if not schema.pdf:
        raise ValueError(f"schema for {form} has no pdf path")
    reader = PdfReader(schema.pdf)
    if reader.is_encrypted:
        reader.decrypt("")
    writer = PdfWriter()
    writer.append(reader)

    values = field_values(form, answers)
    known = set((reader.get_fields() or {}).keys())
    unknown = sorted(k for k in values if k not in known)
    if unknown:
        raise KeyError(f"PDF field names not found (edition drift?): {unknown[:5]}")

    for page in writer.pages:
        writer.update_page_form_field_values(page, values, auto_regenerate=False)
    writer.set_need_appearances_writer(True)

    buf = io.BytesIO()
    writer.write(buf)
    data = buf.getvalue()
    if out:
        Path(out).write_bytes(data)
    return data


def read_back(pdf_bytes: bytes) -> dict[str, Any]:
    """Field name → value, for tests and for the adjudicator's 'what is actually on the page' pass."""
    r = PdfReader(io.BytesIO(pdf_bytes))
    return {k: v.get("/V") for k, v in (r.get_fields() or {}).items() if v.get("/V") not in (None, "", "/Off")}
