"""Unit tests for individual heuristics in :mod:`encyclicals_press.parse.heuristics`.

These lock in the resilience fixes that the wider corpus (Francis, Leo XIV)
forced into the parser. Each test names the source document that motivated
the behavior so future regressions are easy to track down.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from selectolax.lexbor import LexborHTMLParser

from encyclicals_press.parse import _extract_incipit, _parse_footnotes
from encyclicals_press.parse.heuristics import (
    PARAGRAPH_NUMBER_RE,
    extract_paragraph_number,
    find_title_paragraph,
    is_heading,
    node_to_markdown,
    parse_dateline_date,
    parse_title_lines,
    split_body_and_footnotes,
    title_case,
)
from encyclicals_press.schema import Paragraph

FIXTURES = Path(__file__).parent / "fixtures"


# ============================================================================
# parse_title_lines — rubric-line variants across pontificates
# ============================================================================


def test_parse_title_lines_skips_benedict_rubric() -> None:
    """Benedict and Leo use ``OF HIS HOLINESS`` between title and pope."""
    out = parse_title_lines(
        [
            "ENCYCLICAL LETTER",
            "DEUS CARITAS EST",
            "OF THE SUPREME PONTIFF",
            "BENEDICT XVI",
            "ON CHRISTIAN LOVE",
        ]
    )
    assert out.title == "Deus Caritas Est"
    assert out.pope == "Benedict XVI"
    assert out.subtitle == "On Christian Love"


def test_parse_title_lines_skips_francis_rubric() -> None:
    """Francis-era documents use ``OF THE HOLY FATHER`` — different phrase."""
    out = parse_title_lines(
        [
            "ENCYCLICAL LETTER",
            "FRATELLI TUTTI",
            "OF THE HOLY FATHER",
            "FRANCIS",
            "ON FRATERNITY AND SOCIAL FRIENDSHIP",
        ]
    )
    assert out.pope == "Francis", "pope must not capture the 'HOLY FATHER' rubric line"
    assert out.title == "Fratelli Tutti"
    assert out.subtitle == "On Fraternity and Social Friendship"


def test_parse_title_lines_strips_pope_prefix() -> None:
    """Leo XIV's title block writes ``POPE LEO XIV`` — strip the prefix."""
    out = parse_title_lines(
        [
            "ENCYCLICAL LETTER",
            "MAGNIFICA HUMANITAS",
            "OF HIS HOLINESS",
            "POPE LEO XIV",
            "ON SAFEGUARDING THE HUMAN PERSON",
            "IN THE TIME OF ARTIFICIAL INTELLIGENCE",
        ]
    )
    assert out.pope == "Leo XIV"
    assert out.subtitle == "On Safeguarding the Human Person in the Time of Artificial Intelligence"
    assert out.salutation == ""


def test_parse_title_lines_distinguishes_salutation_from_subtitle() -> None:
    """A line opening with ``TO`` marks a salutation block."""
    out = parse_title_lines(
        [
            "ENCYCLICAL LETTER",
            "SPE SALVI",
            "OF THE SUPREME PONTIFF",
            "BENEDICT XVI",
            "TO THE BISHOPS",
            "PRIESTS AND DEACONS",
            "ON CHRISTIAN HOPE",
        ]
    )
    assert out.salutation == "To the Bishops, Priests and Deacons"
    assert out.subtitle == "On Christian Hope"


# ============================================================================
# PARAGRAPH_NUMBER_RE — accept zero-space variants without matching numerics
# ============================================================================


@pytest.mark.parametrize(
    "text, expected_number",
    [
        ("1. The light of Faith", 1),
        ("131.Later, his spiritual director", 131),  # Dilexit Nos quirk
        ("  17. We have raised", 17),  # leading whitespace ok
        ("1. *Spe Salvi facti sumus*", 1),  # italic prefix
        ('1. "Praise be to you"', 1),  # straight quote prefix
        ("1. “Praise be to you”", 1),  # curly quote prefix
    ],
)
def test_paragraph_number_re_matches_valid_paragraphs(text: str, expected_number: int) -> None:
    m = PARAGRAPH_NUMBER_RE.match(text)
    assert m is not None, f"should match {text!r}"
    assert int(m.group(1)) == expected_number


@pytest.mark.parametrize(
    "text",
    [
        "1.5 metres of altitude",  # decimal, not a paragraph number
        "100.000 people",  # European decimal
        "Cf. 1. opening paragraph",  # mid-sentence number
        "",
        "no number here",
    ],
)
def test_paragraph_number_re_rejects_non_paragraphs(text: str) -> None:
    assert PARAGRAPH_NUMBER_RE.match(text) is None, f"should not match {text!r}"


def test_extract_paragraph_number_returns_rest_after_marker() -> None:
    n, rest = extract_paragraph_number("131.Later, his spiritual director")
    assert n == 131
    assert rest == "Later, his spiritual director"


# ============================================================================
# title_case — first alphabetic character of each word
# ============================================================================


