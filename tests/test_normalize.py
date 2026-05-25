"""Unit tests for :mod:`encyclicals_press.normalize`."""

from __future__ import annotations

from datetime import date

from encyclicals_press.normalize import _clean, normalize
from encyclicals_press.schema import Encyclical, Footnote, Paragraph


def test_triple_dots_become_ellipsis() -> None:
    assert _clean("wait...") == "wait…"
    assert _clean("a....b") == "a…b"


def test_straight_double_quotes_become_curly() -> None:
    assert _clean('"hello"') == "“hello”"
    assert _clean('He said "hi".') == "He said “hi”."


def test_straight_single_quotes_become_curly() -> None:
    assert _clean("She said 'hi'.") == "She said ‘hi’."


def test_existing_curly_quotes_are_preserved() -> None:
    assert _clean("“already curly”") == "“already curly”"
    assert _clean("‘already curly’") == "‘already curly’"


def test_double_ascii_hyphen_becomes_em_dash() -> None:
    assert _clean("word -- word") == "word—word"
    assert _clean("word---word") == "word—word"


def test_numeric_hyphen_becomes_en_dash() -> None:
    assert _clean("pp. 12-34") == "pp. 12–34"


def test_nbsp_collapses_to_space() -> None:
    assert _clean("foo bar") == "foo bar"


def test_multiple_spaces_collapse() -> None:
    assert _clean("foo    bar") == "foo bar"


def test_footnote_marker_loses_leading_space() -> None:
    assert _clean("Aquinas  [^4], using") == "Aquinas[^4], using"


def test_normalize_applies_to_all_fields() -> None:
    enc = Encyclical(
        slug="test",
        title="Test",
        subtitle=None,
        pope="Pope Test",
        promulgated=date(2025, 1, 1),
        incipit='straight "quote"',
        salutation='He said "hello"',
        paragraphs=[
            Paragraph(number=1, section='"intro"', text='wait... "yes"'),
            Paragraph(number=None, section=None, text="word -- word"),
        ],
        footnotes=[
            Footnote(number=1, text='See "Source"'),
        ],
        source_url="https://example.test",
    )
    out = normalize(enc)
    assert out.incipit == "straight “quote”"
    assert out.salutation == "He said “hello”"
    assert out.paragraphs[0].section == "“intro”"
    assert out.paragraphs[0].text == "wait… “yes”"
    assert out.paragraphs[1].text == "word—word"
    assert out.footnotes[0].text == "See “Source”"


def test_normalize_does_not_mutate_input() -> None:
    enc = Encyclical(
        slug="x",
        title="X",
        subtitle=None,
        pope="X",
        promulgated=date(2025, 1, 1),
        incipit="",
        salutation="",
        paragraphs=[Paragraph(number=1, section=None, text='"a"')],
        footnotes=[],
        source_url="https://example.test",
    )
    _ = normalize(enc)
    assert enc.paragraphs[0].text == '"a"', "normalize must not mutate input model"
