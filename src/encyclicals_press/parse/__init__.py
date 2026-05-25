"""HTML → :class:`Encyclical` parser with pluggable strategies.

The vatican.va HTML is loose and varies across pontificates: no semantic
headings, no reliable CSS classes, title block in unpredictable places,
footnote definitions sometimes in nested ``<div>``s. Rather than write
per-document parsers, we factor every decision a parser has to make into
a :class:`Strategy` field and try strategies in sequence until validation
passes — the **self-healing** layer.

Public entry points
-------------------

* :func:`parse` — read HTML, run the strategy chain, apply per-document
  overrides, validate, return the resulting :class:`Encyclical`.
* :class:`Strategy` (re-exported) — the bundle of replaceable heuristics.
* :data:`DEFAULT_STRATEGY`, :data:`PERMISSIVE_STRATEGY`,
  :data:`DEFAULT_CHAIN` — the named strategies that ship by default.
* :class:`ParseWarning` — what validation reports.
* :class:`ParseWarningCategory` — the Python warning category used to
  surface non-fatal issues. Filter with :mod:`warnings` as usual.

Extending
---------

To customize behavior for a particular document layout::

    from encyclicals_press.parse import DEFAULT_STRATEGY, register
    my_strategy = DEFAULT_STRATEGY.replace(
        name="my-doc",
        drop_preamble=my_custom_toc_skipper,
    )
    register(my_strategy)

Then reference it from ``URL_MAP``::

    URL_MAP["my-doc"] = DocConfig(url="...", strategy="my-doc")

To patch a specific field without writing a custom strategy, use
``DocConfig.overrides``::

    URL_MAP["weird-doc"] = DocConfig(
        url="...",
        overrides={"pope": "Leo XIV", "incipit": "Magnifica humanitas"},
    )
"""

from __future__ import annotations

import re as _re
import warnings as _warnings
from collections.abc import Iterable
from dataclasses import dataclass

from selectolax.lexbor import LexborHTMLParser, LexborNode

from .._url_map import config_for, url_for
from ..schema import Encyclical, Footnote, Paragraph
from .heuristics import (
    extract_paragraph_number,
    is_empty,
    node_to_markdown,
    parse_dateline_date,
    split_on_breaks,
    strip_inline_markup,
    title_case,
)
from .strategies import (
    DEFAULT_CHAIN,
    DEFAULT_STRATEGY,
    PERMISSIVE_STRATEGY,
    Strategy,
    register,
)
from .strategies import (
    get as get_strategy,
)
from .validate import ParseWarning, has_errors, validate

__all__ = [
    "DEFAULT_CHAIN",
    "DEFAULT_STRATEGY",
    "PERMISSIVE_STRATEGY",
    "ParseAttempt",
    "ParseWarning",
    "ParseWarningCategory",
    "Strategy",
    "get_strategy",
    "parse",
    "register",
]


class ParseWarningCategory(UserWarning):
    """:func:`warnings.warn` category used to surface non-fatal parse issues."""


@dataclass
class ParseAttempt:
    """Result of a single strategy attempt."""

    strategy_name: str
    encyclical: Encyclical | None
    warnings: list[ParseWarning]


# ============================================================================
# Public API
# ============================================================================


