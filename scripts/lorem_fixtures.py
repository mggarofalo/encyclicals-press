"""Replace encyclical body prose in committed fixtures with lorem ipsum.

The cached vatican.va HTML in ``tests/fixtures/*.html`` contains
translations © Libreria Editrice Vaticana. Even though the project
isn't redistributing them commercially, keeping committed copies of
that text invites avoidable copyright friction.

This script walks each fixture and substitutes the *prose* — body
paragraph sentences and footnote-definition citations — with lorem
ipsum. Everything else stays: the title block (with its real title,
pope, and date), section headings (short factual labels), the
dateline + signature, paragraph numbers, footnote anchor structure,
scripture-link anchors. The result still exercises every parser
heuristic the project ships, but no copyrighted prose travels with it.

Users who want to typeset real encyclicals run ``encyclicals fetch``
against the canonical vatican.va URL — their working tree fills in
with the actual translation, the committed repository keeps lorem.

Run::

    uv run --with beautifulsoup4 python scripts/lorem_fixtures.py

Idempotent: re-running produces deterministic lorem (seeded per slug)
so re-runs don't churn the diff.
"""

from __future__ import annotations

import random
import re
import sys
from pathlib import Path

try:
    from bs4 import BeautifulSoup, NavigableString, Tag
except ImportError:
    sys.exit(
        "beautifulsoup4 is required: rerun with "
        "`uv run --with beautifulsoup4 python scripts/lorem_fixtures.py`"
    )

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"

LOREM_WORDS = (
    "lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod "
    "tempor incididunt ut labore et dolore magna aliqua enim ad minim veniam "
    "quis nostrud exercitation ullamco laboris nisi aliquip ex ea commodo "
    "consequat duis aute irure in reprehenderit voluptate velit esse cillum "
    "eu fugiat nulla pariatur excepteur sint occaecat cupidatat non proident "
    "sunt culpa qui officia deserunt mollit anim id est laborum"
).split()

# Strict pattern: matches a number-period prefix only when followed by
# something that looks like the start of prose. Used to *classify* a
# paragraph (does it open with ``N. ``?), against the full concatenated
# text of the <p>.
PARAGRAPH_NUMBER_RE = re.compile(r"^\s*(\d{1,4})\.\s*(?=[A-Za-z“”\"‘’'(\[*])")

# Lenient pattern: matches a number-period prefix at the start of a
# *text node* even if nothing follows (e.g. ``"1. "`` is the entire
# text node because the prose continues inside an <i> or <a> sibling).
# Once we already know the paragraph is numbered (via PARAGRAPH_NUMBER_RE
# on the full text), use this to preserve the prefix without losing it
# to the lorem substitution.
PARAGRAPH_PREFIX_RE = re.compile(r"^\s*(\d{1,4})\.\s*")


def main() -> int:
    fixtures = sorted(FIXTURES_DIR.glob("*.html"))
    if not fixtures:
        sys.exit(f"no fixtures found at {FIXTURES_DIR}")
    for path in fixtures:
        slug = path.stem
        print(f"lorem-ipsuming {path.relative_to(FIXTURES_DIR.parent.parent)}")
        process(path, slug)
    return 0


