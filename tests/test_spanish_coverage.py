"""Every field and risk in every schema must have Spanish label/why/text — the app promises EN/ES parity."""
import pytest

from packages.schemas.loader import available_forms, load_schema


@pytest.mark.parametrize("form", available_forms())
def test_full_spanish_coverage(form):
    s = load_schema(form)
    assert s.title_es
    missing = []
    for sec in s.sections:
        if not sec.title_es:
            missing.append(f"section:{sec.id}")
        for f in sec.fields:
            if not f.label_es:
                missing.append(f"label:{f.id}")
            if f.why_en and not f.why_es:
                missing.append(f"why:{f.id}")
            for r in f.risks:
                if not r.text_es:
                    missing.append(f"risk:{r.id}")
    assert missing == [], missing
