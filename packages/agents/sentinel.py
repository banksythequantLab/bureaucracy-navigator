"""Deadline Sentinel — the "after you file" half of the product.

A Case is a small opt-in record: which form, when filed, and the handful of
dates that start clocks. Deadlines are computed deterministically from rules
below (each with its authority); the runner emails whichever ones fall inside
their warning window. Nemotron, when a key exists, only rephrases the nudge in
the user's language — it never decides dates.

Storage: JSON files under BN_CASE_DIR (default .cache/cases). Delete-anytime.
Email: SMTP via env (SMTP_HOST/PORT/USER/PASS/FROM); without it the runner
prints what it would send — good enough for the demo and for tests.
"""
from __future__ import annotations

import json
import os
import smtplib
import uuid
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from packages.agents import nebius
from packages.rules.timeline import predict

CASE_DIR = Path(os.getenv("BN_CASE_DIR", ".cache/cases"))
Lang = Literal["en", "es"]


class Case(BaseModel):
    id: str
    form: str
    lang: Lang = "en"
    email: Optional[str] = None
    filed_on: Optional[str] = None            # YYYY-MM-DD
    receipt_number: Optional[str] = None
    ead_expires: Optional[str] = None         # I-765 renewals
    i94_expires: Optional[str] = None
    rfe_received_on: Optional[str] = None
    rfe_due_on: Optional[str] = None
    lpr_since: Optional[str] = None           # N-400 90-day window
    basis: Optional[str] = None               # N-400: general_5yr | spouse_3yr
    priority_date: Optional[str] = None       # I-130 preference categories
    answers: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    notified: dict[str, str] = Field(default_factory=dict)  # deadline id → ISO date last notified

    def save(self) -> None:
        CASE_DIR.mkdir(parents=True, exist_ok=True)
        (CASE_DIR / f"{self.id}.json").write_text(self.model_dump_json(indent=2), encoding="utf-8")

    @classmethod
    def load(cls, cid: str) -> "Case":
        p = CASE_DIR / f"{cid}.json"
        if not p.exists():
            raise KeyError(cid)
        return cls.model_validate_json(p.read_text(encoding="utf-8"))

    @classmethod
    def all(cls) -> list["Case"]:
        if not CASE_DIR.exists():
            return []
        return [cls.model_validate_json(p.read_text(encoding="utf-8")) for p in sorted(CASE_DIR.glob("*.json"))]

    def delete(self) -> None:
        p = CASE_DIR / f"{self.id}.json"
        if p.exists():
            p.unlink()


class Deadline(BaseModel):
    id: str
    due: str
    days_left: int
    urgency: Literal["overdue", "now", "soon", "later"]
    title_en: str
    title_es: str
    action_en: str
    action_es: str
    cite: list[str] = Field(default_factory=list)
    warn_days: int = 30


def _d(s: Optional[str]) -> Optional[date]:
    return date.fromisoformat(s) if s else None


def _urgency(days_left: int, warn: int) -> str:
    if days_left < 0:
        return "overdue"
    if days_left <= 7:
        return "now"
    if days_left <= warn:
        return "soon"
    return "later"


def _mk(id_: str, due: date, today: date, warn: int, title_en: str, title_es: str,
        action_en: str, action_es: str, cite: list[str]) -> Deadline:
    dl = (due - today).days
    return Deadline(id=id_, due=due.isoformat(), days_left=dl, urgency=_urgency(dl, warn), warn_days=warn,
                    title_en=title_en, title_es=title_es, action_en=action_en, action_es=action_es, cite=cite)


