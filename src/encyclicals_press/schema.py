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

    slug: str
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
