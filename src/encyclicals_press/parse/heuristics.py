"""Default heuristics for the parsing pipeline.

Every decision a parser has to make about vatican.va HTML — where the title
lives, what counts as a heading, how to recognise the closing dateline —
lives here as a named, single-responsibility function. A :class:`Strategy`
bundles a choice for each. Replace any field on the strategy to override
the corresponding heuristic for a specific document layout without
rewriting the whole parser.

The functions break into two layers:

* **Markup helpers** at the top: pure utilities that walk the HTML node
  tree and emit our internal Markdown dialect. These are not strategy
  fields — they are shared infrastructure.
* **Strategy heuristics** below: each maps to one field on
  :class:`Strategy`. Their docstrings document the contract.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import date

from selectolax.lexbor import LexborHTMLParser, LexborNode

# ---- regexes shared across heuristics ----------------------------------

# A numbered paragraph begins ``"N. Text..."`` — but vatican.va inconsistently
# drops the space between the period and the first word (Dilexit Nos has
# ``"131.Later"`` and ``"135.In"`` mid-document). Allow zero-or-more space
# but require the next character to look like the start of prose (a letter,
# or an opening quote/bracket) so plain numerics like ``"1.5 metres"`` don't
# accidentally match.
PARAGRAPH_NUMBER_RE = re.compile(r"^\s*(\d{1,4})\.\s*(?=[A-Za-z“”\"‘’'(\[*])")
# Body footnote refs and definition back-links can use either a bare
# fragment (``#_ftn1`` / ``#_ftnref1``) or an absolute URL whose fragment
# is the same (``/content/.../doc.html#_ftn1``). ``search`` rather than
# ``match`` so either form qualifies.
FOOTNOTE_BODY_HREF_RE = re.compile(r"#?_ftn(\d+)$")
FOOTNOTE_DEF_HREF_RE = re.compile(r"#?_ftnref(\d+)$")
ROMAN_RE = re.compile(r"^[IVXLCDM]+\.?$", re.IGNORECASE)

DATE_RE = re.compile(
    r"on (\d{1,2}) (January|February|March|April|May|June|July|August|"
    r"September|October|November|December)\b.*?(\d{4})",
    re.IGNORECASE,
)

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}  # fmt: skip

SIGNATURE_MAX_LEN = 60
SIGNATURE_UPPERCASE_RATIO = 0.7
TITLE_BLOCK_MAX_LEN = 400


@dataclass
class TitleBlock:
    """The four fields a title-block parser produces."""

    title: str
    subtitle: str | None
    pope: str
    salutation: str


# ============================================================================
# Markup helpers — shared HTML-walking infrastructure
# ============================================================================


def is_empty(p: LexborNode) -> bool:
    """True for ``<p>`` elements with no rendered text (or just ``&nbsp;``)."""
    text = p.text(deep=True, strip=True)
    return text in ("", "\xa0")


def split_on_breaks(p: LexborNode) -> list[str]:
    """Return the text lines of a ``<p>`` split on its ``<br />`` elements."""
    lines: list[str] = []
    buf: list[str] = []

    def emit() -> None:
        if buf:
            lines.append("".join(buf))
            buf.clear()

    def walk(node: LexborNode) -> None:
        for child in node.iter(include_text=True):
            if child.tag == "br":
                emit()
            elif child.tag == "-text":
                buf.append(child.text() or "")
            else:
                walk(child)

    walk(p)
    emit()
    return lines


def node_to_markdown(node: LexborNode) -> str:
    """Convert a paragraph node's inline content to project-flavored Markdown.

    Footnote references collapse to ``[^N]``. Italic spans become ``*X*``,
    bold becomes ``**X**``. Anchors that aren't footnote references become
    Markdown links. ``<font>`` and similar presentational wrappers are
    transparently unwrapped.
    """
    parts: list[str] = []
    _emit_inline(node, parts)
    return _tidy("".join(parts))


def _emit_inline(node: LexborNode, out: list[str]) -> None:  # noqa: PLR0912
    for child in node.iter(include_text=True):
        if child.tag == "-text":
            out.append(child.text() or "")
        elif child.tag == "br":
            out.append(" ")
        elif child.tag in ("i", "em"):
            inner: list[str] = []
            _emit_inline(child, inner)
            _emit_wrapped(inner, "*", out)
        elif child.tag in ("b", "strong"):
            inner = []
            _emit_inline(child, inner)
            _emit_wrapped(inner, "**", out)
        elif child.tag == "a":
            href = child.attributes.get("href") or ""
            body_ref = FOOTNOTE_BODY_HREF_RE.search(href)
            # FOOTNOTE_BODY_HREF_RE matches both ``_ftn1`` and ``_ftnref1``
            # because both end in digits — distinguish by checking the
            # presence of ``ref`` in the matched substring.
            def_ref = FOOTNOTE_DEF_HREF_RE.search(href)
            if def_ref is not None:
                body_ref = None
            if body_ref is not None:
                out.append(f"[^{body_ref.group(1)}]")
                continue
            if def_ref is not None:
                inner = []
                _emit_inline(child, inner)
                out.append("".join(inner))
                continue
            inner = []
            _emit_inline(child, inner)
            text = "".join(inner).strip()
            if not text:
                continue
            href_attr = child.attributes.get("href") or ""
            if href_attr:
                out.append(f"[{text}]({href_attr})")
            else:
                out.append(text)
        elif child.tag in ("sup", "sub", "font", "u", "span"):
            _emit_inline(child, out)
        else:
            _emit_inline(child, out)


def _emit_wrapped(inner: list[str], marker: str, out: list[str]) -> None:
    """Wrap *inner* in *marker* while preserving outer whitespace.

    The vatican.va HTML frequently puts the trailing space *inside* the
    formatting tag (``<i>Corpus Inscriptionum Latinarum </i>VI``). Without
    this, the emitted Markdown would be ``*Corpus Inscriptionum Latinarum*VI``,
    gluing the words together.
    """
    raw = "".join(inner)
    if not raw.strip():
        return
    leading = raw[: len(raw) - len(raw.lstrip())]
    trailing = raw[len(raw.rstrip()) :]
    core = raw.strip()
    out.append(f"{leading}{marker}{core}{marker}{trailing}")


_WHITESPACE_RE = re.compile(r"[ \t\xa0]+")
_HYPHEN_BREAK_RE = re.compile(r"(\w)-\s+(\w)")
_BRACKETED_FOOTNOTE_RE = re.compile(r"\[\s*\[\^(\d+)\]\s*\]")


def _tidy(text: str) -> str:
    text = html.unescape(text)
    text = text.replace("\xa0", " ")
    text = _WHITESPACE_RE.sub(" ", text)
    text = _HYPHEN_BREAK_RE.sub(r"\1\2", text)
    text = _BRACKETED_FOOTNOTE_RE.sub(r"[^\1]", text)
    text = re.sub(r"\*\*\s+\*\*", " ", text)
    text = re.sub(r"\*\s+\*", " ", text)
    return text.strip()


def strip_inline_markup(s: str) -> str:
    """Remove asterisk markers so heading text can be inspected as plain text."""
    return re.sub(r"\*+", "", s).strip()


def extract_paragraph_number(text: str) -> tuple[int | None, str]:
    """If *text* starts with ``"N. "``, return ``(N, rest)``; else ``(None, text)``."""
    m = PARAGRAPH_NUMBER_RE.match(text)
    if m is None:
        return None, text
    return int(m.group(1)), text[m.end() :].strip()


def parse_dateline_date(text: str) -> date | None:
    """Pull the day/month/year out of a ``Given in X, on Day Month, ..., Year`` line."""
    plain = strip_inline_markup(text)
    m = DATE_RE.search(plain)
    if m is None:
        return None
    return date(int(m.group(3)), _MONTHS[m.group(2).lower()], int(m.group(1)))


# ---- title-casing utilities (used by parse_title_lines) ---------------

_SMALL_WORDS = {
    "and", "or", "of", "the", "to", "in", "for", "on", "a", "an",
    "at", "by", "as", "with", "from",
}  # fmt: skip


def title_case(text: str) -> str:
    """Title-case while preserving Roman numerals and small connecting words.

    The "capitalize" step finds the first alphabetic character in the word
    so that punctuation prefixes like an opening curly quote in
    ``"LAUDATO`` don't leave the actual ``l`` un-capitalized.
    """
    words = text.split()
    out: list[str] = []
    for i, word in enumerate(words):
        if _is_roman_numeral(word):
            out.append(word.upper())
            continue
        # Strip the alphabetic-only-comparison form to test small-words
        # membership.
        alpha = "".join(c for c in word if c.isalpha())
        lowered_alpha = alpha.lower()
        if 0 < i < len(words) - 1 and lowered_alpha in _SMALL_WORDS:
            out.append(word.lower())
            continue
        out.append(_capitalize_first_letter(word.lower()))
    return " ".join(out)


def _capitalize_first_letter(word: str) -> str:
    """Uppercase the first alphabetic character of *word*, leaving leading
    punctuation (``"laudato`` → ``"Laudato``) untouched.
    """
    for i, c in enumerate(word):
        if c.isalpha():
            return word[:i] + c.upper() + word[i + 1 :]
    return word


def _is_roman_numeral(word: str) -> bool:
    return bool(ROMAN_RE.match(word)) and word.upper() == word


_CHAPTER_WORDS = {
    "ONE": "I", "TWO": "II", "THREE": "III", "FOUR": "IV", "FIVE": "V",
    "SIX": "VI", "SEVEN": "VII", "EIGHT": "VIII", "NINE": "IX", "TEN": "X",
}  # fmt: skip


# ============================================================================
# Strategy heuristics — each maps to one Strategy field
# ============================================================================


def find_body_container(tree: LexborHTMLParser) -> LexborNode | None:
    """**Strategy.find_body** — pick the ``div.vaticanrichtext`` holding the body.

    Vatican.va pages embed multiple decorative wrappers with the same class
    (abstract summary, empty container). The real body is whichever has the
    largest ``<p>`` count.
    """
    candidates = tree.css("div.vaticanrichtext")
    if not candidates:
        return None
    return max(candidates, key=lambda node: len(node.css("p")))


def find_title_paragraph(tree: LexborHTMLParser, body: LexborNode) -> LexborNode | None:
    """**Strategy.find_title** — locate the centered title-rubric paragraph.

    The rubric ``ENCYCLICAL LETTER`` appears on every encyclical's title
    page and nowhere else in the body, which makes it a reliable beacon
    regardless of whether the title block lives in the body container
    (Spe Salvi) or in a separate ``div.vaticanrichtext.abstract``
    (Magnifica Humanitas).
    """
    for candidate in tree.css("div.vaticanrichtext p"):
        plain = candidate.text(deep=True, strip=True).upper()
        if "ENCYCLICAL LETTER" in plain and len(plain) < TITLE_BLOCK_MAX_LEN:
            return candidate
    # Last resort: first non-empty paragraph in the body container.
    for p in body.iter(include_text=False):
        if p.tag == "p" and not is_empty(p):
            return p
    return None


def parse_title_lines(lines: list[str]) -> TitleBlock:
    """**Strategy.parse_title_lines** — extract title/subtitle/pope/salutation.

    Lines come in stripped of ``&nbsp;`` and outer whitespace, already split
    on ``<br>``. We skip the rubric labels (``ENCYCLICAL LETTER``, ``OF HIS
    HOLINESS``), then take the first remaining line as the title, the next
    as the pope's name (stripping any ``POPE `` prefix), and distinguish a
    salutation block (``To the Bishops, Priests…``) from a multi-line
    subtitle (``On Safeguarding the Human Person / In the Time of Artificial
    Intelligence``) by the presence of a ``TO `` opener.
    """
    title = ""
    pope = ""
    trailing: list[str] = []

    for line in lines:
        text = strip_inline_markup(line)
        upper = text.upper()
        if upper == "ENCYCLICAL LETTER":
            continue
        # The "by-whom" rubric line varies by pontificate: Benedict and Leo
        # use "OF HIS HOLINESS" or "OF THE SUPREME PONTIFF"; Francis uses
        # "OF THE HOLY FATHER". Match any of them so the pope's name lands
        # in the right slot.
        if (
            upper.startswith("OF THE SUPREME PONTIFF")
            or upper.startswith("OF HIS HOLINESS")
            or upper.startswith("OF THE HOLY FATHER")
        ):
            continue
        if not title:
            title = title_case(text)
            continue
        if not pope:
            cleaned = re.sub(r"(?i)^pope\s+", "", text)
            pope = title_case(cleaned)
            continue
        trailing.append(text)

    if not trailing:
        return TitleBlock(title=title, subtitle=None, pope=pope, salutation="")

    has_salutation = any(line.upper().startswith("TO ") for line in trailing)
    if has_salutation:
        subtitle = title_case(trailing.pop())
        salutation = ", ".join(title_case(s) for s in trailing)
    else:
        subtitle = title_case(" ".join(trailing))
        salutation = ""

    return TitleBlock(title=title, subtitle=subtitle, pope=pope, salutation=salutation)


_FOOTNOTE_DEF_ANCHOR_NAME_RE = re.compile(r"^_ftn\d+$")


def _is_footnote_def_paragraph(p: LexborNode) -> bool:
    """A paragraph is a footnote definition if it contains an anchor with
    ``name="_ftn{N}"`` (the back-link target) — the marker that uniquely
    identifies definitions across every vatican.va layout we've seen.

    Body paragraphs cite footnotes via ``name="_ftnref{N}"`` (note the
    ``ref``), so that pattern does not match here.
    """
    for anchor in p.css("a"):
        name = anchor.attributes.get("name") or ""
        if _FOOTNOTE_DEF_ANCHOR_NAME_RE.match(name):
            return True
    return False


def split_body_and_footnotes(
    tree: LexborHTMLParser, container: LexborNode
) -> tuple[list[LexborNode], list[LexborNode]]:
    """**Strategy.split_body_and_footnotes** — separate the encyclical body
    from its footnote definitions.

    Identifies footnote definitions by the ``<a name="_ftnN">`` back-link
    anchor each one carries. This works regardless of how the page wraps
    them: as direct children of the body container with an ``<hr/>``
    above (Spe Salvi), nested in ``<div id="ftnN">`` siblings (Laudato
    Si'), or sitting in a ``p.MsoFootnoteText`` after an ``<hr/>``
    buried inside a ``<font>`` (Magnifica Humanitas, Lumen Fidei).

    Walks every ``<p>`` descendant of the container in document order.
    The first paragraph that matches the def signature ends the body
    section and starts the footnote section.
    """
    body: list[LexborNode] = []
    footnotes: list[LexborNode] = []
    for p in container.css("p"):
        if _is_footnote_def_paragraph(p):
            footnotes.append(p)
        elif not footnotes:
            body.append(p)
        # If we've already entered the footnote section but encounter a
        # non-def paragraph (e.g. a blank separator), skip it.
    # If the container didn't carry the footnotes at all, fall back to the
    # whole document — some pages park them in a sibling div with the
    # class ``MsoFootnoteText``.
    if not footnotes:
        footnotes = [p for p in tree.css("p.MsoFootnoteText") if _is_footnote_def_paragraph(p)]
    return body, footnotes


def drop_table_of_contents(body_ps: list[LexborNode]) -> list[LexborNode]:
    """**Strategy.drop_preamble** — trim leading TOC paragraphs.

    Recent encyclicals (Leo XIV onward) prepend a table of contents to the
    body container: alternating chapter labels and concatenated subsection
    listings. The real body always begins with a numbered paragraph
    (``1. ...``) — pivot there, keeping the heading immediately above if
    present so paragraph 1 still has a section.
    """
    for i, p in enumerate(body_ps):
        if is_empty(p):
            continue
        text = p.text(deep=True, strip=True)
        if PARAGRAPH_NUMBER_RE.match(text):
            for j in range(i - 1, -1, -1):
                if is_empty(body_ps[j]):
                    continue
                return body_ps[j:]
            return body_ps[i:]
    return body_ps


def keep_all(body_ps: list[LexborNode]) -> list[LexborNode]:
    """**Strategy.drop_preamble** alternative — keep every paragraph.

    Useful as a fallback when the default TOC heuristic would discard too
    much (e.g. an encyclical without numbered paragraphs).
    """
    return body_ps


def is_heading(p: LexborNode) -> bool:
    """**Strategy.is_heading** — True iff the paragraph carries no top-level
    text node of its own (i.e. all text is inside ``<b>``/``<i>``/``<font>``
    /``<em>``/``<strong>`` wrappers).
    """
    for child in p.iter(include_text=True):
        if child.tag == "-text" and (child.text() or "").strip(" \xa0\n\t"):
            return False
    return True


def chapter_preamble_numeral(text: str) -> str | None:
    """**Strategy.chapter_preamble_numeral** — return the Roman-numeral form
    if *text* is a chapter preamble like ``CHAPTER ONE`` / ``CHAPTER 1`` /
    ``CHAPTER I`` / ``PART ONE``.
    """
    stripped = text.strip().rstrip(".:")
    upper = stripped.upper()
    for prefix in ("CHAPTER ", "PART "):
        if upper.startswith(prefix):
            rest = upper[len(prefix) :].strip()
            if rest in _CHAPTER_WORDS:
                return _CHAPTER_WORDS[rest]
            if ROMAN_RE.match(rest):
                return rest.rstrip(".")
            if rest.isdigit():
                return rest
    return None


def find_dateline_index(body_ps: list[LexborNode]) -> int | None:
    """**Strategy.find_dateline_index** — locate the closing italic dateline.

    Search from the end of the body backwards: the dateline is the last
    paragraph that begins ``Given in`` or ``Given at`` (the conventional
    Roman dating formula).
    """
    for i in range(len(body_ps) - 1, -1, -1):
        p = body_ps[i]
        if is_empty(p):
            continue
        text = p.text(deep=True, strip=True)
        if text.startswith("Given in") or text.startswith("Given at"):
            return i
    return None


def looks_like_signature(text: str) -> bool:
    """**Strategy.looks_like_signature** — True for paragraphs that look like
    the papal signature line (short, predominantly uppercase).
    """
    stripped = strip_inline_markup(text).strip()
    if not stripped or len(stripped) > SIGNATURE_MAX_LEN:
        return False
    letters = [c for c in stripped if c.isalpha()]
    if not letters:
        return False
    upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
    return upper_ratio > SIGNATURE_UPPERCASE_RATIO