def compute_deadlines(c: Case, today: date | None = None) -> list[Deadline]:
    today = today or date.today()
    out: list[Deadline] = []

    if c.rfe_due_on:
        out.append(_mk("rfe_response", _d(c.rfe_due_on), today, 30,
                       "RFE response due", "Vence la respuesta al RFE",
                       "Mail the complete response so it ARRIVES by this date; USCIS denies on the record if nothing is received.",
                       "Envíe la respuesta completa para que LLEGUE antes de esta fecha; USCIS deniega con el expediente si no recibe nada.",
                       ["8 CFR 103.2(b)(8)(iv)", "8 CFR 103.2(b)(13)"]))
    elif c.rfe_received_on:
        out.append(_mk("rfe_response", _d(c.rfe_received_on) + timedelta(days=87), today, 30,
                       "RFE response due (87-day default)", "Vence la respuesta al RFE (87 días por defecto)",
                       "Check the notice for the exact date; most RFEs allow 87 days from the notice date.",
                       "Revise el aviso para la fecha exacta; la mayoría de los RFE dan 87 días desde la fecha del aviso.",
                       ["8 CFR 103.2(b)(8)(iv)"]))

    if c.ead_expires:
        exp = _d(c.ead_expires)
        out.append(_mk("ead_renewal_window_opens", exp - timedelta(days=180), today, 14,
                       "EAD renewal window opens (180 days before expiry)", "Se abre la ventana de renovación del EAD (180 días antes del vencimiento)",
                       "File the renewal I-765 as early as this date to keep the 540-day automatic extension available.",
                       "Presente la renovación del I-765 desde esta fecha para conservar la extensión automática de 540 días.",
                       ["8 CFR 274a.13(d)"]))
        out.append(_mk("ead_expires", exp, today, 60,
                       "Work permit expires", "Vence el permiso de trabajo",
                       "If the renewal was filed before this date and the category qualifies, work authorization auto-extends up to 540 days; keep the receipt notice with the old card.",
                       "Si la renovación se presentó antes de esta fecha y la categoría califica, la autorización se extiende automáticamente hasta 540 días; conserve el aviso de recibo con la tarjeta anterior.",
                       ["8 CFR 274a.13(d)(1)"]))

    if c.i94_expires:
        out.append(_mk("i94_expires", _d(c.i94_expires), today, 60,
                       "Authorized stay (I-94) ends", "Termina la estadía autorizada (I-94)",
                       "Overstaying starts unlawful presence; file an extension or change of status before this date if you need one.",
                       "Quedarse más tiempo inicia la presencia ilegal; presente una extensión o cambio de estatus antes de esta fecha si lo necesita.",
                       ["INA 212(a)(9)(B)"]))

    if c.form == "n-400" and c.lpr_since:
        years = 3 if c.basis == "spouse_3yr" else 5
        anniv = _d(c.lpr_since).replace(year=_d(c.lpr_since).year + years)
        out.append(_mk("n400_early_filing_window", anniv - timedelta(days=90), today, 14,
                       f"N-400 early-filing window opens (90 days before the {years}-year mark)",
                       f"Se abre la ventana de presentación anticipada del N-400 (90 días antes de los {years} años)",
                       "You may file on or after this date; filing even one day earlier is denied and the fee is lost.",
                       "Puede presentar a partir de esta fecha; presentar aunque sea un día antes se deniega y la tarifa se pierde.",
                       ["INA 334(a)", "8 CFR 334.2(b)"]))

    if c.filed_on:
        t = predict(c.form, c.answers, c.filed_on)
        if t.inquiry_after:
            out.append(_mk("outside_normal_processing", _d(t.inquiry_after), today, 30,
                           "Case outside normal processing time", "Caso fuera del tiempo normal de procesamiento",
                           f"After this date you can submit a case inquiry (posted range {t.min_months}-{t.max_months} months as of {t.as_of}).",
                           f"Después de esta fecha puede presentar una consulta de caso (rango publicado {t.min_months}-{t.max_months} meses al {t.as_of}).",
                           [t.source]))

    if c.form == "i-130" and c.priority_date:
        out.append(_mk("visa_bulletin_check", _first_of_next_month(today), today, 7,
                       "Monthly Visa Bulletin check", "Revisión mensual del Boletín de Visas",
                       f"Compare your priority date {c.priority_date} with the Final Action chart for your category; when it is current, the NVC or USCIS can move the case.",
                       f"Compare su fecha de prioridad {c.priority_date} con la tabla de Acción Final de su categoría; cuando esté vigente, el NVC o USCIS puede avanzar el caso.",
                       ["INA 203(a)", "travel.state.gov Visa Bulletin"]))

    out.sort(key=lambda d: d.due)
    return out


