"""Convert corpus Markdown to Typst markup.

The corpus dialect uses a small fixed inventory of inline forms:

* ``*X*``        — italic     → ``#emph[X]``
* ``**X**``      — bold       → ``#strong[X]``
* ``[L](U)``     — link       → ``#link("U")[L]``
* ``[^N]``       — footnote   → ``#footnote[<resolved body>]``

We emit Typst's **function-call** form (``#emph[X]``) rather than its
markup form (``_X_``) because the latter is delimiter-sensitive — Typst
won't close ``_S_ocialis`` (a vatican.va quirk that occurs in the wild)
since the trailing ``_`` is followed by a word character. The function
form has no such constraint.

The one wrinkle: in Typst markup mode, ``#emph[X](Y)`` is parsed as
``#emph`` with two positional arguments — the content ``[X]`` and the
parenthesised expression ``(Y)`` — not as an emph followed by a literal
``(Y)``. A zero-width space between ``]`` and ``(`` breaks the call
sequence invisibly; see :func:`_terminate_call`.
"""

from __future__ import annotations

import re

_INLINE_TOKEN_RE = re.compile(
    r"(?P<fnref>\[\^(?P<fnnum>\d+)\])"
    r"|(?P<bold>\*\*(?P<boldtxt>[^*]+)\*\*)"
    r"|(?P<italic>\*(?P<italictxt>[^*\n]+?)\*)"
    r"|(?P<link>\[(?P<linktext>[^\]]+)\]\((?P<linkurl>[^)\s]+)\))"
)

_TYPST_ESCAPE_RE = re.compile(r"([\\#@$<>*_`\[\]])")


def inline_to_typst_markup(md: str, footnotes: dict[int, str]) -> str:
    """Convert one Markdown run to raw Typst markup (no outer ``[...]``)."""
    pieces: list[str] = []
    pos = 0
    for m in _INLINE_TOKEN_RE.finditer(md):
        if m.start() > pos:
            pieces.append(escape_typst(md[pos : m.start()]))
        pieces.append(_token_to_typst(m, md, footnotes))
        pos = m.end()
    if pos < len(md):
        pieces.append(escape_typst(md[pos:]))
    return "".join(pieces)


def inline_to_typst(md: str, footnotes: dict[int, str]) -> str:
    """Convert Markdown to a Typst content block ``[…]`` for use as a function arg."""
    return "[" + inline_to_typst_markup(md, footnotes) + "]"


def escape_typst(text: str) -> str:
    """Escape Typst-special characters in a literal-text run."""
    return _TYPST_ESCAPE_RE.sub(r"\\\1", text)


def wrap_section_opening(markup: str) -> str:
    """Splice ``#smallcaps[#lower[first 3-5 words]]`` into the start of *markup*.

    Renders the first words of a section's opening paragraph as small caps
    — the SCOTUS-style flourish that replaces a drop cap. Falls through
    unchanged if the opener starts with markup that doesn't admit a clean
    prefix match (e.g. an italic phrase or a link).
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


# ---- internals ----------------------------------------------------------


def _token_to_typst(m: re.Match, md: str, footnotes: dict[int, str]) -> str:
    if m.group("fnref"):
        n = int(m.group("fnnum"))
        body = footnotes.get(n, f"[footnote {n} missing from corpus]")
        return _terminate_call(f"#footnote[{inline_to_typst_markup(body, footnotes)}]", md, m.end())
    if m.group("bold"):
        return _terminate_call(f"#strong[{escape_typst(m.group('boldtxt'))}]", md, m.end())
    if m.group("italic"):
        return _terminate_call(f"#emph[{escape_typst(m.group('italictxt'))}]", md, m.end())
    if m.group("link"):
        label = inline_to_typst_markup(m.group("linktext"), footnotes)
        url = m.group("linkurl")
        return _terminate_call(f'#link("{url}")[{label}]', md, m.end())
    return ""  # pragma: no cover — exhaustive over the regex alternatives


def _terminate_call(call: str, md: str, end: int) -> str:
    """Append a zero-width space if the next markdown char would be parsed
    as additional positional args to the call.

    Typst reads ``#emph[X](Y)`` as a two-arg invocation; the ZWSP breaks
    the sequence so ``(Y)`` reverts to literal markup.
    """
    if end < len(md) and md[end] in "([":
        return call + "\u200b"
    return call
