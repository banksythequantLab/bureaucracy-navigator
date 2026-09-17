"""Interview answers → I-130 (edition 04/01/24) AcroForm field values.

Field names from `python -m packages.forms.inspect packages/forms/pdf/i-130.pdf`.
Notes:
  - The petitioner's own signature line (Part 6, 6.a) is NOT a fillable widget in
    this edition — only the interpreter (Part 7) and preparer (Part 8) signatures
    are; both are in NEVER_FILL.
  - Part 2 Item 36 uses two separate checkboxes with different on-states:
    USCitizen → "/Y", LPR → "/N".
  - Part 4 Item 18 marital status is one widget group with lettered states.
"""
from __future__ import annotations

from typing import Any

from packages.forms.maps.i_765 import _date

S = [f"form1[0].#subform[{i}]." for i in range(12)]

NEVER_FILL = {S[9] + "Pt7Line7a_Signature[0]", S[10] + "Pt8Line8a_Signature[0]"}

_REL = {"spouse": "Pt1Line1_Spouse[0]", "parent": "Pt1Line1_Parent[0]", "sibling": "Pt1Line1_Siblings[0]", "child": "Pt1Line1_Child[0]"}
_CHILD = {"in_wedlock": "Pt1Line2_InWedlock[0]", "out_of_wedlock": "Pt1Line2_OutOfWedlock[0]",
          "stepchild": "Pt1Line2_Stepchild[0]", "adopted": "Pt1Line2_AdoptedChild[0]"}
_PET_MS = {"widowed": "Widowed", "annulled": "Annulled", "separated": "Separated", "single": "Single", "married": "Married", "divorced": "Divorced"}
_BEN_MS = {"widowed": (0, "/W"), "annulled": (1, "/A"), "separated": (2, "/S"), "single": (3, "/S"), "married": (4, "/M"), "divorced": (5, "/D")}
_UNIT_STATES = {  # per-address-block on-state spelling differs in this PDF
    "Pt2Line10": {"apt": (0, "/APT "), "ste": (1, "/STE"), "flr": (2, "/FLR")},
    "Pt4Line11": {"apt": (0, "/APT"), "ste": (1, "/STE"), "flr": (2, "/FLR")},
}


def _name(prefix: str, n: dict | None) -> dict[str, str]:
    if not n:
        return {}
    return {f"{prefix}a_FamilyName[0]": n.get("family", ""), f"{prefix}b_GivenName[0]": n.get("given", ""),
            f"{prefix}c_MiddleName[0]": n.get("middle", "")}


def _address(sub: str, line: str, a: dict | None, *, in_care_of: bool = False, unit_key: str | None = None) -> dict[str, str]:
    if not a:
        return {}
    p = sub + line + "_"
    out = {
        p + "StreetNumberName[0]": a.get("street", ""),
        p + "AptSteFlrNumber[0]": a.get("unit", ""),
        p + "CityOrTown[0]": a.get("city", ""),
        p + "State[0]": a.get("state", ""),
        p + "ZipCode[0]": a.get("zip", ""),
        p + "Province[0]": a.get("province", ""),
        p + "PostalCode[0]": a.get("postal_code", ""),
        p + "Country[0]": a.get("country", ""),
    }
    if in_care_of:
        out[p + "InCareofName[0]"] = a.get("in_care_of", "")
    ut = (a.get("unit_type") or "").lower()
    states = _UNIT_STATES.get(unit_key or line)
    if states and ut in states and a.get("unit"):
        i, v = states[ut]
        out[p + f"Unit[{i}]"] = v
    return out


