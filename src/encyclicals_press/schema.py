"""Intermediate schema for encyclicals.

Flat by design — the corpus Markdown is the artifact users read and hand-edit, and
the schema is just the data carrier between stages (parse, normalize, render). Resist
the urge to grow this into a block tree.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict


class Paragraph(BaseModel):
    model_config = ConfigDict(extra="forbid")

    number: int | None
    """The encyclical paragraph number (1, 2, ...). ``None`` for continuation
    paragraphs that share a number with the preceding one, and for prose that
    sits outside the numbered body (the closing dateline and signature)."""

    chapter: str | None = None
    """The most recent Roman-numeral chapter divider above this paragraph,
    as ``"I. Inheritance"`` / ``"II. The Mystery"`` etc. The renderer
    promotes this to a ``#chapter-divider`` block. ``None`` for documents
    without explicit chapter dividers."""

    section: str | None
    """The most recent heading-like paragraph above this one in document order.
    Carried, not nested — the corpus is too lightly structured to justify a tree."""

    text: str
    """Inline Markdown. Footnote references appear as ``[^N]``; italic spans as
    ``*span*``; scripture/source links as ``[text](url)``."""


class Footnote(BaseModel):
    model_config = ConfigDict(extra="forbid")

    number: int
    text: str
    """Inline Markdown, same conventions as :attr:`Paragraph.text`."""


class Encyclical(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title_slug: str
    """Kebab-case identifier derived from the title — e.g. ``redemptor-hominis``.
    Used as the corpus filename and as the last component of output PDF names."""

    author_slug: str
    """Kebab-case slug for the promulgating pope — e.g. ``john-paul-ii``.
    Used as the corpus subdirectory and as the middle component of output PDF
    names. Derived from :attr:`pope` at parse time; hand-editable thereafter."""

    publication_date_slug: str
    """ISO date slug for the promulgation — e.g. ``1979-03-04``. Stored
    explicitly so output filenames are self-describing without re-deriving
    from :attr:`promulgated`."""

    title: str
    subtitle: str | None
    pope: str
    promulgated: date
    incipit: str
    salutation: str
    """The full opening salutation block (``"To the Bishops, Priests and Deacons..."``)
    rendered as a SCOTUS-style rubric preamble before the numbered body."""

    paragraphs: list[Paragraph]
    footnotes: list[Footnote]
    source_url: str