def test_title_case_capitalizes_after_leading_punctuation() -> None:
    """Curly-quoted Latin should produce ``"Laudato`` not ``"laudato``."""
    assert title_case('"laudato si"') == '"Laudato Si"'
    assert title_case("'caritas'") == "'Caritas'"
    assert title_case("(carit̀as in veritate)") == "(Carit̀as in Veritate)"


def test_title_case_preserves_roman_numerals() -> None:
    assert title_case("Benedict XVI") == "Benedict XVI"
    assert title_case("POPE LEO XIV") == "Pope Leo XIV"


def test_title_case_lowercases_small_words_only_in_middle() -> None:
    """Mid-sentence ``and``/``of``/``the`` lowercased; first/last word always cased."""
    assert title_case("FRATERNITY AND SOCIAL FRIENDSHIP") == "Fraternity and Social Friendship"
    assert title_case("the heart of jesus") == "The Heart of Jesus"
    # 'a' at the very start gets capitalized (not treated as small-word-in-middle).
    assert title_case("a hidden challenge") == "A Hidden Challenge"


# ============================================================================
# FOOTNOTE refs — absolute self-referential URLs (Lumen Fidei)
# ============================================================================


def test_footnote_ref_recognised_from_absolute_url() -> None:
    """Lumen Fidei body refs use ``href="/content/.../doc.html#_ftn1"``."""
    html = (
        '<div class="vaticanrichtext"><p>The sun does not illumine'
        '<a href="/content/francesco/en/encyclicals/documents/doc.html#_ftn1"'
        ' name="_ftnref1">[1]</a> all reality.</p></div>'
    )
    tree = LexborHTMLParser(html)
    p = tree.css_first("p")
    md = node_to_markdown(p)
    assert "[^1]" in md
    assert "#_ftn" not in md, "the raw href must not leak into the markdown"


def test_footnote_def_back_link_visible_text_preserved() -> None:
    """A definition's back-link anchor keeps its ``[N]`` visible text."""
    html = (
        '<div class="vaticanrichtext"><p>'
        '<a href="#_ftnref1" name="_ftn1">[1]</a>'
        " First footnote body."
        "</p></div>"
    )
    tree = LexborHTMLParser(html)
    p = tree.css_first("p")
    md = node_to_markdown(p)
    assert md.startswith("[1]"), "the definition's [1] label must be preserved verbatim"


# ============================================================================
# split_body_and_footnotes — content-based identification
# ============================================================================


def test_split_finds_footnote_defs_in_nested_divs() -> None:
    """Laudato Si' nests each footnote def in its own ``<div id="ftnN">``."""
    html = (
        '<div class="text parbase vaticanrichtext container">'
        "<p>1. Praise be to you, my Lord.</p>"
        '<div><p><a name="_ftn1" href="#_ftnref1">[1]</a> Canticle of the Creatures.</p></div>'
        '<div id="ftn2"><p><a name="_ftn2" href="#_ftnref2">[2]</a> Octogesima Adveniens.</p></div>'
        "</div>"
    )
    tree = LexborHTMLParser(html)
    container = tree.css_first("div.vaticanrichtext")
    body, fns = split_body_and_footnotes(tree, container)
    assert len(body) == 1
    assert "Praise be to you" in body[0].text(deep=True, strip=True)
    assert len(fns) == 2


def test_split_handles_dateline_in_font_wrapper() -> None:
    """Lumen Fidei buries the dateline + <hr/> inside a ``<font>`` wrapper."""
    dateline = "Given in Rome, on 29 June, in the year 2013, the first of my pontificate."
    html = (
        '<div class="text parbase vaticanrichtext container">'
        "<p>1. The light of Faith.</p>"
        f'<font size="4"><p>{dateline}</p><hr/></font>'
        '<p><a name="_ftn1" href="#_ftnref1">[1]</a> Dialogus cum Tryphone Iudaeo.</p>'
        "</div>"
    )
    tree = LexborHTMLParser(html)
    container = tree.css_first("div.vaticanrichtext")
    body, fns = split_body_and_footnotes(tree, container)
    # The dateline lives inside the <font> but is captured as a body para
    # (which the dateline finder picks up downstream).
    body_text = " ".join(p.text(deep=True, strip=True) for p in body)
    assert "Given in Rome" in body_text
    assert len(fns) == 1


# ============================================================================
# _parse_footnotes — malformed labels and packed paragraphs
# ============================================================================


def test_parse_footnotes_recovers_number_from_anchor_when_label_broken() -> None:
    """Fratelli Tutti has ``<a name="_ftn86"></a>86]`` — no opening bracket."""
    html = (
        '<div class="vaticanrichtext">'
        '<p><a name="_ftn86" href="#_ftnref86"></a>86] Encyclical Letter <i>Laudato Si\'</i>.</p>'
        "</div>"
    )
    tree = LexborHTMLParser(html)
    p = tree.css_first("p")
    fns = _parse_footnotes([p])
    assert len(fns) == 1
    assert fns[0].number == 86
    assert "Laudato Si" in fns[0].text


