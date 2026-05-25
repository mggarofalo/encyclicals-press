"""Slug -> vatican.va URL table for supported encyclicals.

One row per encyclical the project ships. URLs are the canonical English-language
HTML pages on vatican.va. The slug is the project's stable identifier; vatican.va's
own filenames (e.g. ``hf_ben-xvi_enc_20071130_spe-salvi``) are intentionally hidden.
"""

from __future__ import annotations

URL_MAP: dict[str, str] = {
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
    try:
        return URL_MAP[slug]
    except KeyError as exc:
        raise KeyError(f"unknown encyclical slug {slug!r}; known slugs: {sorted(URL_MAP)}") from exc
