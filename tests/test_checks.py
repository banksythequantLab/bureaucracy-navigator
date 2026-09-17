import json
from pathlib import Path

from packages.rules.checks import evaluate, run_checks
from packages.rules.snapshot import RuleSnapshot, Sourced
from packages.schemas.loader import load_schema

ANSWERS = json.loads(Path("tests/fixtures/i765_answers.json").read_text())
SCHEMA = load_schema("i-765")


def snap(edition="09/15/26", alert=None, paper="$520", online="$470"):
    return RuleSnapshot(
        form="i-765", fetched_at="2026-09-16T00:00:00+00:00",
        edition_dates=Sourced(value=edition, source_url="https://www.uscis.gov/i-765"),
        edition_alert=Sourced(value=alert, source_url="https://www.uscis.gov/i-765"),
        fee_schedule_edition="09/09/26",
        fee_paper=Sourced(value=paper, source_url="g1055"), fee_online=Sourced(value=online, source_url="g1055"),
    )


def test_evaluate_missing_is_none_and_attr_access():
    assert evaluate("not a_number", {}) is True
    assert evaluate("full_name.family == 'X'", {"full_name": {"family": "X"}}) is True
    assert evaluate("full_name.family == 'X'", {}) is False
    assert evaluate("this is not python", {}) is False


def test_seeded_bad_packet_findings():
    ids = {f.id: f for f in run_checks(SCHEMA, ANSWERS, snap())}
    assert ids["invalid_signature"].severity == "deny"        # typed signature
    assert ids["pl119_21_fee_combined"].severity == "reject"  # (c)(8) fee not separate
    assert "edition.stale" not in ids and "edition.upcoming" not in ids
    ids2 = {f.id: f for f in run_checks(SCHEMA, ANSWERS, snap(edition="09/15/26", alert="10/01/26"))}
    assert ids2["edition.upcoming"].severity == "info"
    assert "renewal_window" not in ids                         # 40 days < 180
    assert "fee.mismatch" not in ids                           # $520 paper matches


def test_clean_packet_has_no_hard_findings():
    a = dict(ANSWERS, signature_type="wet_ink", pl119_21_fee_paid_separately=True)
    hard = [f for f in run_checks(SCHEMA, a, snap()) if f.severity in ("deny", "reject")]
    assert hard == []


def test_snapshot_edition_and_fee_drift():
    a = dict(ANSWERS, fee_paid="$410")
    ids = {f.id for f in run_checks(SCHEMA, a, snap(edition="08/21/25"))}
    assert {"edition.stale", "fee.mismatch"} <= ids


def test_required_when():
    a = dict(ANSWERS, mailing_same_as_physical=False, physical_address=None)
    ids = {f.id for f in run_checks(SCHEMA, a)}
    assert "required.physical_address" in ids


def test_cutover_hard_reject_after_effective_date():
    from datetime import date

    from packages.rules.checks import snapshot_checks

    sn = snap(edition="08/21/25", alert="09/15/26")
    sn.cutover_old_edition, sn.cutover_new_edition, sn.cutover_effective = "08/21/25", "09/15/26", "2026-09-15"
    old = load_schema("i-765").model_copy(update={"pdf_edition": "08/21/25"})
    ids = {f.id: f.severity for f in snapshot_checks(old, ANSWERS, sn, today=date(2026, 9, 17))}
    assert ids.get("edition.cutover") == "reject" and "edition.stale" not in ids
    new = load_schema("i-765")  # now 09/15/26
    assert "edition.cutover" not in {f.id for f in snapshot_checks(new, ANSWERS, sn, today=date(2026, 9, 17))}
    assert {f.id for f in snapshot_checks(new, ANSWERS, sn, today=date(2026, 9, 1))} >= {"edition.too_early"}