def parse(
    html_source: str,
    slug: str,
    source_url: str | None = None,
    *,
    strategy: Strategy | None = None,
    strategies: Iterable[Strategy] | None = None,
    emit_warnings: bool = True,
) -> Encyclical:
    """Parse *html_source* into an :class:`Encyclical`.

    Strategy resolution order:

    1. *strategy* argument — explicit override; the chain becomes that one
       strategy.
    2. *strategies* argument — explicit chain to walk.
    3. ``DocConfig.strategy`` named in the URL_MAP — single strategy.
    4. :data:`DEFAULT_CHAIN`.

    Each strategy in the resolved chain is executed in turn. The first
    attempt whose validation finds no errors is returned. If every
    strategy fails validation, the last attempt is returned anyway (the
    user can still inspect the partial result and the warnings).

    Per-document field overrides from ``DocConfig.overrides`` are applied
    *after* strategy execution but *before* warnings are emitted, so an
    override can suppress a warning by patching the offending field.

    :param emit_warnings: if True (default), warnings are sent through
        :func:`warnings.warn` with category :class:`ParseWarningCategory`.
        Set False to retrieve them programmatically — they are still
        attached to the returned encyclical via the surrounding context
        if needed; see :func:`parse_with_attempts` for that.
    """
    attempts = parse_with_attempts(
        html_source, slug, source_url, strategy=strategy, strategies=strategies
    )
    winning = _pick_attempt(attempts)
    if winning.encyclical is None:
        # Every strategy threw before producing a partial result.
        raise RuntimeError(
            f"all strategies failed for {slug!r}: "
            + "; ".join(f"{a.strategy_name}: {a.warnings[0].message}" for a in attempts)
        )
    encyclical = _apply_overrides(winning.encyclical, slug)
    if emit_warnings:
        for w in winning.warnings:
            _warnings.warn(str(w), ParseWarningCategory, stacklevel=2)
    return encyclical


def parse_with_attempts(
    html_source: str,
    slug: str,
    source_url: str | None = None,
    *,
    strategy: Strategy | None = None,
    strategies: Iterable[Strategy] | None = None,
) -> list[ParseAttempt]:
    """Run the strategy chain and return every attempt, in order.

    Useful for debugging, tests, and tooling that wants to inspect *why*
    the parser ended up with a particular result. The first attempt
    without validation errors is the one :func:`parse` would have
    returned.
    """
    chain = _resolve_chain(slug, strategy, strategies)
    out: list[ParseAttempt] = []
    for strat in chain:
        attempt = _try(html_source, slug, source_url, strat)
        out.append(attempt)
        if attempt.encyclical is not None and not has_errors(attempt.warnings):
            break
    return out


# ============================================================================
# Internals
# ============================================================================


def _resolve_chain(
    slug: str,
    strategy: Strategy | None,
    strategies: Iterable[Strategy] | None,
) -> tuple[Strategy, ...]:
    if strategy is not None:
        return (strategy,)
    if strategies is not None:
        return tuple(strategies)
    cfg = config_for(slug, allow_unknown=True)
    if cfg is not None and cfg.strategy is not None:
        return (get_strategy(cfg.strategy),)
    return DEFAULT_CHAIN


def _try(html_source: str, slug: str, source_url: str | None, strat: Strategy) -> ParseAttempt:
    try:
        encyclical = _execute(html_source, slug, source_url, strat)
    except Exception as exc:  # noqa: BLE001
        return ParseAttempt(
            strategy_name=strat.name,
            encyclical=None,
            warnings=[
                ParseWarning(
                    code="strategy-crashed",
                    message=f"{strat.name}: {exc}",
                    severity="error",
                )
            ],
        )
    warnings_list = validate(encyclical)
    return ParseAttempt(strategy_name=strat.name, encyclical=encyclical, warnings=warnings_list)


def _pick_attempt(attempts: list[ParseAttempt]) -> ParseAttempt:
    for attempt in attempts:
        if attempt.encyclical is not None and not has_errors(attempt.warnings):
            return attempt
    return attempts[-1]


def _apply_overrides(encyclical: Encyclical, slug: str) -> Encyclical:
    cfg = config_for(slug, allow_unknown=True)
    if cfg is None or not cfg.overrides:
        return encyclical
    return encyclical.model_copy(update=cfg.overrides)


# ---- the actual strategy execution -------------------------------------


def _execute(html_source: str, slug: str, source_url: str | None, strat: Strategy) -> Encyclical:
    tree = LexborHTMLParser(html_source)

    container = strat.find_body(tree)
    if container is None:
        raise ValueError("body container not found")

    title_p = strat.find_title(tree, container)
    if title_p is None:
        raise ValueError("title paragraph not found")

    raw_lines = split_on_breaks(title_p)
    title_lines = [line for line in (s.strip(" \xa0") for s in raw_lines) if line]
    title_block = strat.parse_title_lines(title_lines)

    body_ps, footnote_ps = strat.split_body_and_footnotes(tree, container)
    if not body_ps:
        raise ValueError("no body paragraphs found")
    if title_p is body_ps[0]:
        body_ps = body_ps[1:]
    body_ps = strat.drop_preamble(body_ps)

    paragraphs, closing, promulgated = _parse_body(body_ps, strat)

    footnotes = _parse_footnotes(footnote_ps)

    incipit = _extract_incipit(paragraphs, title_block.title)

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


