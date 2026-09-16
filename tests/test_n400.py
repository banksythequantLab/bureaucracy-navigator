import json
from pathlib import Path

import pytest

from packages.forms.fill import fill_pdf, read_back
from packages.forms.maps.n_400 import NEVER_FILL, map_answers
from packages.rules.checks import run_checks
from packages.schemas.loader import load_schema

ANSWERS = json.loads(Path("tests/fixtures/n400_answers.json").read_text())
SCHEMA = load_schema("n-400")
PDF = Path("packages/forms/pdf/n-400.pdf")


def test_map_basics():
    v = map_answers(ANSWERS)
    assert not (set(v) & NEVER_FILL)
    assert v["form1[0].#subform[0].Part1_Eligibility[2]"] == "/A"
    assert v["form1[0].#subform[0].#area[0].Line1_AlienNumber[0]"] == "098765432"
    assert v["form1[0].#subform[5].P9_Line1_Countries1[0]"] == "Vietnam"          # misnamed row-1 box
    assert v["form1[0].#subform[5].P8_Line1_Countries2[0]"] == "Vietnam, Thailand"
    assert v["form1[0].#subform[2].P4_Line1_State[0]"] == " NY"                  # leading-space quirk
    assert v["form1[0].#subform[5].P9_Line3[0]"] == "/Y"                         # overdue taxes: [0] is Yes


def test_seeded_findings():
    ids = {f.id: f.severity for f in run_checks(SCHEMA, ANSWERS)}
    assert ids["trip_over_6_months"] == "rfe"        # 228-day trip
    assert ids["taxes_no_plan"] == "rfe"
    assert ids["reduced_fee_online"] == "reject"     # reduced fee + online
    assert "filed_too_early" not in ids              # 2054 days > 1736
    assert "physical_presence_short" not in ids      # 250 < 913
    assert "trip_over_1_year" not in ids


def test_early_filing_and_presence():
    a = dict(ANSWERS, days_as_lpr=1500, total_days_outside=1000, longest_trip_days=400)
    ids = {f.id for f in run_checks(SCHEMA, a)}
    assert {"filed_too_early", "physical_presence_short", "trip_over_1_year"} <= ids


@pytest.mark.skipif(not PDF.exists(), reason="official PDF not present")
def test_fill_and_read_back(tmp_path):
    data = fill_pdf("n-400", ANSWERS, tmp_path / "n-400.filled.pdf")
    back = read_back(data)
    assert back["form1[0].#subform[0].P2_Line1_FamilyName[0]"] == "Nguyen"
    assert back["form1[0].#subform[1].P2_Line9_DateBecamePermanentResident[0]"] == "02/14/2021"
    assert back["form1[0].#subform[0].Part1_Eligibility[2]"] == "/A"
    assert not any(k in back for k in NEVER_FILL)
