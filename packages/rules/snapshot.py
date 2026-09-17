"""RuleSnapshot: live agency facts for a form, pulled via Tavily, never hardcoded.

For a form id (e.g. "i-765") this fetches from uscis.gov:
  - current edition date(s) accepted
  - filing fee (paper vs online) and biometrics note
  - where-to-file page
  - processing-time page
and returns a RuleSnapshot with `fetched_at` and the source URL for every field.

Parsing is deliberately regex-based and conservative: if a value cannot be found,
it is left None and the UI shows "could not verify today" rather than a guess.
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()

CACHE_DIR = Path(os.getenv("BN_CACHE_DIR", ".cache/rules"))
CACHE_TTL_S = int(os.getenv("BN_RULES_TTL_SECONDS", str(24 * 3600)))

FORM_PAGES = {
    "i-130": "https://www.uscis.gov/i-130",
    "i-765": "https://www.uscis.gov/i-765",
    "n-400": "https://www.uscis.gov/n-400",
}
# The G-1055 web page is a JS fee lookup with no static amounts; the PDF is the
# authoritative schedule and Tavily Extract reads it cleanly.
FEE_PAGE = "https://www.uscis.gov/sites/default/files/document/forms/g-1055.pdf"
PROC_TIME_PAGE = "https://egov.uscis.gov/processing-times/"
FORM_TITLES = {
    "i-130": "I-130 Petition for Alien Relative",
    "i-765": "I-765 Application for Employment Authorization",
    "n-400": "N-400 Application for Naturalization",
}


class Sourced(BaseModel):
    value: Optional[str] = None
    source_url: Optional[str] = None
    excerpt: Optional[str] = None


class RuleSnapshot(BaseModel):
    form: str
    fetched_at: str
    edition_dates: Sourced = Field(default_factory=Sourced)
    edition_alert: Sourced = Field(default_factory=Sourced)  # e.g. "new edition 09/15/26" banner
    # Cutover parsed from "Reject the <old> edition ... on or after <date>" language (no-grace-period revisions)
    cutover_old_edition: Optional[str] = None
    cutover_new_edition: Optional[str] = None
    cutover_effective: Optional[str] = None  # ISO date
    cutover_excerpt: Optional[str] = None
    fee_schedule_edition: Optional[str] = None
    fee_table_excerpt: Optional[str] = None  # full G-1055 row(s) for the adjudicator
    fee_paper: Sourced = Field(default_factory=Sourced)
    fee_online: Sourced = Field(default_factory=Sourced)
    biometrics_note: Sourced = Field(default_factory=Sourced)
    where_to_file_url: Optional[str] = None
    processing_time_url: Optional[str] = None
    raw_sources: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    stale: bool = False  # True when served from packages/rules/known/ because the live lookup failed

    @property
    def verified(self) -> bool:
        return bool(self.edition_dates.value and (self.fee_paper.value or self.fee_online.value))


# --------------------------------------------------------------------------- Tavily
def _tavily():
    from tavily import TavilyClient  # imported lazily so tests can run without it

    key = os.getenv("TAVILY_API_KEY")
    # Keyless mode is supported by tavily-python (rate-limited). Good enough for dev.
    return TavilyClient(api_key=key) if key else TavilyClient()


def _extract(urls: list[str]) -> dict[str, str]:
    """Return {url: markdown} for each URL Tavily could extract."""
    resp = _tavily().extract(urls=urls, extract_depth="advanced", format="markdown")
    out = {r["url"]: r.get("raw_content", "") for r in resp.get("results", [])}
    return out


def _search_uscis(query: str, max_results: int = 3) -> list[dict]:
    resp = _tavily().search(
        query,
        search_depth="advanced",
        include_domains=["uscis.gov"],
        max_results=max_results,
    )
    return resp.get("results", [])


# --------------------------------------------------------------------------- parsing
_DATE = r"(\d{2}/\d{2}/\d{2,4})"
_MONEY = r"\$\s?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)"


def _find(pattern: str, text: str, flags=re.I | re.S) -> Optional[re.Match]:
    return re.search(pattern, text, flags)


_DATE_STRICT = r"(?<![\d/])(\d{2}/\d{2}/\d{2})(?![\d/])"  # mm/dd/yy, not inside a URL like 2026/07/17


def parse_edition_dates(md: str) -> Optional[tuple[str, str]]:
    """Return (value, excerpt) from the page's 'Edition Date' section.

    uscis.gov renders the label and the dates in separate table cells; the
    extracted markdown puts them a few characters apart, so we look at the
    first ~300 characters after the label and keep mm/dd/yy tokens only.
    """
    # Case-sensitive: the section label is "Edition Date"; alert banners say
    # "(edition date: mm/dd/yy)" and are handled by parse_edition_alert.
    m = _find(r"\bEdition Date\b.{0,300}", md, flags=re.S)
    if not m:
        return None
    chunk = m.group(0)
    dates = re.findall(_DATE_STRICT, chunk)
    if not dates:
        return None
    seen: list[str] = []
    for d in dates:
        if d not in seen:
            seen.append(d)
    return ", ".join(seen), chunk[:300]


def parse_edition_alert(md: str) -> Optional[tuple[str, str]]:
    """A 'new edition' banner such as '(edition date: 09/15/26)' near the top of the page."""
    m = _find(r"\(edition date:\s*" + _DATE_STRICT + r"\)", md)
    if not m:
        return None
    s = max(0, m.start() - 200)
    return m.group(1), md[s : m.end() + 100]


_NEXT_FORM = re.compile(r"\b[A-Z]{1,2}-\d{3}[A-Z]{0,2}\s+(?:Petition|Application|Request|Notice|Declaration|Supplement|Affidavit|Report|Consent)\b")


def _row_text(md: str, start: int, limit: int = 900) -> str:
    """Text from `start` up to the next form's title (or `limit` chars)."""
    chunk = md[start : start + limit]
    nxt = _NEXT_FORM.search(chunk, 20)
    return chunk[: nxt.start()] if nxt else chunk


_MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def parse_cutover(md: str) -> Optional[dict[str, str]]:
    """Detect 'Reject the 08/21/25 edition ... on or after Sept. 15, 2026' and the replacing edition."""
    m = re.search(r"Reject the\s+" + _DATE_STRICT + r"\s+edition[^.]{0,160}?on or after\s+([A-Z][a-z]{2,8})\.?\s+(\d{1,2}),\s+(\d{4})", md)
    if not m:
        return None
    old = m.group(1)
    mon = _MONTHS.get(m.group(2)[:3].lower())
    if not mon:
        return None
    eff = f"{int(m.group(4)):04d}-{mon:02d}-{int(m.group(3)):02d}"
    new = None
    m2 = re.search(r"Only accept the\s+" + _DATE_STRICT + r"\s+edition", md)
    if m2:
        new = m2.group(1)
    s0 = max(0, m.start() - 120)
    return {"old": old, "new": new or "", "effective": eff, "excerpt": md[s0 : m.end() + 160]}


def parse_fee_row(g1055_md: str, form_title: str) -> dict[str, str]:
    """Parse the general-filing row for a form from the G-1055 PDF text.

    Returns keys: paper, online (when present), excerpt (the row text), and
    schedule_edition (the 'Form G-1055 Edition mm/dd/yy' stamp).
    """
    out: dict[str, str] = {}
    ed = _find(r"Form G-1055 Edition\s+" + _DATE_STRICT, g1055_md)
    if ed:
        out["schedule_edition"] = ed.group(1)
    i = g1055_md.find(form_title)
    if i < 0:
        return out
    row = _row_text(g1055_md, i)
    # Forms with many categories say "Varies ... See Appendix X: I-765"; the
    # amounts live in that appendix, whose heading repeats at its start.
    app = re.search(r"See (Appendix [A-Z]: " + re.escape(form_title.split(" ")[0]) + r")", g1055_md[i : i + 900])
    if app:
        heads = [m.start() for m in re.finditer(re.escape(app.group(1)), g1055_md)]
        if heads:
            j = g1055_md.find(form_title, heads[-1])
            row = _row_text(g1055_md, j if j >= 0 else heads[-1], limit=1400)
    out["excerpt"] = row
    paper = _find(r"Paper Filing:\s*" + _MONEY, row)
    online = _find(r"Online Filing:\s*" + _MONEY, row)
    if paper:
        out["paper"] = f"${paper.group(1)}"
    if online:
        out["online"] = f"${online.group(1)}"
    if not paper and not online:
        single = _find(r"General filing[^$]{0,120}" + _MONEY, row)
        if single:
            out["paper"] = f"${single.group(1)}"
    return out


def parse_biometrics(g1055_row: str) -> Optional[tuple[str, str]]:
    m = _find(r"biometric[^.|]{0,250}", g1055_row)
    if not m:
        return None
    return m.group(0)[:250], m.group(0)[:250]


def parse_where_to_file(md: str, base: str = "https://www.uscis.gov") -> Optional[str]:
    m = _find(r"\]\((/[a-z0-9\-]+-addresses)\)", md) or _find(r"\]\((/forms/all-forms/direct-filing-addresses[^)]+)\)", md)
    return base + m.group(1) if m else None


# --------------------------------------------------------------------------- cache
def _cache_path(form: str) -> Path:
    return CACHE_DIR / f"{form}.json"