def _parse_body(  # noqa: PLR0912, PLR0915
    body_ps: list[LexborNode], strat: Strategy
):
    """Walk the body paragraphs and build the paragraph list.

    Uses ``strat.is_heading``, ``strat.chapter_preamble_numeral``,
    ``strat.find_dateline_index``, and ``strat.looks_like_signature``.
    Pending-chapter logic combines ``CHAPTER ONE`` preamble paragraphs
    with the one or more title paragraphs that follow into a single
    ``"I. Title"`` section name — :mod:`encyclicals_press.render` then
    emits these as ``#chapter-divider`` blocks.
    """
    paragraphs: list[Paragraph] = []
    current_section: str | None = None
    pending_chapter: str | None = None
    pending_chapter_titles: list[str] = []
    closing: list[str] = []

    def flush_chapter() -> str | None:
        nonlocal pending_chapter, pending_chapter_titles
        if pending_chapter is None:
            return None
        title_text = " ".join(pending_chapter_titles).strip()
        out = f"{pending_chapter}. {title_text}" if title_text else f"{pending_chapter}."
        pending_chapter = None
        pending_chapter_titles = []
        return out

    dateline_idx = strat.find_dateline_index(body_ps)
    body_range = body_ps[:dateline_idx] if dateline_idx is not None else body_ps

    for p in body_range:
        if is_empty(p):
            continue
        md = node_to_markdown(p)
        if not md.strip():
            continue
        number, body_text = extract_paragraph_number(md)
        if number is not None:
            chapter_section = flush_chapter()
            if chapter_section is not None:
                current_section = chapter_section
            paragraphs.append(Paragraph(number=number, section=current_section, text=body_text))
            continue
        if strat.is_heading(p):
            heading_text = strip_inline_markup(md)
            chapter_numeral = strat.chapter_preamble_numeral(heading_text)
            if chapter_numeral is not None:
                chapter_section = flush_chapter()
                if chapter_section is not None:
                    current_section = chapter_section
                pending_chapter = chapter_numeral
                continue
            if pending_chapter is not None:
                pending_chapter_titles.append(title_case(heading_text).rstrip("."))
            else:
                current_section = heading_text
            continue
        chapter_section = flush_chapter()
        if chapter_section is not None:
            current_section = chapter_section
        paragraphs.append(Paragraph(number=None, section=current_section, text=md))

    promulgated = None
    if dateline_idx is not None:
        dateline_p = body_ps[dateline_idx]
        dateline_md = node_to_markdown(dateline_p).strip()
        promulgated = parse_dateline_date(dateline_md)
        closing.append(dateline_md)
        for sig_p in body_ps[dateline_idx + 1 :]:
            if is_empty(sig_p):
                continue
            sig_md = node_to_markdown(sig_p).strip()
            if sig_md and strat.looks_like_signature(sig_md):
                closing.append(sig_md)
            break

    if promulgated is None:
        raise ValueError("could not extract promulgation date from body")

    return paragraphs, closing, promulgated


_FOOTNOTE_DEF_HEAD_RE = _re.compile(r"\[(\d+)\]")
_FOOTNOTE_DEF_BARE_HEAD_RE = _re.compile(r"(\d+)\]")
_FTN_ANCHOR_NAME_RE = _re.compile(r"^_ftn(\d+)$")


