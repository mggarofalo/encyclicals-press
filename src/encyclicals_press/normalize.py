"""Post-parse cleanup pass on the :class:`Encyclical` model.

Conservative by design: fix typographic artifacts the vatican.va prints
inherit (straight quotes that escaped, doubled spaces, leftover NBSP, ``--``
that should be en-dashes), but do not touch the actual prose. The corpus
Markdown is a long-lived hand-editable artifact; over-eager normalization
makes it impossible to round-trip past human edits.
"""

from __future__ import annotations

import re
import unicodedata

from .schema import Encyclical, Footnote, Paragraph

# Straight quote -> smart quote heuristics. We only touch quotes that the
# source clearly left straight; vatican.va already curls most of them.
_STRAIGHT_DOUBLE_OPEN = re.compile(r'(^|[\s(\[{])"')
_STRAIGHT_DOUBLE_CLOSE = re.compile(r'"')
_STRAIGHT_SINGLE_OPEN = re.compile(r"(^|[\s(\[{])'")
_STRAIGHT_SINGLE_CLOSE = re.compile(r"'")

_TRIPLE_DOT = re.compile(r"\.{3,}")
_MULTI_SPACE = re.compile(r"[ \t]{2,}")
_ASCII_EM_DASH = re.compile(r"(?<=\w) -- (?=\w)|(?<=\w)---(?=\w)")
_ASCII_EN_DASH = re.compile(r"(?<=\d)-(?=\d)")
# Footnote separators where vatican.va leaves stray spaces:  " [^12]." -> "[^12]."
_FOOTNOTE_TIGHTEN = re.compile(r"\s+\[\^(\d+)\]")


def normalize(enc: Encyclical) -> Encyclical:
    """Return a copy of *enc* with cleanup applied to all text fields."""
    return enc.model_copy(
        update={
            "salutation": _clean(enc.salutation),
            "incipit": _clean(enc.incipit),
            "paragraphs": [_clean_paragraph(p) for p in enc.paragraphs],
            "footnotes": [_clean_footnote(f) for f in enc.footnotes],
        }
    )


def _clean_paragraph(p: Paragraph) -> Paragraph:
    return p.model_copy(
        update={
            "section": _clean(p.section) if p.section else p.section,
            "text": _clean(p.text),
        }
    )


def _clean_footnote(f: Footnote) -> Footnote:
    return f.model_copy(update={"text": _clean(f.text)})


def _clean(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = text.replace(" ", " ")  # NBSP
    text = text.replace(" ", " ").replace(" ", " ")  # line/para sep
    text = _TRIPLE_DOT.sub("…", text)
    text = _ASCII_EM_DASH.sub("—", text)
    text = _ASCII_EN_DASH.sub("–", text)
    text = _smart_quote(text)
    text = _FOOTNOTE_TIGHTEN.sub(r"[^\1]", text)
    text = _MULTI_SPACE.sub(" ", text)
    return text.strip()


def _smart_quote(text: str) -> str:
    """Replace any straight quotes the source still has with curly equivalents.

    Order matters: openings are determined by what precedes them (start of
    string or whitespace/opening bracket), and all remaining straight quotes
    are then treated as closings.
    """
    text = _STRAIGHT_DOUBLE_OPEN.sub(r"\1“", text)
    text = _STRAIGHT_DOUBLE_CLOSE.sub("”", text)
    text = _STRAIGHT_SINGLE_OPEN.sub(r"\1‘", text)
    text = _STRAIGHT_SINGLE_CLOSE.sub("’", text)
    return text
