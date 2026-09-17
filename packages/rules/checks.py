"""Deterministic adjudicator core.

Runs BEFORE any model call so hard rejects are never hallucinated:
  1. schema risks   — each field's `risks[].when` expression evaluated over answers
  2. required fields — `required` / `required_when`
  3. rule-snapshot   — fee paid vs live G-1055, PDF edition vs live edition list

`when` expressions are Python expressions authored in our own YAML (trusted),
evaluated with no builtins over an answers namespace where missing keys read as
None and dict answers support attribute access (full_name.family).
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from packages.rules.snapshot import RuleSnapshot
from packages.schemas.loader import FormSchema

SEVERITY_ORDER = {"deny": 0, "reject": 1, "rfe": 2, "info": 3}


class Finding(BaseModel):
    id: str
    severity: str  # deny | reject | rfe | info
    field: str | None = None
    text_en: str
    text_es: str | None = None
    cite: list[str] = []
    source: str = "schema"  # schema | required | snapshot


class _Attr(dict):
    """dict with attribute access; missing → None."""

    def __getattr__(self, k: str) -> Any:
        v = self.get(k)
        return _wrap(v)

    def __missing__(self, k: str) -> Any:  # noqa: D401
        return None


def _wrap(v: Any) -> Any:
    if isinstance(v, dict) and not isinstance(v, _Attr):
        return _Attr(v)
    return v


class _NS(dict):
    def __missing__(self, k: str) -> Any:
        return None

    def __getitem__(self, k: str) -> Any:
        return _wrap(super().__getitem__(k))


def evaluate(expr: str, answers: dict[str, Any]) -> bool:
    try:
        return bool(eval(expr, {"__builtins__": {}}, _NS(answers)))  # noqa: S307 - trusted schema text
    except Exception:  # noqa: BLE001 - a broken expression must never crash a check run
        return False


def _is_blank(v: Any) -> bool:
    return v is None or v == "" or v == [] or v == {}


def run_checks(schema: FormSchema, answers: dict[str, Any], snapshot: RuleSnapshot | None = None) -> list[Finding]:
    out: list[Finding] = []

    for field in schema.all_fields():
        # required / required_when
        needed = field.required if field.required_when is None else evaluate(field.required_when, answers)
        if needed and _is_blank(answers.get(field.id)):
            out.append(Finding(
                id=f"required.{field.id}", severity="reject", field=field.id, source="required",
                text_en=f"Required item is blank: {field.label_en}",
                text_es=f"Falta un dato obligatorio: {field.label_es or field.label_en}",
            ))
        for r in field.risks:
            if evaluate(r.when, answers):
                out.append(Finding(id=r.id, severity=r.severity, field=field.id, text_en=r.text_en,
                                   text_es=r.text_es, cite=field.cite, source="schema"))

    if snapshot is not None:
        out.extend(snapshot_checks(schema, answers, snapshot))

    out.sort(key=lambda f: (SEVERITY_ORDER.get(f.severity, 9), f.id))
    return out


def snapshot_checks(schema: FormSchema, answers: dict[str, Any], snap: RuleSnapshot, today: "date | None" = None) -> list[Finding]:
    from datetime import date as _date

    today = today or _date.today()
    out: list[Finding] = []
    # No-grace-period cutover: after the effective date the old edition is rejected outright,
    # and before it the NEW edition is rejected — both are hard rejects, not heads-ups.
    if snap.cutover_effective and schema.pdf_edition:
        eff = _date.fromisoformat(snap.cutover_effective)
        if today >= eff and schema.pdf_edition == snap.cutover_old_edition:
            out.append(Finding(
                id="edition.cutover", severity="reject", source="snapshot",
                text_en=(f"USCIS rejects the {snap.cutover_old_edition} edition if postmarked on or after {eff:%b %d, %Y} "
                         f"(no grace period); only the {snap.cutover_new_edition or 'new'} edition is accepted now."),
                text_es=(f"USCIS rechaza la edición {snap.cutover_old_edition} si el matasellos es del {eff:%d/%m/%Y} o posterior "
                         f"(sin periodo de gracia); ahora solo se acepta la edición {snap.cutover_new_edition or 'nueva'}."),
                cite=[snap.edition_alert.source_url or ""],
            ))
        elif today < eff and snap.cutover_new_edition and schema.pdf_edition == snap.cutover_new_edition:
            out.append(Finding(
                id="edition.too_early", severity="reject", source="snapshot",
                text_en=f"The {snap.cutover_new_edition} edition is rejected if postmarked before {eff:%b %d, %Y}; use {snap.cutover_old_edition} until then.",
                text_es=f"La edición {snap.cutover_new_edition} se rechaza si el matasellos es anterior al {eff:%d/%m/%Y}; use la {snap.cutover_old_edition} hasta entonces.",
                cite=[snap.edition_alert.source_url or ""],
            ))
    # Edition drift: the PDF we fill vs what uscis.gov accepts today
    if schema.pdf_edition and snap.edition_dates.value and not snap.cutover_effective:
        accepted = [d.strip() for d in snap.edition_dates.value.split(",")]
        if schema.pdf_edition not in accepted:
            out.append(Finding(
                id="edition.stale", severity="reject", source="snapshot",
                text_en=(f"This packet uses edition {schema.pdf_edition}; uscis.gov currently accepts "
                         f"{snap.edition_dates.value} (checked {snap.fetched_at[:10]})."),
                text_es=(f"Este paquete usa la edición {schema.pdf_edition}; uscis.gov acepta actualmente "
                         f"{snap.edition_dates.value} (verificado {snap.fetched_at[:10]})."),
                cite=[snap.edition_dates.source_url or ""],
            ))
        if snap.edition_alert.value and snap.edition_alert.value not in accepted:
            out.append(Finding(
                id="edition.upcoming", severity="info", source="snapshot",
                text_en=(f"USCIS announced a new edition dated {snap.edition_alert.value}. "
                         "Check the form page before mailing; old editions are usually accepted for a grace period."),
                text_es=(f"USCIS anunció una nueva edición con fecha {snap.edition_alert.value}. "
                         "Revise la página del formulario antes de enviar; las ediciones anteriores suelen aceptarse por un periodo de gracia."),
                cite=[snap.edition_alert.source_url or ""],
            ))
    # Fee paid vs live schedule (general-filing row only; category exceptions are schema risks)
    paid = answers.get("fee_paid")
    online = answers.get("filing_online")
    expected = snap.fee_online.value if online else snap.fee_paper.value
    if paid and expected and _money(paid) != _money(expected) and not answers.get("fee_exception"):
        out.append(Finding(
            id="fee.mismatch", severity="reject", source="snapshot",
            text_en=(f"Fee entered {paid} but the current G-1055 (ed. {snap.fee_schedule_edition}) lists "
                     f"{expected} for {'online' if online else 'paper'} filing. Wrong fee = rejection at intake."),
            text_es=(f"Indicó una tarifa de {paid}, pero el G-1055 vigente (ed. {snap.fee_schedule_edition}) establece "
                     f"{expected} para la presentación {'en línea' if online else 'en papel'}. Tarifa incorrecta = rechazo al recibirlo."),
            cite=[snap.fee_paper.source_url or ""],
        ))
    return out


def _money(s: Any) -> float | None:
    try:
        return float(str(s).replace("$", "").replace(",", ""))
    except ValueError:
        return None
