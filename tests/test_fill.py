"""Fill the official I-765 PDF and read the values back."""
import json
from pathlib import Path

import pytest

from packages.forms.fill import fill_pdf, read_back
from packages.forms.maps.i_765 import NEVER_FILL, map_answers

ANSWERS = json.loads(Path("tests/fixtures/i765_answers.json").read_text())
PDF = Path("packages/forms/pdf/i-765.pdf")


def test_map_never_touches_signature():
    vals = map_answers(ANSWERS)
    assert not (set(vals) & NEVER_FILL)
    assert vals["form1[0].Page3[0].#area[1].section_1[0]"] == "(c)("
    assert vals["form1[0].Page3[0].#area[1].section_2[0]"] == "8)"
    assert vals["form1[0].Page1[0].Part1_Checkbox[2]"] == "/3"  # renewal
    assert vals["form1[0].Page2[0].Pt2Line5_Unit[2]"] == "/ APT "
    assert vals["form1[0].Page3[0].Line19_DOB[0]"] == "04/17/1991"


@pytest.mark.skipif(not PDF.exists(), reason="official PDF not present (download on Vesper)")
def test_fill_and_read_back(tmp_path):
    out = tmp_path / "i-765.filled.pdf"
    data = fill_pdf("i-765", ANSWERS, out)
    assert out.exists() and len(data) > 100_000
    back = read_back(data)
    assert back["form1[0].Page1[0].Line1a_FamilyName[0]"] == "Perez Gomez"
    assert back["form1[0].Page2[0].Pt2Line5_State[0]"] == "NY"
    assert back["form1[0].Page2[0].Line10_Checkbox[3]"] == "/Married"
    assert back["form1[0].Page3[0].#area[1].section_2[0]"] == "8)"
    assert "form1[0].Page4[0].Pt3Line7a_Signature[0]" not in back
