"""Post-parse validation.

After a strategy produces an :class:`Encyclical`, :func:`validate` walks the
result and emits :class:`ParseWarning` records for anything that looks
broken or suspicious. Errors (``severity == "error"``) cause the parser
to fall back to the next strategy in the chain; warnings (``"warn"``) and
informational notes (``"info"``) are surfaced to the user but don't trip
self-healing.

Checks are deliberately defensive and additive: if a checker can't run
(missing field, malformed text), it skips itself rather than crashing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..schema import Encyclical


@dataclass(frozen=True)
class ParseWarning:
    """A single observation about a parsed document.

    :attr:`code`: a short, stable identifier suitable for filtering.
    :attr:`message`: human-readable detail.
    :attr:`severity`: ``"error"`` (triggers fallback strategy), ``"warn"``,
                       or ``"info"``.
    """

    code: str
    message: str
    severity: str

    def __str__(self) -> str:
        return f"[{self.severity}] {self.code}: {self.message}"


def validate(enc: Encyclical) -> list[ParseWarning]:
    """Return the warnings raised by every applicable check."""
    out: list[ParseWarning] = []
    for check in _CHECKS:
        out.extend(check(enc))
    return out


def has_errors(warnings: list[ParseWarning]) -> bool:
    """True if any warning's severity is ``"error"``."""
    return any(w.severity == "error" for w in warnings)


# ---- individual checks --------------------------------------------------


def _check_title(enc: Encyclical) -> list[ParseWarning]:
    if not enc.title.strip():
        return [ParseWarning("missing-title", "title is empty", "error")]
    return []


def _check_pope(enc: Encyclical) -> list[ParseWarning]:
    if not enc.pope.strip():
        return [ParseWarning("missing-pope", "pope is empty", "error")]
    return []


def _check_paragraphs(enc: Encyclical) -> list[ParseWarning]:
    if not enc.paragraphs:
        return [ParseWarning("no-paragraphs", "no body paragraphs extracted", "error")]
    numbered = [p for p in enc.paragraphs if p.number is not None]
    if not numbered:
        return [
            ParseWarning(
                "no-numbered-paragraphs",
                "no numbered paragraphs — the document may have an unfamiliar layout",
                "error",
            )
        ]
    return []


def _check_paragraph_number_contiguity(enc: Encyclical) -> list[ParseWarning]:
    numbers = [p.number for p in enc.paragraphs if p.number is not None]
    if not numbers:
        return []
    out: list[ParseWarning] = []
    if numbers[0] != 1:
        out.append(
            ParseWarning(
                "first-paragraph-not-1",
                f"first numbered paragraph is {numbers[0]}, expected 1",
                "warn",
            )
        )
    gaps = _find_gaps(numbers)
    if gaps:
        out.append(
            ParseWarning(
                "paragraph-number-gap",
                f"paragraph numbers are non-contiguous: {_describe_gaps(gaps)}",
                "warn",
            )
        )
    return out


_FOOTNOTE_REF_RE = re.compile(r"\[\^(\d+)\]")


def _check_footnote_balance(enc: Encyclical) -> list[ParseWarning]:
    refs: set[int] = set()
    for p in enc.paragraphs:
        refs.update(int(m.group(1)) for m in _FOOTNOTE_REF_RE.finditer(p.text))
    defs = {f.number for f in enc.footnotes}
    if refs and not defs:
        return [
            ParseWarning(
                "no-footnote-definitions",
                f"{len(refs)} footnote references in body but no definitions parsed",
                "error",
            )
        ]
    missing = refs - defs
    unused = defs - refs
    if not missing and not unused:
        return []
    parts: list[str] = []
    if missing:
        parts.append(f"refs without defs: {_short(sorted(missing))}")
    if unused:
        parts.append(f"defs without refs: {_short(sorted(unused))}")
    return [ParseWarning("footnote-mismatch", "; ".join(parts), "warn")]


def _check_promulgation_date(enc: Encyclical) -> list[ParseWarning]:
    if enc.promulgated is None:
        return [ParseWarning("missing-date", "could not extract promulgation date", "error")]
    return []


_CHECKS = (
    _check_title,
    _check_pope,
    _check_paragraphs,
    _check_paragraph_number_contiguity,
    _check_footnote_balance,
    _check_promulgation_date,
)


def _find_gaps(numbers: list[int]) -> list[tuple[int, int]]:
    """Return ``(prev, next)`` pairs where the sequence skips one or more values."""
    gaps: list[tuple[int, int]] = []
    for i in range(1, len(numbers)):
        if numbers[i] != numbers[i - 1] + 1:
            gaps.append((numbers[i - 1], numbers[i]))
    return gaps


def _describe_gaps(gaps: list[tuple[int, int]]) -> str:
    shown = gaps[:3]
    rendered = ", ".join(f"{a}→{b}" for a, b in shown)
    if len(gaps) > len(shown):
        rendered += f", … ({len(gaps)} total)"
    return rendered


def _short(values: list[int]) -> str:
    if len(values) <= 5:  # noqa: PLR2004
        return str(values)
    return f"{values[:5]} (+{len(values) - 5} more)"
