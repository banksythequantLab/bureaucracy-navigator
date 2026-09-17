import json
from pathlib import Path

import pytest

from packages.forms.fill import fill_pdf, read_back
from packages.forms.maps.i_130 import NEVER_FILL, map_answers
from packages.rules.checks import run_checks
from packages.schemas.loader import load_schema

ANSWERS = json.loads(Path("tests/fixtures/i130_answers.json").read_text())
SCHEMA = load_schema("i-130")
PDF = Path("packages/forms/pdf/i-130.pdf")


def test_map_basics():
    v = map_answers(ANSWERS)
    assert not (set(v) & NEVER_FILL)
    assert v["form1[0].#subform[0].Pt1Line1_Spouse[0]"] == "/Y"
    assert v["form1[0].#subform[2].Pt2Line36_USCitizen[0]"] == "/Y"
    assert v["form1[0].#subform[1].Pt2Line10_Unit[0]"] == "/APT "   # trailing-space quirk on this block
    assert v["form1[0].#subform[4].Pt4Line11_Unit[0]"] == "/APT"
    assert v["form1[0].#subform[4].P4Line5a_FamilyName[0]"] if ANSWERS.get("beneficiary_other_names") else True
    assert v["form1[0].#subform[7].Pt4Line60a_CityOrTown[0]"] == "Bronx"


def test_seeded_findings():
    ids = {f.id: f.severity for f in run_checks(SCHEMA, ANSWERS)}
    assert ids["concurrent_online"] == "reject"
    assert ids["concurrent_wrong_lockbox"] == "reject"
    assert ids["petitioner_prior_marriage_docs"] == "rfe"
    assert "lpr_cannot_petition" not in ids and "invalid_signature" not in ids


def test_lpr_parent_denied_and_age():
    a = dict(ANSWERS, petitioner_status="lpr", relationship="parent", petitioner_age=19)
    ids = {f.id for f in run_checks(SCHEMA, a)}
    assert {"lpr_cannot_petition", "parent_petitioner_under_21"} <= ids


@pytest.mark.skipif(not PDF.exists(), reason="official PDF not present")
def test_fill_and_read_back(tmp_path):
    data = fill_pdf("i-130", ANSWERS, tmp_path / "i-130.filled.pdf")
    back = read_back(data)
    assert back["form1[0].#subform[0].Pt2Line4a_FamilyName[0]"] == "Rivera"
    assert back["form1[0].#subform[4].Pt4Line4a_FamilyName[0]"] == "Castillo Mora"
    assert back["form1[0].#subform[0].Pt1Line1_Spouse[0]"] == "/Y"
    assert back["form1[0].#subform[5].Pt4Line18_MaritalStatus[4]"] == "/M"
    assert not any(k in back for k in NEVER_FILL)