def _parse_footnotes(footnote_ps: list["LexborNode"]) -> list[Footnote]:  # noqa: PLR0912
    """Recover footnote definitions from the paragraphs the strategy gave us.

    Resilient to two vatican.va quirks observed in the wild:

    * **Malformed visible label.** Some pages emit ``<a name="_ftn86"></a>86]``
      — empty anchor followed by a half-bracketed ``86]`` literal that
      doesn't match the canonical ``[N]`` pattern. Fall back to the anchor's
      ``name="_ftn{N}"`` attribute, which never lies about the number.

    * **Multiple footnotes in one ``<p>``.** Fratelli Tutti packs ftn 118
      and 119 into a single paragraph: ``<a name="_ftn118">[118]</a> body...
      <a name="_ftn119">[119]</a> body...``. Split on each
      ``<a name="_ftnN">`` anchor and emit one footnote per segment.
    """
    footnotes: list[Footnote] = []
    for p in footnote_ps:
        if is_empty(p):
            continue
        anchor_numbers = _collect_def_anchor_numbers(p)
        md = node_to_markdown(p)

        if len(anchor_numbers) <= 1:
            number = _extract_footnote_number(md, anchor_numbers)
            if number is None:
                continue
            footnotes.append(Footnote(number=number, text=_strip_leading_marker(md)))
            continue

        # Multiple footnotes packed into one paragraph: split on the [N]
        # marker corresponding to each anchor, in order.
        segments = _split_packed_footnotes(md, anchor_numbers)
        for number, text in segments:
            footnotes.append(Footnote(number=number, text=text))
    return footnotes


def _collect_def_anchor_numbers(p: "LexborNode") -> list[int]:
    numbers: list[int] = []
    for anchor in p.css("a"):
        name = anchor.attributes.get("name") or ""
        m = _FTN_ANCHOR_NAME_RE.match(name)
        if m is not None:
            numbers.append(int(m.group(1)))
    return numbers


def _extract_footnote_number(md: str, anchor_numbers: list[int]) -> int | None:
    """Number from ``[N]`` if present, else from the def anchor, else None."""
    m = _FOOTNOTE_DEF_HEAD_RE.search(md[:20])
    if m is not None:
        return int(m.group(1))
    if anchor_numbers:
        return anchor_numbers[0]
    return None


def _strip_leading_marker(md: str) -> str:
    """Drop the leading ``[N]`` / ``N]`` marker from a definition's body."""
    md = md.lstrip()
    m = _FOOTNOTE_DEF_HEAD_RE.match(md)
    if m is not None:
        return md[m.end() :].strip()
    m = _FOOTNOTE_DEF_BARE_HEAD_RE.match(md)
    if m is not None:
        return md[m.end() :].strip()
    return md


def _split_packed_footnotes(md: str, anchor_numbers: list[int]) -> list[tuple[int, str]]:
    """Slice *md* at each ``[N]`` matching one of *anchor_numbers*, in order."""
    out: list[tuple[int, str]] = []
    cursor = 0
    pending: int | None = None
    for n in anchor_numbers:
        pattern = _re.compile(r"\b" + str(n) + r"\]")
        match = pattern.search(md, cursor)
        if match is None:
            continue
        if pending is not None:
            out.append((pending, md[cursor : match.start()].strip().rstrip("[").strip()))
        pending = n
        cursor = match.end()
    if pending is not None:
        out.append((pending, md[cursor:].strip()))
    return out


def _extract_incipit(paragraphs: list[Paragraph], title: str) -> str:
    """The Latin opening words used as the title-page incipit.

    Look for the first italic span in paragraph 1. Use it as the incipit
    only if it contains the title's first word — that filters out
    scripture-citation italics like ``*1 Jn*`` / ``*Rom*`` / ``*Jn*`` that
    open paragraph 1 in many encyclicals. When the italic doesn't qualify,
    fall back to the title itself.
    """
    title_first = title.split()[0].lower() if title.split() else ""
    for p in paragraphs:
        if p.number != 1:
            continue
        for m in _re.finditer(r"\*([^*]+)\*", p.text):
            candidate = m.group(1).strip().rstrip(",.;")
            if not candidate:
                continue
            words = [w.strip("\".,'’‘“”") for w in candidate.lower().split()]
            if not title_first or title_first not in words:
                continue
            # A single-word italic that just echoes the title's first word
            # (e.g. ``*caritas*`` in *Caritas in Veritate* paragraph 1) is
            # less informative than the full title — prefer the title.
            if len(words) == 1 and len(title.split()) > 1:
                break
            return title_case(candidate)
        break
    return title
