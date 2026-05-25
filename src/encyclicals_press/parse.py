"""HTML -> :class:`Encyclical` parser for vatican.va documents.

The vatican.va HTML is loose: no semantic headings, no reliable CSS classes,
paragraph numbers as leading plain text inside ``<p>`` elements, footnote refs
as ``<sup>``-style anchors to ``#_ftn{N}``. Parse what's there; don't try to be
a generalized HTML-to-anything converter.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import date

from selectolax.lexbor import LexborHTMLParser, LexborNode

from ._url_map import url_for
from .schema import Encyclical, Footnote, Paragraph

PARAGRAPH_NUMBER_RE = re.compile(r"^\s*(\d{1,4})\.\s+")
# Body footnote ref anchors: <a href="#_ftn1" name="_ftnref1">[1]</a> — the
# href targets the footnote definition.
FOOTNOTE_BODY_HREF_RE = re.compile(r"^_ftn(\d+)$")
# Footnote def back-links: <a href="#_ftnref1" name="_ftn1">[1]</a> — the
# href targets the body ref so the reader can navigate back.
FOOTNOTE_DEF_HREF_RE = re.compile(r"^_ftnref(\d+)$")
DATE_RE = re.compile(
    r"on (\d{1,2}) (January|February|March|April|May|June|July|August|"
    r"September|October|November|December)\b.*?(\d{4})",
    re.IGNORECASE,
)
INLINE_FORMATTING_TAGS = {"b", "strong", "i", "em", "font", "sup", "sub", "u"}

SIGNATURE_MAX_LEN = 60
SIGNATURE_UPPERCASE_RATIO = 0.7

_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


@dataclass
class _TitleBlock:
    title: str
    subtitle: str | None
    pope: str
    salutation: str


def parse(html_source: str, slug: str, source_url: str | None = None) -> Encyclical:
    """Parse vatican.va HTML into an :class:`Encyclical`."""

    tree = LexborHTMLParser(html_source)
    container = _find_body_container(tree)
    if container is None:
        raise ValueError("body container 'div.vaticanrichtext' not found in HTML")

    title_p = _find_title_paragraph(tree, container)
    if title_p is None:
        raise ValueError("title paragraph not found in HTML")
    title_block = _parse_title_block(title_p)

    body_ps, footnote_ps = _split_on_hr(container)
    if not body_ps:
        raise ValueError("no <p> elements found in body container")
    # If the title came from the body container's first paragraph (older layout
    # like Spe Salvi), drop it. Otherwise the title lives in a separate div
    # and the whole body container is available for parsing.
    if title_p is body_ps[0]:
        body_ps = body_ps[1:]
    body_ps = _drop_table_of_contents(body_ps)

    paragraphs, closing, promulgated = _parse_body(body_ps)

    # The post-<hr/> footnote definitions may be wrapped in extra <div>s on
    # newer vatican.va pages, so fall back to a CSS query when the inline
    # split came up empty.
    if not footnote_ps:
        footnote_ps = tree.css("p.MsoFootnoteText")
    footnotes = _parse_footnotes(footnote_ps)

    incipit = _extract_incipit(paragraphs)

    for text in closing:
        paragraphs.append(Paragraph(number=None, section=None, text=text))

    return Encyclical(
        slug=slug,
        title=title_block.title,
        subtitle=title_block.subtitle,
        pope=title_block.pope,
        promulgated=promulgated,
        incipit=incipit,
        salutation=title_block.salutation,
        paragraphs=paragraphs,
        footnotes=footnotes,
        source_url=source_url or url_for(slug),
    )


def _find_body_container(tree: LexborHTMLParser) -> LexborNode | None:
    """Pick the ``div.vaticanrichtext`` that actually holds the encyclical body.

    Vatican.va pages embed several decorative wrappers with the same class
    (abstract summary, empty container). The real body is whichever has the
    largest ``<p>`` count.
    """
    candidates = tree.css("div.vaticanrichtext")
    if not candidates:
        return None
    return max(candidates, key=lambda node: len(node.css("p")))


def _find_title_paragraph(tree: LexborHTMLParser, body: LexborNode) -> LexborNode | None:
    """Locate the centered title-rubric paragraph.

    Older documents (e.g. *Spe Salvi*) put the title block in the first
    paragraph of the body container. Newer ones (e.g. *Magnifica Humanitas*)
    put it in a separate ``div.vaticanrichtext.abstract`` ahead of the body.
    Detect by looking for "ENCYCLICAL LETTER" in the rendered text — that
    rubric label appears on every encyclical's title page and nowhere else.
    """
    for candidate in tree.css("div.vaticanrichtext p"):
        plain = candidate.text(deep=True, strip=True).upper()
        if "ENCYCLICAL LETTER" in plain and len(plain) < 400:  # noqa: PLR2004
            return candidate
    # Last resort: first non-empty paragraph in the body container.
    for p in body.iter(include_text=False):
        if p.tag == "p" and not _is_empty(p):
            return p
    return None


def _drop_table_of_contents(body_ps: list[LexborNode]) -> list[LexborNode]:
    """Trim leading TOC paragraphs from documents that include one.

    Recent encyclicals (Leo XIV onward) prepend a table of contents to the
    body container: alternating chapter labels and concatenated subsection
    listings, ending in a blank paragraph. The real body always begins with
    a section heading (e.g. ``INTRODUCTION``) immediately followed by a
    numbered paragraph (``1. ...``). Find that pivot.
    """
    for i, p in enumerate(body_ps):
        if _is_empty(p):
            continue
        text = p.text(deep=True, strip=True)
        if PARAGRAPH_NUMBER_RE.match(text):
            # Keep the heading immediately above, if any, plus everything after.
            for j in range(i - 1, -1, -1):
                if _is_empty(body_ps[j]):
                    continue
                return body_ps[j:]
            return body_ps[i:]
    return body_ps


def _split_on_hr(container: LexborNode) -> tuple[list[LexborNode], list[LexborNode]]:
    """Walk direct children, splitting <p> elements into body and footnotes at the <hr />."""
    body: list[LexborNode] = []
    footnotes: list[LexborNode] = []
    in_footnotes = False
    for child in container.iter(include_text=False):
        if child.tag == "hr":
            in_footnotes = True
            continue
        if child.tag != "p":
            continue
        (footnotes if in_footnotes else body).append(child)
    return body, footnotes


def _parse_title_block(p: LexborNode) -> _TitleBlock:
    """Extract title, subtitle, pope, salutation from the centered title <p>."""
    lines = _split_on_breaks(p)
    lines = [line for line in (raw.strip(" \xa0") for raw in lines) if line]

    title = ""
    subtitle: str | None = None
    pope = ""
    trailing: list[str] = []

    for line in lines:
        text = _strip_inline_markup(line)
        upper = text.upper()
        if upper == "ENCYCLICAL LETTER":
            continue
        if upper.startswith("OF THE SUPREME PONTIFF") or upper.startswith("OF HIS HOLINESS"):
            continue
        if not title:
            title = _title_case(text)
            continue
        if not pope:
            # Strip the optional "POPE " prefix newer documents prepend.
            cleaned = re.sub(r"(?i)^pope\s+", "", text)
            pope = _title_case(cleaned)
            continue
        trailing.append(text)

    if not trailing:
        return _TitleBlock(title=title, subtitle=None, pope=pope, salutation="")

    # Distinguish a salutation block ("To the Bishops, Priests...") from a
    # multi-line subtitle ("On Safeguarding the Human Person / In the
    # Time of Artificial Intelligence"). Salutations always open with "To".
    has_salutation = any(line.upper().startswith("TO ") for line in trailing)
    if has_salutation:
        subtitle = _title_case(trailing.pop())
        salutation = ", ".join(_title_case(s) for s in trailing)
    else:
        subtitle = _title_case(" ".join(trailing))
        salutation = ""

    return _TitleBlock(title=title, subtitle=subtitle, pope=pope, salutation=salutation)


def _parse_body(  # noqa: PLR0912, PLR0915
    body_ps: list[LexborNode],
) -> tuple[list[Paragraph], list[str], date]:
    """Parse numbered body and detect the closing dateline + signature.

    Returns ``(paragraphs, closing_lines, promulgated)`` where ``closing_lines``
    contains the dateline and signature as separate Markdown strings (so they
    can be rendered as distinct trailing paragraphs).
    """

    paragraphs: list[Paragraph] = []
    current_section: str | None = None
    pending_chapter: str | None = None
    pending_chapter_titles: list[str] = []
    closing: list[str] = []
    promulgated: date | None = None

    def flush_chapter() -> str | None:
        nonlocal pending_chapter, pending_chapter_titles
        if pending_chapter is None:
            return None
        title = " ".join(pending_chapter_titles).strip()
        combined = f"{pending_chapter}. {title}" if title else pending_chapter + "."
        pending_chapter = None
        pending_chapter_titles = []
        return combined

    dateline_idx = _find_dateline(body_ps)
    body_range = body_ps[:dateline_idx] if dateline_idx is not None else body_ps

    for p in body_range:
        if _is_empty(p):
            continue
        md = _node_to_markdown(p)
        if not md.strip():
            continue
        number, body_text = _extract_paragraph_number(md)
        if number is not None:
            chapter_section = flush_chapter()
            if chapter_section is not None:
                current_section = chapter_section
            paragraphs.append(Paragraph(number=number, section=current_section, text=body_text))
            continue
        if _is_heading(p):
            heading_text = _strip_inline_markup(md)
            chapter_numeral = _chapter_preamble_numeral(heading_text)
            if chapter_numeral is not None:
                # If a previous CHAPTER had no body paragraphs yet (shouldn't
                # happen in practice), flush it to current_section so it's
                # not silently dropped.
                chapter_section = flush_chapter()
                if chapter_section is not None:
                    current_section = chapter_section
                pending_chapter = chapter_numeral
                continue
            if pending_chapter is not None:
                # Multi-line chapter title (e.g. ``CHAPTER THREE`` /
                # ``TECHNOLOGY AND DOMINANCE.`` / ``THE GRANDEUR OF HUMANITY``).
                pending_chapter_titles.append(_title_case(heading_text).rstrip("."))
            else:
                current_section = heading_text
            continue
        # Continuation prose with no number.
        chapter_section = flush_chapter()
        if chapter_section is not None:
            current_section = chapter_section
        paragraphs.append(Paragraph(number=None, section=current_section, text=md))

    if dateline_idx is not None:
        dateline_p = body_ps[dateline_idx]
        dateline_md = _node_to_markdown(dateline_p).strip()
        promulgated = _parse_dateline_date(dateline_md)
        closing.append(dateline_md)
        # Skip blank paragraphs vatican.va sometimes inserts between dateline
        # and signature (Magnifica Humanitas has one).
        for sig_p in body_ps[dateline_idx + 1 :]:
            if _is_empty(sig_p):
                continue
            sig_md = _node_to_markdown(sig_p).strip()
            if sig_md and _looks_like_signature(sig_md):
                closing.append(sig_md)
            break

    if promulgated is None:
        raise ValueError("could not extract promulgation date from body")

    return paragraphs, closing, promulgated


def _parse_footnotes(footnote_ps: list[LexborNode]) -> list[Footnote]:
    footnotes: list[Footnote] = []
    for p in footnote_ps:
        if _is_empty(p):
            continue
        md = _node_to_markdown(p)
        # Footnote definitions start with [N] (now rendered as plain text by
        # the markdown converter, which has stripped the back-link anchor).
        m = re.match(r"^\s*\[(\d+)\]\s*(.*)$", md, re.DOTALL)
        if not m:
            continue
        number = int(m.group(1))
        text = m.group(2).strip()
        footnotes.append(Footnote(number=number, text=text))
    return footnotes


# ---- node walking helpers ----------------------------------------------------


def _is_empty(p: LexborNode) -> bool:
    text = p.text(deep=True, strip=True)
    return text in ("", "\xa0")


def _is_heading(p: LexborNode) -> bool:
    """True iff the paragraph's text is entirely inside <b>/<i>/<font>/<em>/<strong>.

    A heading carries no top-level text node of its own.
    """
    for child in p.iter(include_text=True):
        if child.tag == "-text" and (child.text() or "").strip(" \xa0\n\t"):
            return False
    # Some content exists (we've already filtered _is_empty before calling).
    return True


def _split_on_breaks(p: LexborNode) -> list[str]:
    """Return text lines from a <p> by splitting on <br /> elements."""
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


def _node_to_markdown(node: LexborNode) -> str:
    """Convert a paragraph node's inline content to Markdown-flavored text.

    Footnote references collapse to ``[^N]``. Italic spans become ``*X*``,
    bold becomes ``**X**``. Anchors to other vatican.va pages (scripture
    citations etc.) become Markdown links. ``<font>`` wrappers and stray
    formatting are stripped.
    """
    parts: list[str] = []
    _emit_inline(node, parts)
    return _tidy(_join_markdown(parts))


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
            href = (child.attributes.get("href") or "").lstrip("#")
            body_ref = FOOTNOTE_BODY_HREF_RE.match(href)
            def_ref = FOOTNOTE_DEF_HREF_RE.match(href)
            if body_ref is not None:
                out.append(f"[^{body_ref.group(1)}]")
                continue
            if def_ref is not None:
                # Back-link from the footnote definition: keep the visible
                # ``[N]`` so the footnote parser can recover the number.
                inner = []
                _emit_inline(child, inner)
                out.append(_join_markdown(inner))
                continue
            inner = []
            _emit_inline(child, inner)
            text = _join_markdown(inner).strip()
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
            # Unknown inline; recurse and emit children.
            _emit_inline(child, out)


def _join_markdown(parts: list[str]) -> str:
    return "".join(parts)


def _emit_wrapped(inner: list[str], marker: str, out: list[str]) -> None:
    """Emit ``inner`` wrapped in ``marker`` while preserving outer whitespace.

    The vatican.va HTML frequently puts the trailing space *inside* the
    formatting tag (``<i>Corpus Inscriptionum Latinarum </i>VI``). If we
    naively strip and re-emit, ``*Corpus Inscriptionum Latinarum*VI`` glues
    the words together. Capture the leading/trailing whitespace and emit
    it outside the markers instead.
    """
    raw = _join_markdown(inner)
    if not raw.strip():
        return
    leading = raw[: len(raw) - len(raw.lstrip())]
    trailing = raw[len(raw.rstrip()) :]
    core = raw.strip()
    out.append(f"{leading}{marker}{core}{marker}{trailing}")


_WHITESPACE_RE = re.compile(r"[ \t\xa0]+")
_HYPHEN_BREAK_RE = re.compile(r"(\w)-\s+(\w)")
# Vatican.va wraps body footnote anchors in literal "[...]" — e.g.
# ``Saint Thomas Aquinas[<a href="#_ftn4">4</a>],``. After collapsing the
# anchor to [^N], the surrounding brackets remain. Tighten them.
_BRACKETED_FOOTNOTE_RE = re.compile(r"\[\s*\[\^(\d+)\]\s*\]")


def _tidy(text: str) -> str:
    text = html.unescape(text)
    text = text.replace("\xa0", " ")
    text = _WHITESPACE_RE.sub(" ", text)
    # The vatican.va prints carry print-edition hyphenated word breaks
    # like "Prot- estant" inside body text. Re-join them.
    text = _HYPHEN_BREAK_RE.sub(r"\1\2", text)
    text = _BRACKETED_FOOTNOTE_RE.sub(r"[^\1]", text)
    # Collapse "** **" -> " " when bold/italic spans abutted whitespace.
    text = re.sub(r"\*\*\s+\*\*", " ", text)
    text = re.sub(r"\*\s+\*", " ", text)
    return text.strip()


def _strip_inline_markup(s: str) -> str:
    return re.sub(r"\*+", "", s).strip()


def _extract_paragraph_number(text: str) -> tuple[int | None, str]:
    m = PARAGRAPH_NUMBER_RE.match(text)
    if m is None:
        return None, text
    number = int(m.group(1))
    body = text[m.end() :]
    return number, body.strip()


def _find_dateline(body_ps: list[LexborNode]) -> int | None:
    for i in range(len(body_ps) - 1, -1, -1):
        p = body_ps[i]
        if _is_empty(p):
            continue
        text = p.text(deep=True, strip=True)
        if text.startswith("Given in") or text.startswith("Given at"):
            return i
    return None


def _looks_like_signature(text: str) -> bool:
    stripped = _strip_inline_markup(text).strip()
    if not stripped or len(stripped) > SIGNATURE_MAX_LEN:
        return False
    # Mostly uppercase letters — the closing ``BENEDICTUS PP. XVI`` style.
    letters = [c for c in stripped if c.isalpha()]
    if not letters:
        return False
    upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
    return upper_ratio > SIGNATURE_UPPERCASE_RATIO


def _parse_dateline_date(text: str) -> date | None:
    plain = _strip_inline_markup(text)
    m = DATE_RE.search(plain)
    if m is None:
        return None
    day = int(m.group(1))
    month = _MONTHS[m.group(2).lower()]
    year = int(m.group(3))
    return date(year, month, day)


def _extract_incipit(paragraphs: list[Paragraph]) -> str:
    """The opening Latin phrase used as the title-page incipit."""
    for p in paragraphs:
        if p.number != 1:
            continue
        m = re.search(r"\*([^*]+)\*", p.text)
        if m:
            return _title_case(m.group(1).strip().rstrip(",.;"))
        break
    return ""


_SMALL_WORDS = {
    "and",
    "or",
    "of",
    "the",
    "to",
    "in",
    "for",
    "on",
    "a",
    "an",
    "at",
    "by",
    "as",
    "with",
    "from",
}


def _title_case(text: str) -> str:
    """Title-case a string while preserving Roman numerals and small words."""
    words = text.split()
    out: list[str] = []
    for i, word in enumerate(words):
        if _is_roman_numeral(word):
            out.append(word.upper())
            continue
        lowered = word.lower()
        if 0 < i < len(words) - 1 and lowered in _SMALL_WORDS:
            out.append(lowered)
            continue
        out.append(lowered[:1].upper() + lowered[1:])
    return " ".join(out)


_ROMAN_RE = re.compile(r"^[IVXLCDM]+\.?$", re.IGNORECASE)


def _is_roman_numeral(word: str) -> bool:
    return bool(_ROMAN_RE.match(word)) and word.upper() == word


_CHAPTER_WORDS = {
    "ONE": "I",
    "TWO": "II",
    "THREE": "III",
    "FOUR": "IV",
    "FIVE": "V",
    "SIX": "VI",
    "SEVEN": "VII",
    "EIGHT": "VIII",
    "NINE": "IX",
    "TEN": "X",
}


def _chapter_preamble_numeral(text: str) -> str | None:
    """Return the Roman-numeral form if *text* is a chapter preamble.

    Recognises ``CHAPTER ONE``, ``CHAPTER 1``, ``CHAPTER I``, and ``PART ONE``
    style preambles that newer vatican.va documents emit as a separate
    paragraph just above the actual chapter title.
    """
    stripped = text.strip().rstrip(".:")
    upper = stripped.upper()
    for prefix in ("CHAPTER ", "PART "):
        if upper.startswith(prefix):
            rest = upper[len(prefix) :].strip()
            if rest in _CHAPTER_WORDS:
                return _CHAPTER_WORDS[rest]
            if _ROMAN_RE.match(rest):
                return rest.rstrip(".")
            if rest.isdigit():
                return rest
    return None
