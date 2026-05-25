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


# John Paul II encyclicals predating the modern vatican.va template put the
# pope's name in Latin ("IOANNES PAULUS PP. II"), often omit the "ENCYCLICAL
# LETTER" rubric, and sometimes interleave the title with section dividers in
# ways the parser's heuristics can't decode. Patch the affected fields here.
_JP2_OVERRIDES: dict[str, dict[str, str]] = {
    "dives-in-misericordia": {},
    "sollicitudo-rei-socialis": {},
    "redemptoris-missio": {},
    "veritatis-splendor": {},
    "evangelium-vitae": {},
    "slavorum-apostoli": {"title": "Slavorum Apostoli", "incipit": "Slavorum Apostoli"},
    "laborem-exercens": {"title": "Laborem Exercens", "incipit": "Laborem Exercens"},
    "dominum-et-vivificantem": {
        "title": "Dominum et Vivificantem",
        "incipit": "Dominum et Vivificantem",
    },
    "redemptoris-mater": {"title": "Redemptoris Mater", "incipit": "Redemptoris Mater"},
    "ut-unum-sint": {"title": "Ut Unum Sint", "incipit": "Ut Unum Sint"},
}
for _slug, _patch in _JP2_OVERRIDES.items():
    _REGISTRY[_slug] = DocConfig(overrides={"pope": "John Paul II", **_patch})


# Paul VI's pre-1970s vatican.va pages use a "ENCYCLICAL OF POPE PAUL VI"
# rubric instead of the modern "ENCYCLICAL LETTER", which the default
# title-paragraph beacon doesn't recognize. Patch pope (and title/incipit
# for the docs whose first body paragraph isn't the actual title).
_PAUL_VI_OVERRIDES: dict[str, dict[str, str]] = {
    "ecclesiam-suam": {},
    "mense-maio": {},
    "christi-matri": {},
    "sacerdotalis-caelibatus": {},
    "mysterium-fidei": {"title": "Mysterium Fidei", "incipit": "Mysterium Fidei"},
    "populorum-progressio": {
        "title": "Populorum Progressio",
        "incipit": "Populorum Progressio",
    },
}
for _slug, _patch in _PAUL_VI_OVERRIDES.items():
    _REGISTRY[_slug] = DocConfig(overrides={"pope": "Paul VI", **_patch})


def register(slug: str, config: DocConfig) -> None:
    """Register a :class:`DocConfig` for *slug*."""
    _REGISTRY[slug] = config


def config_for(slug: str) -> DocConfig | None:
    """Return the registered :class:`DocConfig` for *slug*, if any."""
    return _REGISTRY.get(slug)


def clear() -> None:
    """Drop every registered config. Used by tests to reset state."""
    _REGISTRY.clear()
