"""Emit Typst source from a :class:`ParsedCorpus`.

Generates a self-contained ``.typ`` file that imports the project
templates, applies the ``edition`` show rule with the document's
metadata, and then walks the body blocks in order. Helper template
functions (``paragraph-num``, ``chapter-divider``, …) are imported from
``templates/lib/typography.typ`` so they're in scope for the body.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime

from .corpus_reader import ParsedCorpus
from .markdown import inline_to_typst, inline_to_typst_markup, wrap_section_opening

_ROMAN_PREFIX_RE = re.compile(r"^([IVXLCDM]+)\.\s+(.+)$")


def emit_typst(parsed: ParsedCorpus) -> str:
    """Render *parsed* to a Typst source string."""
    meta = parsed.meta
    promulgated = _coerce_date(meta.get("promulgated"))

    lines: list[str] = [
        '#import "/templates/lib/typography.typ": '
        "paragraph-num, section-heading, chapter-divider, "
        "salutation, dateline, signature",
        "",
        '#import "/templates/default.typ": edition, section-opening',
        "",
        "#show: edition.with(",
        f"  title: {_quote(meta.get('title', ''))},",
        f"  subtitle: {_quote_optional(meta.get('subtitle'))},",
        f"  pope: {_quote(meta.get('pope', ''))},",
        f"  promulgated: {_typst_date(promulgated)},",
        f"  incipit: {_quote_optional(meta.get('incipit'))},",
        f"  source-url: {_quote(meta.get('source_url', ''))},",
        f"  fetch-date: {_quote(_today())},",
        ")",
        "",
    ]

    first_para_in_section = True

    for block in parsed.blocks:
        if block.kind == "salutation":
            lines.append(f"#salutation({inline_to_typst(block.text, parsed.footnotes)})")
            lines.append("")
            continue

        if block.kind == "section":
            lines.append(_emit_section_heading(block.text))
            lines.append("")
            first_para_in_section = True
            continue

        if block.kind == "paragraph":
            markup = inline_to_typst_markup(block.text, parsed.footnotes)
            opening = f"#paragraph-num({block.number}) " if block.number else ""
            if first_para_in_section:
                markup = wrap_section_opening(markup)
                first_para_in_section = False
            lines.append(opening + markup)
            lines.append("")
            continue

        if block.kind == "continuation":
            lines.append(inline_to_typst_markup(block.text, parsed.footnotes))
            lines.append("")
            continue

        if block.kind == "dateline":
            lines.append(f"#dateline({inline_to_typst(block.text, parsed.footnotes)})")
            lines.append("")
            continue

        if block.kind == "signature":
            # Signature is rendered as letterspaced caps; strip markdown
            # bold so it doesn't compete with the template styling.
            clean = re.sub(r"\*\*([^*]+)\*\*", r"\1", block.text)
            lines.append(f"#signature({inline_to_typst(clean, parsed.footnotes)})")
            lines.append("")
            continue

    return "\n".join(lines)


# ---- internals ----------------------------------------------------------


_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)\s]+\)")
_MD_FOOTNOTE_RE = re.compile(r"\[\^\d+\]")
_MD_EMPHASIS_RE = re.compile(r"\*{1,2}([^*]+)\*{1,2}")


def _strip_markdown(text: str) -> str:
    """Reduce a fragment of corpus Markdown to plain text suitable for a
    Typst smallcaps heading. Section names in the corpus can carry inline
    links (e.g. ``"... from [Leo XIII](https://...)"``) and italic
    emphasis — Typst would render the brackets and URL as literal
    characters inside the heading, so collapse to the label form here.
    """
    text = _MD_LINK_RE.sub(r"\1", text)
    text = _MD_FOOTNOTE_RE.sub("", text)
    text = _MD_EMPHASIS_RE.sub(r"\1", text)
    return text.strip()


def _emit_section_heading(text: str) -> str:
    text = _strip_markdown(text)
    roman_m = _ROMAN_PREFIX_RE.match(text)
    if roman_m is None:
        return f"#section-heading({_quote(text)})"
    numeral, title = roman_m.group(1), roman_m.group(2)
    return f"#chapter-divider({_quote(numeral + '.')}, {_quote(title)})"


def _quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _quote_optional(value: object) -> str:
    if value is None or value == "":
        return "none"
    return _quote(str(value))


def _typst_date(value: date | None) -> str:
    if value is None:
        return "none"
    return f"datetime(year: {value.year}, month: {value.month}, day: {value.day})"


def _coerce_date(value: object) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise TypeError(f"unexpected date value: {value!r}")


def _today() -> str:
    return datetime.now(tz=UTC).date().isoformat()
