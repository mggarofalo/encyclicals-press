"""Slug → vatican.va URL table for supported encyclicals.

Entries can be either a plain URL string (shorthand for the common case)
or a :class:`DocConfig` with a strategy override and/or per-document field
overrides applied after parsing. This is the configurability surface for
documents whose layout doesn't match the default strategy or that need a
specific field hand-corrected without code changes.

Example::

    URL_MAP: dict[str, str | DocConfig] = {
        "spe-salvi": "https://...",                       # plain URL
        "magnifica-humanitas": DocConfig(
            url="https://...",
            strategy="default",                            # named strategy
            overrides={"incipit": "Magnifica humanitas"},  # post-parse patch
        ),
    }

The slug is the project's stable identifier; vatican.va's own filenames
(e.g. ``hf_ben-xvi_enc_20071130_spe-salvi``) are intentionally hidden.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DocConfig:
    """Per-document configuration.

    :attr:`url`: the canonical English-language vatican.va URL.

    :attr:`strategy`: name of a registered parsing :class:`Strategy`. If
    ``None`` the parser walks :data:`encyclicals_press.parse.DEFAULT_CHAIN`
    (default + permissive fallback). If set, that single strategy is used —
    bypass the self-healing chain when you've already characterized the
    document.

    :attr:`overrides`: a mapping of :class:`Encyclical` field names to
    values, applied after parsing. Use this to patch known wrong outputs
    (e.g. an incipit the parser can't extract from prose) without writing
    a custom strategy.
    """

    url: str
    strategy: str | None = None
    overrides: dict = field(default_factory=dict)


URL_MAP: dict[str, str | DocConfig] = {
    "spe-salvi": (
        "https://www.vatican.va/content/benedict-xvi/en/encyclicals/documents/"
        "hf_ben-xvi_enc_20071130_spe-salvi.html"
    ),
    "magnifica-humanitas": (
        "https://www.vatican.va/content/leo-xiv/en/encyclicals/documents/"
        "20260515-magnifica-humanitas.html"
    ),
}


def url_for(slug: str) -> str:
    """Resolve *slug* to its vatican.va URL."""
    cfg = _entry(slug)
    return cfg.url


def config_for(slug: str, *, allow_unknown: bool = False) -> DocConfig | None:
    """Return the :class:`DocConfig` for *slug*.

    If *allow_unknown* is ``True``, unknown slugs return ``None`` instead
    of raising. Callers that need to query optional configuration (the
    parser asking "does this slug have an overridden strategy?") use the
    ``allow_unknown=True`` form so a slug that was passed an explicit URL
    via the API can still parse.
    """
    try:
        return _entry(slug)
    except KeyError:
        if allow_unknown:
            return None
        raise


def _entry(slug: str) -> DocConfig:
    try:
        raw = URL_MAP[slug]
    except KeyError as exc:
        raise KeyError(f"unknown encyclical slug {slug!r}; known slugs: {sorted(URL_MAP)}") from exc
    if isinstance(raw, DocConfig):
        return raw
    return DocConfig(url=raw)