def process(path: Path, slug: str) -> None:
    raw = path.read_text(encoding="utf-8")
    soup = BeautifulSoup(raw, "html.parser")
    rng = random.Random(slug)

    body_container = _pick_body_container(soup)
    if body_container is None:
        print(f"  skip: no body container found", file=sys.stderr)
        return

    body_seen_dateline = False
    paragraphs = list(body_container.find_all("p"))
    for p in paragraphs:
        if _is_title_block(p):
            continue
        if _is_section_heading(p):
            continue
        if _is_dateline(p):
            body_seen_dateline = True
            continue
        if body_seen_dateline and _looks_like_signature_text(p):
            continue
        if _is_footnote_def(p):
            _loremise_footnote_def(p, rng)
            continue
        if _has_paragraph_number(p):
            _loremise_paragraph_body(p, rng)
            continue
        # Continuation paragraph (mid-encyclical) — also prose.
        if _is_inside_body_text(p):
            _loremise_paragraph_body(p, rng)

    # Footnote defs also live in separate <p class="MsoFootnoteText"> sometimes,
    # in nested <div>s after the body container. Catch any we haven't already
    # visited (set membership via id()).
    visited = {id(p) for p in paragraphs}
    for p in soup.find_all("p", class_="MsoFootnoteText"):
        if id(p) in visited:
            continue
        if _is_footnote_def(p):
            _loremise_footnote_def(p, rng)
    for p in soup.find_all("p"):
        if id(p) in visited:
            continue
        if _is_footnote_def(p):
            _loremise_footnote_def(p, rng)

    path.write_text(str(soup), encoding="utf-8", newline="\n")


# ---- container + paragraph classification ------------------------------


def _pick_body_container(soup: BeautifulSoup) -> Tag | None:
    candidates = [d for d in soup.find_all("div") if "vaticanrichtext" in (d.get("class") or [])]
    if not candidates:
        return None
    return max(candidates, key=lambda d: len(d.find_all("p")))


def _is_title_block(p: Tag) -> bool:
    text = p.get_text(" ", strip=True).upper()
    return "ENCYCLICAL LETTER" in text and len(text) < 400


def _is_section_heading(p: Tag) -> bool:
    """Headings carry no text outside <b>/<i>/<font>/<em>/<strong>."""
    if _is_empty(p):
        return False
    text = (p.string or "").strip()
    if text:  # has direct text content
        return False
    for child in p.children:
        if isinstance(child, NavigableString):
            if child.strip() not in ("", "\xa0"):
                return False
    # Has content but only inside formatting wrappers.
    return bool(p.get_text(strip=True))


def _is_dateline(p: Tag) -> bool:
    text = p.get_text(" ", strip=True)
    return text.startswith("Given in") or text.startswith("Given at")


def _looks_like_signature_text(p: Tag) -> bool:
    text = p.get_text(" ", strip=True)
    if not text or len(text) > 60:
        return False
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    return sum(1 for c in letters if c.isupper()) / len(letters) > 0.7


def _is_footnote_def(p: Tag) -> bool:
    for a in p.find_all("a"):
        name = a.get("name", "")
        if re.match(r"^_ftn\d+$", name):
            return True
    return False


def _has_paragraph_number(p: Tag) -> bool:
    text = p.get_text(" ", strip=False)
    return bool(PARAGRAPH_NUMBER_RE.match(text))


def _is_empty(p: Tag) -> bool:
    text = p.get_text(strip=True)
    return text in ("", "\xa0")


def _is_inside_body_text(p: Tag) -> bool:
    """Heuristic: a non-numbered, non-heading <p> nestled between body
    paragraphs is continuation prose. We approximate by looking at the
    direct text content: if it has substantive prose (> 60 chars) it's
    treated as continuation; otherwise left alone (could be a stray
    formatting paragraph).
    """
    text = p.get_text(" ", strip=True)
    return len(text) > 60


# ---- the lorem-ipsum substitution itself --------------------------------


def _loremise_paragraph_body(p: Tag, rng: random.Random) -> None:
    """Replace prose in a body paragraph, preserving paragraph number,
    inline formatting structure, and anchors.

    The number-period prefix can span multiple text nodes — vatican.va's
    Laudato Si' splits ``2. Real prose...`` into
    ``<a name="2">2</a>. Real prose...`` so the digit ``"2"`` and the
    period+space ``". "`` are separate text descendants. Walk leading
    nodes until their concatenation matches ``"N. "`` and only lorem
    the part *after* the prefix.
    """
    target_words = _approx_word_count(p)
    text_nodes = _text_nodes_to_loremise(p)
    if not text_nodes:
        return

    nodes_in_prefix, last_prefix_offset = _locate_paragraph_prefix(text_nodes)

    for idx, node in enumerate(text_nodes):
        if nodes_in_prefix > 0 and idx < nodes_in_prefix - 1:
            # Entirely inside the prefix — keep as-is.
            continue
        if nodes_in_prefix > 0 and idx == nodes_in_prefix - 1:
            preserved = str(node)[:last_prefix_offset]
            lorem = _generate_lorem_sentence(
                rng, _portion(target_words, idx + 1, len(text_nodes))
            )
            node.replace_with(preserved + lorem)
            continue
        node.replace_with(
            _generate_lorem_sentence(rng, _portion(target_words, idx + 1, len(text_nodes)))
        )


