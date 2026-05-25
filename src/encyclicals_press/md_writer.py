"""Serialize an :class:`Encyclical` to corpus Markdown.

Output convention (Pandoc-flavored Markdown):

* YAML frontmatter carrying every metadata field.
* Section headings as ``## Heading``.
* Numbered paragraphs as fenced divs::

      ::: {.paragraph n=49}
      Body text with [^12] inline footnote markers.
      :::

* Unnumbered continuation prose as a plain paragraph (no fence).
* The closing dateline and papal signature as ``{.dateline}`` and
  ``{.signature}`` fenced divs.
* Footnotes at the tail as Pandoc-style ``[^N]: text``.

This file is the project's actual product — it is meant to be hand-edited.
Keep the format readable.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from .schema import Encyclical, Paragraph


def write_markdown(enc: Encyclical, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_markdown(enc), encoding="utf-8", newline="\n")


def render_markdown(enc: Encyclical) -> str:
    return "".join(
        [
            _render_frontmatter(enc),
            "\n",
            _render_salutation(enc),
            _render_body(enc),
            _render_footnotes(enc),
        ]
    )


def _render_frontmatter(enc: Encyclical) -> str:
    data = {
        "slug": enc.slug,
        "title": enc.title,
        "subtitle": enc.subtitle,
        "pope": enc.pope,
        "promulgated": enc.promulgated.isoformat(),
        "incipit": enc.incipit,
        "salutation": enc.salutation,
        "source_url": enc.source_url,
    }
    body = yaml.safe_dump(data, sort_keys=False, allow_unicode=True, default_flow_style=False)
    return f"---\n{body}---\n"


def _render_salutation(enc: Encyclical) -> str:
    if not enc.salutation:
        return ""
    return f"::: {{.salutation}}\n{enc.salutation}\n:::\n\n"


def _render_body(enc: Encyclical) -> str:
    chunks: list[str] = []
    current_section: str | None = None
    for p in enc.paragraphs:
        if p.section != current_section and p.section is not None:
            chunks.append(f"## {p.section}\n\n")
            current_section = p.section
        chunks.append(_render_paragraph(p))
    return "".join(chunks)


def _render_paragraph(p: Paragraph) -> str:
    # The closing dateline and signature share the same ``Paragraph(number=None,
    # section=None)`` shape that continuation prose uses, so distinguish by
    # surface pattern: italic dateline, bold/uppercase signature.
    text = p.text
    if p.number is None:
        if text.startswith("*Given in") or text.startswith("*Given at"):
            return f"::: {{.dateline}}\n{text}\n:::\n\n"
        if _looks_like_signature(text):
            return f"::: {{.signature}}\n{text}\n:::\n\n"
        # Continuation paragraph; emit as plain Markdown.
        return f"{text}\n\n"
    return f"::: {{.paragraph n={p.number}}}\n{text}\n:::\n\n"


def _looks_like_signature(text: str) -> bool:
    stripped = text.strip().strip("*").strip()
    if not stripped or len(stripped) > 60:  # noqa: PLR2004
        return False
    letters = [c for c in stripped if c.isalpha()]
    if not letters:
        return False
    upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
    return upper_ratio > 0.7  # noqa: PLR2004


def _render_footnotes(enc: Encyclical) -> str:
    if not enc.footnotes:
        return ""
    lines = ["\n## Footnotes\n\n"]
    for f in enc.footnotes:
        lines.append(f"[^{f.number}]: {f.text}\n\n")
    return "".join(lines)
