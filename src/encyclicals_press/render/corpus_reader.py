"""Parse corpus Markdown into a structured intermediate.

The corpus dialect is deliberately small — :mod:`encyclicals_press.md_writer`
controls the producer side, and this module the consumer side. The dialect:

* YAML frontmatter at the top, terminated by ``\\n---\\n``.
* ``## Heading`` lines mark section breaks.
* Fenced divs (``::: {.kind [n=N]}`` … ``:::``) carry typed blocks:
  ``salutation``, ``paragraph`` (with ``n=N``), ``dateline``, ``signature``.
* Bare paragraphs between fences are continuation prose.
* A trailing ``## Footnotes`` section holds ``[^N]: text`` Pandoc-style
  definitions, one per blank-line-separated paragraph.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

_FENCE_OPEN_RE = re.compile(
    r"^:::\s*\{\.(salutation|dateline|signature|paragraph)(?:\s+n=(\d+))?\}\s*$"
)
_FENCE_CLOSE_RE = re.compile(r"^:::\s*$")
_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$")
_FOOTNOTE_DEF_RE = re.compile(r"^\[\^(\d+)\]:\s*(.*)$")


@dataclass
class Block:
    """One block of corpus content. ``kind`` is one of:

    ``"salutation"`` | ``"section"`` | ``"paragraph"`` |
    ``"continuation"`` | ``"dateline"`` | ``"signature"``.

    ``number`` is the encyclical paragraph number (only set for
    ``"paragraph"`` blocks).
    """

    kind: str
    text: str = ""
    number: int | None = None


@dataclass
class ParsedCorpus:
    """The whole corpus file, in a form the Typst emitter can walk."""

    meta: dict
    blocks: list[Block] = field(default_factory=list)
    footnotes: dict[int, str] = field(default_factory=dict)


def read_corpus(path: Path) -> ParsedCorpus:
    """Read and parse the corpus Markdown file at *path*."""
    raw = path.read_text(encoding="utf-8")
    meta, body = _split_frontmatter(raw)
    body, footnotes = _split_footnotes(body)
    blocks = _parse_blocks(body)
    return ParsedCorpus(meta=meta, blocks=blocks, footnotes=footnotes)


# ---- internals ----------------------------------------------------------


def _split_frontmatter(raw: str) -> tuple[dict, str]:
    if not raw.startswith("---\n"):
        raise ValueError("corpus file missing YAML frontmatter")
    end = raw.find("\n---\n", 4)
    if end == -1:
        raise ValueError("corpus frontmatter is not terminated")
    meta = yaml.safe_load(raw[4:end]) or {}
    body = raw[end + len("\n---\n") :]
    return meta, body


def _split_footnotes(body: str) -> tuple[str, dict[int, str]]:
    """Strip the trailing ``## Footnotes`` block and return its parsed contents."""
    marker = "\n## Footnotes\n"
    idx = body.find(marker)
    if idx == -1:
        return body, {}
    head, _, tail = body.partition(marker)
    footnotes: dict[int, str] = {}
    current_number: int | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_number, current_lines
        if current_number is not None:
            footnotes[current_number] = " ".join(current_lines).strip()
        current_number = None
        current_lines = []

    for line in tail.splitlines():
        m = _FOOTNOTE_DEF_RE.match(line)
        if m is not None:
            flush()
            current_number = int(m.group(1))
            current_lines = [m.group(2)]
            continue
        if line.strip() == "":
            continue
        if current_number is not None:
            current_lines.append(line.strip())
    flush()
    return head, footnotes


def _parse_blocks(body: str) -> list[Block]:  # noqa: PLR0912
    """Walk the post-frontmatter body and emit a typed Block per region."""
    blocks: list[Block] = []
    current_fence: str | None = None
    current_number: int | None = None
    fence_buf: list[str] = []
    plain_buf: list[str] = []

    def flush_plain() -> None:
        text = " ".join(plain_buf).strip()
        if text:
            blocks.append(Block(kind="continuation", text=text))
        plain_buf.clear()

    def flush_fence() -> None:
        nonlocal current_fence, current_number
        text = " ".join(fence_buf).strip()
        if current_fence == "paragraph":
            blocks.append(Block(kind="paragraph", text=text, number=current_number))
        elif current_fence is not None:
            blocks.append(Block(kind=current_fence, text=text))
        fence_buf.clear()
        current_fence = None
        current_number = None

    for line in body.splitlines():
        stripped = line.rstrip()
        if current_fence is not None:
            if _FENCE_CLOSE_RE.match(stripped):
                flush_fence()
                continue
            fence_buf.append(stripped)
            continue

        open_m = _FENCE_OPEN_RE.match(stripped)
        if open_m is not None:
            flush_plain()
            current_fence = open_m.group(1)
            current_number = int(open_m.group(2)) if open_m.group(2) else None
            continue

        heading_m = _HEADING_RE.match(stripped)
        if heading_m is not None:
            flush_plain()
            blocks.append(Block(kind="section", text=heading_m.group(1)))
            continue

        if not stripped:
            flush_plain()
            continue

        plain_buf.append(stripped)

    flush_plain()
    return blocks