def _locate_paragraph_prefix(text_nodes: list[NavigableString]) -> tuple[int, int]:
    """Return ``(nodes_in_prefix, last_prefix_offset)`` where:

    * ``nodes_in_prefix`` is the count of leading text nodes that together
      contain the ``"N. "`` paragraph-number prefix (``0`` if no prefix).
    * ``last_prefix_offset`` is the offset *within the last such node*
      where the prefix ends (so the substring up to that index is the
      part to preserve verbatim).
    """
    accumulated = ""
    for i, node in enumerate(text_nodes[:5]):
        accumulated += str(node)
        m = PARAGRAPH_PREFIX_RE.match(accumulated)
        if m is None:
            continue
        target = m.end()
        running = 0
        for j in range(i + 1):
            node_len = len(str(text_nodes[j]))
            if running + node_len >= target:
                return j + 1, target - running
            running += node_len
        return i + 1, len(str(text_nodes[i]))
    return 0, 0


def _loremise_footnote_def(p: Tag, rng: random.Random) -> None:
    """Replace the citation body in a footnote definition. Keep the
    leading anchor (``<a name="_ftnN">[N]</a>``) and any trailing
    structural anchors that link out to source documents.
    """
    text_nodes = _text_nodes_to_loremise(p)
    target_words = _approx_word_count(p)
    for i, node in enumerate(text_nodes):
        # Skip the standalone "[N]" / "N]" label text that some defs carry
        # as a separate text node next to an empty anchor (Fratelli Tutti).
        raw = (node.string or "").strip()
        if re.fullmatch(r"\[?\d+\]?", raw):
            continue
        node.replace_with(
            _generate_lorem_sentence(rng, _portion(target_words, i + 1, len(text_nodes)))
        )


def _text_nodes_to_loremise(p: Tag) -> list[NavigableString]:
    out: list[NavigableString] = []
    for descendant in p.descendants:
        if not isinstance(descendant, NavigableString):
            continue
        # Skip the visible-text inside footnote anchors so the "[N]" label
        # survives — both body refs and def back-links.
        anchor = descendant.find_parent("a")
        if anchor is not None:
            name = anchor.get("name", "")
            if name.startswith("_ftnref") or name.startswith("_ftn"):
                continue
        if (descendant.string or "").strip() in ("", "\xa0"):
            continue
        out.append(descendant)
    return out


def _approx_word_count(p: Tag) -> int:
    text = p.get_text(" ", strip=True)
    return max(8, len(text.split()))


def _portion(total: int, idx: int, n: int) -> int:
    """Distribute *total* words across *n* nodes; this is the size of node *idx* (1-based)."""
    base = total // n
    extra = total % n
    return max(3, base + (1 if idx <= extra else 0))


def _generate_lorem_sentence(rng: random.Random, word_count: int) -> str:
    words = [rng.choice(LOREM_WORDS) for _ in range(word_count)]
    text = " ".join(words)
    text = text[:1].upper() + text[1:]
    if not text.endswith("."):
        text += "."
    # Drop a comma somewhere mid-sentence for verisimilitude.
    if word_count > 6:
        comma_at = rng.randint(2, word_count - 3)
        parts = text.split(" ")
        parts[comma_at] = parts[comma_at] + ","
        text = " ".join(parts)
    return text


if __name__ == "__main__":
    sys.exit(main())
