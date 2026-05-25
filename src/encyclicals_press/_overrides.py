"""Per-document overrides registry.

When the parser misreads a particular document and you'd rather patch
the result than chase the heuristic, register a :class:`DocConfig` for
the slug here. The override is applied after parsing but before
validation, so it can both fix a wrong field *and* suppress the warning
that field would have raised.

The registry ships empty. The project no longer maintains a code-level
table of known encyclical URLs; ``encyclicals fetch <url>`` takes the
URL directly and derives the slug from its filename.

Example::

    from encyclicals_press._overrides import DocConfig, register

    register(
        "weird-doc",
        DocConfig(
            strategy="my-custom",                 # named strategy
            overrides={"incipit": "Dei Verbum"},  # post-parse patch
        ),
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DocConfig:
    """Per-document configuration.

    :attr:`strategy`: name of a registered parsing strategy. ``None``
    leaves the strategy chain alone (default + permissive fallback).

    :attr:`overrides`: a mapping of :class:`Encyclical` field names to
    values, applied after parsing.
    """

    strategy: str | None = None
    overrides: dict = field(default_factory=dict)


_REGISTRY: dict[str, DocConfig] = {}


def register(slug: str, config: DocConfig) -> None:
    """Register a :class:`DocConfig` for *slug*."""
    _REGISTRY[slug] = config


def config_for(slug: str) -> DocConfig | None:
    """Return the registered :class:`DocConfig` for *slug*, if any."""
    return _REGISTRY.get(slug)


def clear() -> None:
    """Drop every registered config. Used by tests to reset state."""
    _REGISTRY.clear()
