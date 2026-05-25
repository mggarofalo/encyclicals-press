"""Regression tests for :mod:`encyclicals_press.parse` against the Spe Salvi fixture."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from encyclicals_press.parse import parse
from encyclicals_press.schema import Encyclical

FIXTURE = Path(__file__).parent / "fixtures" / "spe-salvi.html"


@pytest.fixture(scope="module")
def spe_salvi() -> Encyclical:
    return parse(FIXTURE.read_text(encoding="utf-8"), slug="spe-salvi")


def test_metadata(spe_salvi: Encyclical) -> None:
    assert spe_salvi.slug == "spe-salvi"
    assert spe_salvi.title == "Spe Salvi"
    assert spe_salvi.subtitle == "On Christian Hope"
    assert spe_salvi.pope == "Benedict XVI"
    assert spe_salvi.promulgated == date(2007, 11, 30)
    assert "Spe Salvi" in spe_salvi.incipit
    assert spe_salvi.source_url.endswith("hf_ben-xvi_enc_20071130_spe-salvi.html")


def test_salutation(spe_salvi: Encyclical) -> None:
    # The salutation should mention the four addressee groups, joined into one
    # rubric line for the renderer.
    salutation = spe_salvi.salutation.lower()
    assert "bishops" in salutation
    assert "priests and deacons" in salutation
    assert "men and women religious" in salutation
    assert "lay faithful" in salutation


def test_numbered_paragraph_count(spe_salvi: Encyclical) -> None:
    numbered = [p for p in spe_salvi.paragraphs if p.number is not None]
    numbers = [p.number for p in numbered]
    assert numbers == list(range(1, 51)), "Spe Salvi has 50 numbered paragraphs, 1..50"


def test_footnote_count(spe_salvi: Encyclical) -> None:
    numbers = [f.number for f in spe_salvi.footnotes]
    assert numbers == list(range(1, 41)), "Spe Salvi has 40 footnotes, 1..40"


def test_paragraph_one_spot_check(spe_salvi: Encyclical) -> None:
    p1 = next(p for p in spe_salvi.paragraphs if p.number == 1)
    # Section context is the opening 'Faith is Hope' (or whatever heading sits
    # immediately before paragraph 1 in source order).
    assert p1.section is not None
    # The incipit appears at the start of paragraph 1, in italics.
    assert "*SPE SALVI facti sumus*" in p1.text
    # Paul's letter to the Romans is cited inline as a scripture link.
    assert "Rom" in p1.text and "8:24" in p1.text
    # And the paragraph number itself should already be stripped from the body.
    assert not p1.text.startswith("1.")


def test_footnote_one_spot_check(spe_salvi: Encyclical) -> None:
    f1 = next(f for f in spe_salvi.footnotes if f.number == 1)
    assert "Corpus Inscriptionum Latinarum" in f1.text
    assert "26003" in f1.text


def test_sections_detected(spe_salvi: Encyclical) -> None:
    sections = {p.section for p in spe_salvi.paragraphs if p.section}
    # The signature SCOTUS-style chapter dividers — Roman numerals in the
    # closing third of the encyclical — must survive parsing as sections.
    assert "I. Prayer as a school of hope" in sections
    assert "II. Action and suffering as settings for learning hope" in sections
    assert "III. Judgement as a setting for learning and practising hope" in sections


def test_closing_dateline_present(spe_salvi: Encyclical) -> None:
    closing = [p for p in spe_salvi.paragraphs if p.number is None]
    dateline = next((p for p in closing if "Given in Rome" in p.text), None)
    assert dateline is not None, "closing dateline must be preserved as an unnumbered paragraph"
    # Signature lands as a separate paragraph rather than being concatenated.
    signature = next((p for p in closing if "BENEDICTUS PP" in p.text), None)
    assert signature is not None, "papal signature must be preserved as its own paragraph"


def test_footnote_refs_collapsed_to_markdown_syntax(spe_salvi: Encyclical) -> None:
    # No leftover [<a href="#_ftn1">[1]</a>] artifacts in body text.
    for p in spe_salvi.paragraphs:
        assert "#_ftn" not in p.text, f"bare anchor leaked into paragraph: {p.text[:80]}"
    # Body refs should appear as Pandoc-style footnote markers.
    bodies_with_refs = [p for p in spe_salvi.paragraphs if "[^" in p.text]
    assert bodies_with_refs, "expected at least one paragraph to carry a footnote ref"