def test_parse_footnotes_splits_packed_definitions() -> None:
    """Fratelli Tutti packs ftn 118 + 119 into a single ``<p>``."""
    html = (
        '<div class="vaticanrichtext"><p>'
        '<a name="_ftn118" href="#_ftnref118">[118]</a>'
        " <i>Latinoamerica. Conversaciones.</i>"
        '<a name="_ftn119" href="#_ftnref119">[119]</a>'
        " <i>Document on Human Fraternity.</i>"
        "</p></div>"
    )
    tree = LexborHTMLParser(html)
    p = tree.css_first("p")
    fns = _parse_footnotes([p])
    assert {f.number for f in fns} == {118, 119}
    f118 = next(f for f in fns if f.number == 118)
    f119 = next(f for f in fns if f.number == 119)
    assert "Latinoamerica" in f118.text
    assert "Human Fraternity" in f119.text


# ============================================================================
# _extract_incipit — title-first-word filter for scripture citations
# ============================================================================


def test_extract_incipit_uses_italic_when_it_matches_title() -> None:
    """Spe Salvi paragraph 1 opens with ``*SPE SALVI facti sumus*``."""
    paragraphs = [
        Paragraph(
            number=1,
            section=None,
            text='"*SPE SALVI facti sumus*"—in hope we were saved',
        )
    ]
    assert _extract_incipit(paragraphs, "Spe Salvi") == "Spe Salvi Facti Sumus"


def test_extract_incipit_falls_back_to_title_for_scripture_citations() -> None:
    """Deus Caritas Est ¶1 italicizes the *1 Jn* scripture book first."""
    paragraphs = [
        Paragraph(
            number=1,
            section=None,
            text='"God is love, and he who abides in love..." (*1 Jn* 4:16).',
        )
    ]
    assert _extract_incipit(paragraphs, "Deus Caritas Est") == "Deus Caritas Est"


def test_extract_incipit_prefers_title_over_single_word_echo() -> None:
    """Caritas in Veritate ¶1 has ``*caritas*`` mid-paragraph — too short."""
    paragraphs = [
        Paragraph(
            number=1,
            section=None,
            text="Charity in truth — *caritas* — is an extraordinary force",
        )
    ]
    assert _extract_incipit(paragraphs, "Caritas in Veritate") == "Caritas in Veritate"


def test_extract_incipit_returns_title_when_paragraph_one_lacks_italic() -> None:
    """Magnifica Humanitas ¶1 has no italic — use the title."""
    paragraphs = [
        Paragraph(
            number=1,
            section=None,
            text="Humanity, created by God in all its grandeur",
        )
    ]
    assert _extract_incipit(paragraphs, "Magnifica Humanitas") == "Magnifica Humanitas"


# ============================================================================
# find_title_paragraph — scans every vaticanrichtext div, not just the body
# ============================================================================


def test_find_title_finds_block_in_abstract_div() -> None:
    """Leo-era documents put the title block in a separate ``.abstract`` div."""
    title_block = "ENCYCLICAL LETTER<br/>MAGNIFICA HUMANITAS<br/>OF HIS HOLINESS<br/>POPE LEO XIV"
    html = (
        '<div class="abstract text parbase vaticanrichtext">'
        f'<p style="text-align: center;">{title_block}</p>'
        "</div>"
        '<div class="text parbase vaticanrichtext">'
        "<p>INTRODUCTION</p><p>1. Body text.</p>"
        "</div>"
    )
    tree = LexborHTMLParser(html)
    body = max(tree.css("div.vaticanrichtext"), key=lambda d: len(d.css("p")))
    title_p = find_title_paragraph(tree, body)
    assert title_p is not None
    assert "ENCYCLICAL LETTER" in title_p.text(deep=True, strip=True)


# ============================================================================
# Cross-validation against real fixtures
# ============================================================================


def test_dateline_parser_handles_lumen_fidei_format() -> None:
    """Lumen Fidei: ``29 June, the Solemnity..., in the year 2013``."""
    date_str = (
        "Given in Rome, on 29 June, the Solemnity of the Holy Apostles "
        "Peter and Paul, in the year 2013, the first of my pontificate."
    )
    parsed = parse_dateline_date(date_str)
    assert parsed is not None
    assert parsed.year == 2013
    assert parsed.month == 6
    assert parsed.day == 29


def test_dateline_parser_handles_magnifica_humanitas_format() -> None:
    """Magnifica Humanitas: ``on 15 May, in the year 2026, the second of my Pontificate``."""
    date_str = "Given in Rome, on 15 May, in the year 2026, the second of my Pontificate."
    parsed = parse_dateline_date(date_str)
    assert parsed is not None
    assert parsed.year == 2026
    assert parsed.month == 5
    assert parsed.day == 15


def test_is_heading_treats_centered_bold_caps_as_heading() -> None:
    """Spe Salvi's Roman-numeral chapter dividers."""
    html = '<p align="center"><b>I. Prayer as a school of hope</b></p>'
    tree = LexborHTMLParser(html)
    p = tree.css_first("p")
    assert is_heading(p) is True


def test_is_heading_treats_body_paragraph_as_not_heading() -> None:
    html = "<p>1. Body text starts here with no special markup.</p>"
    tree = LexborHTMLParser(html)
    p = tree.css_first("p")
    assert is_heading(p) is False