def _load_cache(form: str) -> Optional[RuleSnapshot]:
    p = _cache_path(form)
    if not p.exists():
        return None
    if time.time() - p.stat().st_mtime > CACHE_TTL_S:
        return None
    return RuleSnapshot.model_validate_json(p.read_text(encoding="utf-8"))


def _save_cache(snap: RuleSnapshot) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(snap.form).write_text(snap.model_dump_json(indent=2), encoding="utf-8")


# --------------------------------------------------------------------------- public
KNOWN_DIR = Path(__file__).parent / "known"


def known_snapshot(form: str) -> Optional[RuleSnapshot]:
    """Last live snapshot committed to the repo — the offline fallback, always flagged stale."""
    p = KNOWN_DIR / f"{form}.json"
    if not p.exists():
        return None
    s = RuleSnapshot.model_validate_json(p.read_text(encoding="utf-8"))
    s.stale = True
    return s


def build_snapshot(form: str, *, use_cache: bool = True, allow_stale: bool = True) -> RuleSnapshot:
    """Live snapshot; on Tavily failure fall back to the committed known snapshot (flagged stale)."""
    form = form.lower()
    if form not in FORM_PAGES:
        raise ValueError(f"Unknown form '{form}'. Known: {sorted(FORM_PAGES)}")
    if use_cache:
        cached = _load_cache(form)
        if cached:
            return cached
    try:
        return _build_live(form)
    except Exception as e:  # noqa: BLE001
        if not allow_stale:
            raise
        known = known_snapshot(form)
        if known is None:
            raise
        known.warnings.append(f"Live lookup failed ({type(e).__name__}); showing last verified snapshot from {known.fetched_at[:10]}.")
        return known


def _build_live(form: str) -> RuleSnapshot:
    snap = RuleSnapshot(form=form, fetched_at=datetime.now(timezone.utc).isoformat())
    form_url = FORM_PAGES[form]
    pages = _extract([form_url, FEE_PAGE])
    snap.raw_sources = list(pages.keys())

    form_md = pages.get(form_url, "")
    if not form_md:
        snap.warnings.append(f"Tavily could not extract {form_url}")
    else:
        ed = parse_edition_dates(form_md)
        if ed:
            snap.edition_dates = Sourced(value=ed[0], source_url=form_url, excerpt=ed[1])
        else:
            snap.warnings.append("Edition date not found on form page")
        alert = parse_edition_alert(form_md)
        if alert:
            snap.edition_alert = Sourced(value=alert[0], source_url=form_url, excerpt=alert[1])
        cut = parse_cutover(form_md)
        if cut:
            snap.cutover_old_edition, snap.cutover_new_edition = cut["old"], cut["new"] or None
            snap.cutover_effective, snap.cutover_excerpt = cut["effective"], cut["excerpt"]
        snap.where_to_file_url = parse_where_to_file(form_md)
        if not snap.where_to_file_url:
            snap.warnings.append("Where-to-file link not found on form page")

    g1055_md = pages.get(FEE_PAGE, "")
    if not g1055_md:
        snap.warnings.append("Tavily could not extract the G-1055 fee schedule PDF")
    else:
        row = parse_fee_row(g1055_md, FORM_TITLES[form])
        snap.fee_schedule_edition = row.get("schedule_edition")
        snap.fee_table_excerpt = row.get("excerpt")
        if "paper" in row:
            snap.fee_paper = Sourced(value=row["paper"], source_url=FEE_PAGE, excerpt=row.get("excerpt", "")[:300])
        if "online" in row:
            snap.fee_online = Sourced(value=row["online"], source_url=FEE_PAGE, excerpt=row.get("excerpt", "")[:300])
        if "paper" not in row and "online" not in row:
            snap.warnings.append(f"Fee row for {FORM_TITLES[form]} not found in G-1055")
        bio = parse_biometrics(row.get("excerpt", ""))
        if bio:
            snap.biometrics_note = Sourced(value=bio[0], source_url=FEE_PAGE, excerpt=bio[1])

    snap.processing_time_url = PROC_TIME_PAGE
    _save_cache(snap)
    return snap


if __name__ == "__main__":
    import sys

    f = sys.argv[1] if len(sys.argv) > 1 else "i-765"
    snap = build_snapshot(f, use_cache=False, allow_stale="--allow-stale" in sys.argv)
    print(json.dumps(snap.model_dump(), indent=2))
    if "--save-known" in sys.argv and not snap.stale:
        KNOWN_DIR.mkdir(exist_ok=True)
        (KNOWN_DIR / f"{f}.json").write_text(snap.model_dump_json(indent=2), encoding="utf-8")
        print(f"saved packages/rules/known/{f}.json", file=sys.stderr)
