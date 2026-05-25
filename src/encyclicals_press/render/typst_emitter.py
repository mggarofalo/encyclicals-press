"""Emit Typst source from a :class:`ParsedCorpus`.

Generates a self-contained ``.typ`` file that imports the project
templates, applies the ``edition`` show rule with the document's
metadata, and then walks the body blocks in order. Helper template
functions (``paragraph-num``, ``chapter-divider``, …) are imported from
``templates/lib/typography.typ`` so they're in scope for the body.

The emitter is a pure layout layer: every semantic decision (which
heading is a chapter divider, what counts as a signature, where the
paragraph number lives) is already resolved in the parser and encoded
as a typed corpus block. The walk here is a straight dispatch on
``block.kind``.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from .corpus_reader import ParsedCorpus
from .markdown import inline_to_typst, inline_to_typst_markup, wrap_section_opening


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
            lines.append(f"#section-heading({_quote(block.text)})")
            lines.append("")
            first_para_in_section = True
            continue

        if block.kind == "chapter-divider":
            numeral = (block.numeral or "") + "."
            lines.append(f"#chapter-divider({_quote(numeral)}, {_quote(block.text)})")
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
            lines.append(f"#signature({inline_to_typst(block.text, parsed.footnotes)})")
            lines.append("")
            continue

    return "\n".join(lines)


# ---- internals ----------------------------------------------------------


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
