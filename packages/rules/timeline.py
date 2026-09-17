"""Processing-time predictor.

USCIS publishes processing times per form / category / office at
egov.uscis.gov/processing-times (JS-rendered; the historic page is a template
until hydrated). Live path: Tavily Extract on the check-case-processing page for
the form, parsed for "X to Y months". Fallback: packages/rules/known/processing_times.json
(compiled Sep 2026), always flagged `stale=True`.

The key is chosen from the applicant's answers:
  i-765 → category code           n-400 → default
  i-130 → f"{petitioner_status}:{relationship}"
"""
from __future__ import annotations

import json
import os
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel

KNOWN = Path(__file__).parent / "known" / "processing_times.json"
LIVE_PAGE = "https://egov.uscis.gov/processing-times/"


class Timeline(BaseModel):
    form: str
    key: str
    label: str
    min_months: float
    max_months: float
    as_of: str
    stale: bool
    source: str
    filed_on: Optional[str] = None
    earliest: Optional[str] = None
    latest: Optional[str] = None
    inquiry_after: Optional[str] = None  # USCIS lets you ask about a case once it is past the posted time


def select_key(form: str, answers: dict[str, Any]) -> str:
    if form == "i-765":
        return (answers.get("category") or "default").replace(" ", "")
    if form == "i-130":
        return f"{answers.get('petitioner_status') or 'usc'}:{answers.get('relationship') or 'spouse'}"
    return "default"


def _known(form: str, key: str) -> Timeline:
    d = json.loads(KNOWN.read_text(encoding="utf-8"))
    table = d["forms"].get(form, {})
    row = table.get(key) or table["default"]
    return Timeline(form=form, key=key if key in table else "default", label=row["label"],
                    min_months=row["min_months"], max_months=row["max_months"],
                    as_of=d["as_of"], stale=True, source=d["source"])


_RANGE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:to|-|–)\s*(\d+(?:\.\d+)?)\s*months", re.I)


def _live(form: str, key: str) -> Optional[Timeline]:
    """Best-effort live read. Returns None when Tavily is unavailable or nothing parses."""
    if not os.getenv("TAVILY_API_KEY"):
        return None
    try:
        from tavily import TavilyClient

        resp = TavilyClient(api_key=os.getenv("TAVILY_API_KEY")).extract(
            urls=[LIVE_PAGE], extract_depth="advanced", format="text")
        md = " ".join(r.get("raw_content", "") for r in resp.get("results", []))
    except Exception:  # noqa: BLE001
        return None
    i = md.upper().find(form.upper())
    window = md[i : i + 3000] if i >= 0 else md
    m = _RANGE.search(window)
    if not m:
        return None
    lo, hi = float(m.group(1)), float(m.group(2))
    return Timeline(form=form, key=key, label=f"{form.upper()} (live)", min_months=lo, max_months=hi,
                    as_of=date.today().isoformat(), stale=False, source=LIVE_PAGE)


def _add_months(d: date, months: float) -> date:
    return d + timedelta(days=round(months * 30.44))


def predict(form: str, answers: dict[str, Any], filed_on: str | date | None = None) -> Timeline:
    key = select_key(form, answers)
    t = _live(form, key) or _known(form, key)
    if filed_on:
        f = date.fromisoformat(filed_on) if isinstance(filed_on, str) else filed_on
        t.filed_on = f.isoformat()
        t.earliest = _add_months(f, t.min_months).isoformat()
        t.latest = _add_months(f, t.max_months).isoformat()
        t.inquiry_after = t.latest
    return t
