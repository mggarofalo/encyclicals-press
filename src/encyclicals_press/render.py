"""Corpus Markdown -> Typst source -> PDF.

Reads ``corpus/<pope>/<slug>.md``, parses its YAML frontmatter and the
fenced-div / Pandoc-flavored body that :mod:`md_writer` emits, generates a
Typst source file, and invokes the bundled ``typst`` compiler to produce a
PDF in ``output/<slug>.pdf``.

The corpus dialect is deliberately small (see ``md_writer.py``): a YAML
frontmatter block, ``## Section`` headings, ``::: {.paragraph n=N}`` /
``{.salutation}`` / ``{.dateline}`` / ``{.signature}`` fenced divs, plain
paragraphs for continuation prose, and a trailing ``## Footnotes`` section
with Pandoc-style ``[^N]: body`` definitions. We parse it by hand rather
than pulling in a full Markdown engine.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

import typst
import yaml


@dataclass
class _Block:
    kind: str  # "salutation" | "section" | "paragraph" | "continuation" | "dateline" | "signature"
    text: str = ""
    number: int | None = None  # for paragraph blocks


@dataclass
class _ParsedCorpus:
    meta: dict
    blocks: list[_Block] = field(default_factory=list)
    footnotes: dict[int, str] = field(default_factory=dict)


_FENCE_OPEN_RE = re.compile(
    r"^:::\s*\{\.(salutation|dateline|signature|paragraph)(?:\s+n=(\d+))?\}\s*$"
)
_FENCE_CLOSE_RE = re.compile(r"^:::\s*$")
_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$")
_FOOTNOTE_DEF_RE = re.compile(r"^\[\^(\d+)\]:\s*(.*)$")


def render(corpus_path: Path, output_path: Path) -> Path:
    """Render the encyclical at *corpus_path* to *output_path* (PDF)."""
    parsed = _read_corpus(corpus_path)
    typst_source = _emit_typst(parsed)

    typ_path = output_path.with_suffix(".typ")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    typ_path.write_text(typst_source, encoding="utf-8", newline="\n")

    template_root = _template_root()
    font_paths = [str(template_root / "fonts")]

    typst.compile(
        str(typ_path),
        output=str(output_path),
        root=str(template_root.parent),
        font_paths=font_paths,
    )
    return output_path


def _template_root() -> Path:
    # src/encyclicals_press/render.py -> project root -> templates/
    return Path(__file__).resolve().parents[2] / "templates"


# ---- corpus parsing -----------------------------------------------------


def _read_corpus(path: Path) -> _ParsedCorpus:
    raw = path.read_text(encoding="utf-8")
    meta, body = _split_frontmatter(raw)
    body, footnotes = _split_footnotes(body)

    blocks: list[_Block] = []
    current_fence: str | None = None
    current_number: int | None = None
    fence_buf: list[str] = []
    plain_buf: list[str] = []

    def flush_plain() -> None:
        text = " ".join(plain_buf).strip()
        if text:
            blocks.append(_Block(kind="continuation", text=text))
        plain_buf.clear()

    def flush_fence() -> None:
        nonlocal current_fence, current_number
        text = " ".join(fence_buf).strip()
        if current_fence == "paragraph":
            blocks.append(_Block(kind="paragraph", text=text, number=current_number))
        elif current_fence is not None:
            blocks.append(_Block(kind=current_fence, text=text))
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
            blocks.append(_Block(kind="section", text=heading_m.group(1)))
            continue

        if not stripped:
            flush_plain()
            continue

        plain_buf.append(stripped)

    flush_plain()

    return _ParsedCorpus(meta=meta, blocks=blocks, footnotes=footnotes)


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


# ---- Typst emission -----------------------------------------------------

_ROMAN_PREFIX_RE = re.compile(r"^([IVXLCDM]+)\.\s+(.+)$")


def _emit_typst(parsed: _ParsedCorpus) -> str:
    meta = parsed.meta
    promulgated_raw = meta.get("promulgated")
    promulgated = _coerce_date(promulgated_raw)

    lines: list[str] = [
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
            lines.append(f"#salutation({_inline_to_typst(block.text, parsed.footnotes)})")
            lines.append("")
            continue
        if block.kind == "section":
            heading_text = block.text
            roman_m = _ROMAN_PREFIX_RE.match(heading_text)
            if roman_m is not None:
                numeral, title = roman_m.group(1), roman_m.group(2)
                lines.append(f"#chapter-divider({_quote(numeral + '.')}, {_quote(title)})")
            else:
                lines.append(f"#section-heading({_quote(heading_text)})")
            lines.append("")
            first_para_in_section = True
            continue
        if block.kind == "paragraph":
            markup = _inline_to_typst_markup(block.text, parsed.footnotes)
            opening = "#paragraph-num(" + str(block.number) + ") " if block.number else ""
            if first_para_in_section:
                markup = _wrap_section_opening_markup(markup)
                first_para_in_section = False
            lines.append(opening + markup)
            lines.append("")
            continue
        if block.kind == "continuation":
            markup = _inline_to_typst_markup(block.text, parsed.footnotes)
            lines.append(markup)
            lines.append("")
            continue
        if block.kind == "dateline":
            lines.append(f"#dateline({_inline_to_typst(block.text, parsed.footnotes)})")
            lines.append("")
            continue
        if block.kind == "signature":
            # Signature is rendered as letterspaced caps; strip markdown bold
            # so it doesn't compete with the template styling.
            clean = re.sub(r"\*\*([^*]+)\*\*", r"\1", block.text)
            lines.append(f"#signature({_inline_to_typst(clean, parsed.footnotes)})")
            lines.append("")
            continue

    # Re-import the helpers we call at the top level (chapter-divider,
    # section-heading, paragraph-num, salutation, dateline, signature)
    # so the show-rule body sees them in scope.
    helpers_import = (
        '#import "/templates/lib/typography.typ": '
        "paragraph-num, section-heading, chapter-divider, "
        "salutation, dateline, signature\n"
    )
    return helpers_import + "\n" + "\n".join(lines)


def _wrap_section_opening_markup(markup: str) -> str:
    """Wrap the first 3-5 words of a section opener in small caps in-place.

    *markup* is raw Typst markup (no outer ``[...]``). Falls through
    unchanged if the opener starts with markup that doesn't admit a clean
    prefix match.
    """
    plain = re.sub(r"#[a-zA-Z][\w-]*\([^)]*\)\[[^\]]*\]|[_*]", "", markup).lstrip()
    if not plain:
        return markup
    words = plain.split()
    take = min(4, len(words))
    needle = " ".join(words[:take])
    idx = markup.find(needle)
    if idx == -1:
        return markup
    head = markup[:idx]
    rest = markup[idx + len(needle) :]
    return f"{head}#smallcaps[#lower[{needle}]]{rest}"


# ---- inline markdown -> Typst markup ------------------------------------

_INLINE_TOKEN_RE = re.compile(
    r"(?P<fnref>\[\^(?P<fnnum>\d+)\])"
    r"|(?P<bold>\*\*(?P<boldtxt>[^*]+)\*\*)"
    r"|(?P<italic>\*(?P<italictxt>[^*\n]+?)\*)"
    r"|(?P<link>\[(?P<linktext>[^\]]+)\]\((?P<linkurl>[^)\s]+)\))"
)


def _inline_to_typst_markup(md: str, footnotes: dict[int, str]) -> str:
    """Convert one markdown run to raw Typst markup (no outer ``[...]``)."""

    pieces: list[str] = []
    pos = 0
    for m in _INLINE_TOKEN_RE.finditer(md):
        if m.start() > pos:
            pieces.append(_escape_typst(md[pos : m.start()]))
        if m.group("fnref"):
            n = int(m.group("fnnum"))
            body = footnotes.get(n, f"[footnote {n} missing from corpus]")
            fn_call = f"#footnote[{_inline_to_typst_markup(body, footnotes)}]"
            pieces.append(_terminated(fn_call, md, m.end()))
        elif m.group("bold"):
            inner = m.group("boldtxt")
            pieces.append(_terminated(f"#strong[{_escape_typst(inner)}]", md, m.end()))
        elif m.group("italic"):
            inner = m.group("italictxt")
            pieces.append(_terminated(f"#emph[{_escape_typst(inner)}]", md, m.end()))
        elif m.group("link"):
            label = m.group("linktext")
            url = m.group("linkurl")
            pieces.append(
                _terminated(
                    f'#link("{url}")[{_inline_to_typst_markup(label, footnotes)}]', md, m.end()
                )
            )
        pos = m.end()
    if pos < len(md):
        pieces.append(_escape_typst(md[pos:]))
    return "".join(pieces)


def _terminated(call: str, md: str, end: int) -> str:
    """Emit *call* followed by a zero-width space if the next markdown char
    would otherwise be parsed as additional function-call arguments.

    In Typst markup, ``#emph[X](Y)`` is read as ``#emph`` with two positional
    arguments — the content ``[X]`` and the parenthesised expression
    ``(Y)``. A ZWSP between the ``]`` and ``(`` breaks the call sequence
    without inserting a visible space.
    """
    if end < len(md) and md[end] in "([":
        return call + "\u200b"
    return call


def _inline_to_typst(md: str, footnotes: dict[int, str]) -> str:
    """Convert markdown to a Typst content block ``[...]`` for use as a function arg."""
    return "[" + _inline_to_typst_markup(md, footnotes) + "]"


_TYPST_ESCAPE_RE = re.compile(r"([\\#@$<>*_`\[\]])")


def _escape_typst(text: str) -> str:
    return _TYPST_ESCAPE_RE.sub(r"\\\1", text)


# ---- value formatting ---------------------------------------------------


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