def map_answers(a: dict[str, Any]) -> dict[str, str]:
    f: dict[str, str] = {}

    # Part 1
    if a.get("relationship") in _REL:
        f[S[0] + _REL[a["relationship"]]] = "/Y"
    if a.get("child_relationship_type") in _CHILD:
        f[S[0] + _CHILD[a["child_relationship_type"]]] = "/Y"
    if a.get("sibling_by_adoption") is True:
        f[S[0] + "Pt1Line3_Yes[0]"] = "/Y"
    elif a.get("sibling_by_adoption") is False:
        f[S[0] + "Pt1Line3_No[0]"] = "/N"
    if a.get("status_through_adoption_or_marriage") is True:
        f[S[0] + "Pt1Line4_Yes[0]"] = "/Y"
    elif a.get("status_through_adoption_or_marriage") is False:
        f[S[0] + "Pt1Line4_No[0]"] = "/N"

    # Part 2 — petitioner
    f[S[0] + "#area[4].Pt2Line1_AlienNumber[0]"] = (a.get("petitioner_a_number") or "").lstrip("Aa")
    f[S[0] + "Pt2Line11_SSN[0]"] = a.get("petitioner_ssn") or ""
    f.update({S[0] + k: v for k, v in _name("Pt2Line4", a.get("petitioner_name")).items()})
    others = a.get("petitioner_other_names") or []
    if others:
        f.update({S[1] + k: v for k, v in _name("Pt2Line5", others[0]).items()})
    pob = a.get("petitioner_place_of_birth") or {}
    f[S[1] + "Pt2Line6_CityTownOfBirth[0]"] = pob.get("city", "")
    f[S[1] + "Pt2Line7_CountryofBirth[0]"] = pob.get("country", "")
    f[S[1] + "Pt2Line8_DateofBirth[0]"] = _date(a.get("petitioner_dob"))
    if a.get("petitioner_sex") == "male":
        f[S[1] + "Pt2Line9_Male[0]"] = "/Y"
    elif a.get("petitioner_sex") == "female":
        f[S[1] + "Pt2Line9_Female[0]"] = "/Y"
    f.update(_address(S[1], "Pt2Line10", a.get("petitioner_mailing_address"), in_care_of=True))
    same = a.get("petitioner_mailing_same_as_physical")
    if same is True:
        f[S[1] + "Pt2Line11_Yes[0]"] = "/Y"
    elif same is False:
        f[S[1] + "Pt2Line11_No[0]"] = "/N"
    if a.get("petitioner_marriages") is not None:
        f[S[1] + "Pt2Line16_NumberofMarriages[0]"] = str(a["petitioner_marriages"])
    if a.get("petitioner_marital_status") in _PET_MS:
        f[S[1] + f"Pt2Line17_{_PET_MS[a['petitioner_marital_status']]}[0]"] = "/Y"
    f[S[2] + "Pt2Line18_DateOfMarriage[0]"] = _date(a.get("marriage_date"))
    if a.get("petitioner_status") == "usc":
        f[S[2] + "Pt2Line36_USCitizen[0]"] = "/Y"
    elif a.get("petitioner_status") == "lpr":
        f[S[2] + "Pt2Line36_LPR[0]"] = "/N"
    nc = a.get("naturalization_certificate")
    if nc is True:
        f[S[2] + "Pt2Line36_Yes[0]"] = "/Y"
        c = a.get("certificate") or {}
        f[S[2] + "Pt2Line37a_CertificateNumber[0]"] = c.get("number", "")
        f[S[2] + "Pt2Line37b_PlaceOfIssuance[0]"] = c.get("place", "")
        f[S[2] + "Pt2Line37c_DateOfIssuance[0]"] = _date(c.get("date"))
    elif nc is False:
        f[S[2] + "Pt2Line36_No[0]"] = "/N"

    # Part 4 — beneficiary
    f[S[4] + "#area[6].Pt4Line1_AlienNumber[0]"] = (a.get("beneficiary_a_number") or "").lstrip("Aa")
    f.update({S[4] + k: v for k, v in _name("Pt4Line4", a.get("beneficiary_name")).items()})
    bo = a.get("beneficiary_other_names") or []
    if bo:
        f[S[4] + "P4Line5a_FamilyName[0]"] = bo[0].get("family", "")  # sic: "P4" not "Pt4" in this edition
        f[S[4] + "Pt4Line5b_GivenName[0]"] = bo[0].get("given", "")
        f[S[4] + "Pt4Line5c_MiddleName[0]"] = bo[0].get("middle", "")
    bpob = a.get("beneficiary_place_of_birth") or {}
    f[S[4] + "Pt4Line7_CityTownOfBirth[0]"] = bpob.get("city", "")
    f[S[4] + "Pt4Line8_CountryOfBirth[0]"] = bpob.get("country", "")
    f[S[4] + "Pt4Line9_DateOfBirth[0]"] = _date(a.get("beneficiary_dob"))
    if a.get("beneficiary_sex") == "male":
        f[S[4] + "Pt4Line9_Male[0]"] = "/Y"
    elif a.get("beneficiary_sex") == "female":
        f[S[4] + "Pt4Line9_Female[0]"] = "/Y"
    pp = {"yes": ("Yes", "/Y"), "no": ("No", "/N"), "unknown": ("Unknown", "/U")}.get(a.get("prior_petition_for_beneficiary") or "")
    if pp:
        f[S[4] + f"Pt4Line10_{pp[0]}[0]"] = pp[1]
    f.update(_address(S[4], "Pt4Line11", a.get("beneficiary_physical_address")))
    f[S[4] + "Pt4Line14_DaytimePhoneNumber[0]"] = a.get("beneficiary_daytime_phone") or ""
    f[S[5] + "Pt4Line16_EmailAddress[0]"] = a.get("beneficiary_email") or ""
    if a.get("beneficiary_marriages") is not None:
        f[S[5] + "Pt4Line17_NumberofMarriages[0]"] = str(a["beneficiary_marriages"])
    if a.get("relationship") == "spouse":
        f[S[5] + "Pt4Line18_MaritalStatus[4]"] = "/M"
        f[S[5] + "Pt4Line19_DateOfMarriage[0]"] = _date(a.get("marriage_date"))
    if a.get("concurrent_i485") is True:
        addr = a.get("beneficiary_physical_address") or {}
        f[S[7] + "Pt4Line60a_CityOrTown[0]"] = addr.get("city", "")
        f[S[7] + "Pt4Line60b_State[0]"] = addr.get("state", "")
    cp = a.get("consular_post") or {}
    if cp:
        f[S[7] + "Pt4Line61a_CityOrTown[0]"] = cp.get("city", "")
        f[S[7] + "Pt4Line61b_Province[0]"] = cp.get("state", "")
        f[S[7] + "Pt4Line61c_Country[0]"] = cp.get("country", "")

    # Part 6 — petitioner statement/contact
    if a.get("read_language") == "english":
        f[S[8] + "Pt6Line1Checkbox[0]"] = "/A"
    elif a.get("read_language") == "interpreter":
        f[S[8] + "Pt6Line1Checkbox[1]"] = "/B"
        f[S[8] + "Pt6Line1b_Language[0]"] = a.get("interpreter_language") or ""
    f[S[8] + "Pt6Line3_DaytimePhoneNumber[0]"] = a.get("daytime_phone") or ""
    f[S[8] + "Pt6Line4_MobileNumber[0]"] = a.get("mobile_phone") or ""
    f[S[8] + "Pt6Line5_Email[0]"] = a.get("email") or ""
    f[S[8] + "Pt6Line6b_DateofSignature[0]"] = _date(a.get("signature_date"))

    assert not (set(f) & NEVER_FILL), "refusing to fill a signature field"
    return {k: v for k, v in f.items() if v != ""}
