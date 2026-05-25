"""Strategy bundles.

A :class:`Strategy` is a frozen record of heuristic choices that the parser
consults at each decision point. Replace individual fields with
:meth:`Strategy.replace` to customize for a particular document layout
without reimplementing the whole pipeline. Strategies can be looked up by
name (``register()``/``get()``) for use from the URL_MAP.

Two strategies ship by default:

* ``"default"`` — the heuristics that handle both Spe Salvi (Benedict-era)
  and Magnifica Humanitas (Leo-era) layouts. This is what
  :func:`encyclicals_press.parse.parse` picks unless told otherwise.

* ``"permissive"`` — the same heuristics with TOC-skipping disabled.
  Used as the second link in :data:`DEFAULT_CHAIN`: when the default
  strategy produces a validation error (no paragraphs, no title…),
  the parser falls back to ``"permissive"`` before giving up.

The two together form :data:`DEFAULT_CHAIN`, the self-healing fallback
sequence ``parse()`` walks.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from . import heuristics

if TYPE_CHECKING:
    from selectolax.lexbor import LexborHTMLParser, LexborNode

    from .heuristics import TitleBlock


@dataclass(frozen=True)
class Strategy:
    """A bundle of heuristic choices used by :func:`parse`.

    Each field is a small, single-purpose callable. The defaults are in
    :mod:`encyclicals_press.parse.heuristics`. Use :meth:`replace` to
    override fields::

        my_strategy = DEFAULT_STRATEGY.replace(
            name="my-doc",
            drop_preamble=heuristics.keep_all,
        )
    """

    name: str
    find_body: Callable[[LexborHTMLParser], LexborNode | None]
    find_title: Callable[[LexborHTMLParser, LexborNode], LexborNode | None]
    parse_title_lines: Callable[[list[str]], TitleBlock]
    split_body_and_footnotes: Callable[
        [LexborHTMLParser, LexborNode],
        tuple[list[LexborNode], list[LexborNode]],
    ]
    drop_preamble: Callable[[list[LexborNode]], list[LexborNode]]
    is_heading: Callable[[LexborNode], bool]
    chapter_preamble_numeral: Callable[[str], str | None]
    find_dateline_index: Callable[[list[LexborNode]], int | None]
    looks_like_signature: Callable[[str], bool]

    def replace(self, **overrides) -> Strategy:
        """Return a new strategy with the named fields swapped out."""
        return replace(self, **overrides)


DEFAULT_STRATEGY = Strategy(
    name="default",
    find_body=heuristics.find_body_container,
    find_title=heuristics.find_title_paragraph,
    parse_title_lines=heuristics.parse_title_lines,
    split_body_and_footnotes=heuristics.split_body_and_footnotes,
    drop_preamble=heuristics.drop_table_of_contents,
    is_heading=heuristics.is_heading,
    chapter_preamble_numeral=heuristics.chapter_preamble_numeral,
    find_dateline_index=heuristics.find_dateline_index,
    looks_like_signature=heuristics.looks_like_signature,
)


PERMISSIVE_STRATEGY = DEFAULT_STRATEGY.replace(
    name="permissive",
    drop_preamble=heuristics.keep_all,
)


DEFAULT_CHAIN: tuple[Strategy, ...] = (DEFAULT_STRATEGY, PERMISSIVE_STRATEGY)
"""The fallback chain ``parse()`` walks when no explicit strategy is supplied.

The default strategy handles every document we've encountered. The
permissive strategy exists so that genuinely novel layouts — ones whose
TOC heuristic would discard real content — still produce *something*
the user can inspect, rather than a parse error.
"""


_REGISTRY: dict[str, Strategy] = {
    "default": DEFAULT_STRATEGY,
    "permissive": PERMISSIVE_STRATEGY,
}


def register(strategy: Strategy) -> None:
    """Register *strategy* by name so it can be referenced from URL_MAP."""
    _REGISTRY[strategy.name] = strategy


def get(name: str) -> Strategy:
    """Look up a registered strategy by name. Raises :class:`KeyError` if missing."""
    try:
        return _REGISTRY[name]
    except KeyError as exc:
        raise KeyError(f"unknown strategy {name!r}; registered: {sorted(_REGISTRY)}") from exc