def _first_of_next_month(d: date) -> date:
    return (d.replace(day=1) + timedelta(days=32)).replace(day=1)


# ------------------------------------------------------------------ notifications
def due_now(c: Case, today: date | None = None) -> list[Deadline]:
    """Deadlines inside their warning window that have not been notified in the last 7 days."""
    today = today or date.today()
    out = []
    for d in compute_deadlines(c, today):
        if d.urgency in ("now", "soon", "overdue"):
            last = c.notified.get(d.id)
            if not last or (today - date.fromisoformat(last)).days >= 7:
                out.append(d)
    return out


def render_nudge(c: Case, deadlines: list[Deadline]) -> tuple[str, str]:
    """(subject, body). Plain deterministic text; Nemotron may rephrase when configured."""
    es = c.lang == "es"
    subject = ("Bureaucracy Navigator: " + (f"{len(deadlines)} fecha(s) próximas" if es else f"{len(deadlines)} upcoming deadline(s)"))
    lines = []
    for d in deadlines:
        title = d.title_es if es else d.title_en
        action = d.action_es if es else d.action_en
        when = (f"vence {d.due} ({d.days_left} días)" if es else f"due {d.due} ({d.days_left} days)")
        lines.append(f"• {title} — {when}\n  {action}\n  {' · '.join(d.cite)}")
    body = "\n\n".join(lines)
    body += "\n\n" + ("Esta herramienta explica y revisa formularios. No es asesoría legal." if es
                       else "This tool explains and checks forms. It is not legal advice.")
    if os.getenv("NEBIUS_API_KEY"):
        try:
            system = ("Rewrite this deadline notice as a short, warm, plain-language email in the same language. "
                      "Keep every date, number, and citation exactly. Do not add advice or predictions.")
            body = nebius.chat(system, body, model=nebius.FAST_MODEL) or body
        except Exception:  # noqa: BLE001
            pass
    return subject, body


def send_email(to: str, subject: str, body: str) -> bool:
    host = os.getenv("SMTP_HOST")
    if not host or not to:
        return False
    msg = EmailMessage()
    msg["From"] = os.getenv("SMTP_FROM", os.getenv("SMTP_USER", "navigator@localhost"))
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "587"))) as s:
        s.starttls()
        if os.getenv("SMTP_USER"):
            s.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASS", ""))
        s.send_message(msg)
    return True


def run_once(today: date | None = None, *, dry_run: bool = False) -> list[dict[str, Any]]:
    """Cron entry point: python -m packages.agents.sentinel"""
    today = today or date.today()
    report = []
    for c in Case.all():
        dl = due_now(c, today)
        if not dl:
            continue
        subject, body = render_nudge(c, dl)
        sent = False if dry_run else send_email(c.email or "", subject, body)
        if not dry_run:
            for d in dl:
                c.notified[d.id] = today.isoformat()
            c.save()
        report.append({"case": c.id, "to": c.email, "sent": sent, "subject": subject, "deadlines": [d.id for d in dl], "body": body})
    return report


def new_case(form: str, lang: Lang = "en", **fields: Any) -> Case:
    c = Case(id=uuid.uuid4().hex[:10], form=form, lang=lang, created_at=datetime.now(timezone.utc).isoformat(), **fields)
    c.save()
    return c


if __name__ == "__main__":
    import sys

    dry = "--dry-run" in sys.argv
    for r in run_once(dry_run=dry):
        print(json.dumps({k: v for k, v in r.items() if k != "body"}), "\n", r["body"], "\n")
