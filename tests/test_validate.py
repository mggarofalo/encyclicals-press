"""Tests for :mod:`encyclicals_press.parse.validate`."""

from __future__ import annotations

from datetime import date

from encyclicals_press.parse.validate import (
    ParseWarning,
    has_errors,
    validate,
)
from encyclicals_press.schema import Encyclical, Footnote, Paragraph


def _make(
    *,
    title: str = "Test",
    pope: str = "Test Pope",
    paragraphs: list[Paragraph] | None = None,
    footnotes: list[Footnote] | None = None,
) -> Encyclical:
    if paragraphs is None:
        paragraphs = [Paragraph(number=1, section=None, text="hello.")]
    if footnotes is None:
        footnotes = []
    return Encyclical(
        slug="t",
        title=title,
        subtitle=None,
        pope=pope,
        promulgated=date(2024, 1, 1),
        incipit="",
        salutation="",
        paragraphs=paragraphs,
        footnotes=footnotes,
        source_url="https://example.test",
    )


def test_clean_encyclical_has_no_warnings() -> None:
    assert validate(_make()) == []


def test_missing_title_is_error() -> None:
    out = validate(_make(title=""))
    assert any(w.code == "missing-title" and w.severity == "error" for w in out)


def test_missing_pope_is_error() -> None:
    out = validate(_make(pope=""))
    assert any(w.code == "missing-pope" and w.severity == "error" for w in out)


def test_no_paragraphs_is_error() -> None:
    out = validate(_make(paragraphs=[]))
    assert any(w.code == "no-paragraphs" and w.severity == "error" for w in out)


def test_no_numbered_paragraphs_is_error() -> None:
    out = validate(_make(paragraphs=[Paragraph(number=None, section=None, text="hi")]))
    assert any(w.code == "no-numbered-paragraphs" and w.severity == "error" for w in out)


def test_first_paragraph_not_one_is_warn() -> None:
    out = validate(_make(paragraphs=[Paragraph(number=5, section=None, text="hi")]))
    codes = {w.code: w.severity for w in out}
    assert codes.get("first-paragraph-not-1") == "warn"


def test_paragraph_number_gap_is_warn() -> None:
    out = validate(
        _make(
            paragraphs=[
                Paragraph(number=1, section=None, text="a"),
                Paragraph(number=2, section=None, text="b"),
                Paragraph(number=5, section=None, text="e"),
            ]
        )
    )
    assert any(w.code == "paragraph-number-gap" and w.severity == "warn" for w in out)


def test_footnote_refs_without_defs_is_error() -> None:
    out = validate(
        _make(paragraphs=[Paragraph(number=1, section=None, text="hi[^1]")], footnotes=[])
    )
    assert any(w.code == "no-footnote-definitions" and w.severity == "error" for w in out)


def test_unused_footnote_def_is_warn() -> None:
    out = validate(
        _make(
            paragraphs=[Paragraph(number=1, section=None, text="hi")],
            footnotes=[Footnote(number=1, text="unused")],
        )
    )
    assert any(w.code == "footnote-mismatch" and w.severity == "warn" for w in out)


def test_has_errors_detects_error_severity() -> None:
    warnings = [
        ParseWarning(code="x", message="x", severity="warn"),
        ParseWarning(code="y", message="y", severity="error"),
    ]
    assert has_errors(warnings)
    assert not has_errors([w for w in warnings if w.severity != "error"])


def test_warning_str_includes_severity_and_code() -> None:
    w = ParseWarning(code="missing-title", message="title is empty", severity="error")
    s = str(w)
    assert "error" in s
    assert "missing-title" in s
    assert "title is empty" in s
