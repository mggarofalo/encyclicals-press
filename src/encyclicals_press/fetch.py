"""Polite client for fetching encyclical HTML from vatican.va.

Single-document fetch. Caches the response body to ``tests/fixtures/<slug>.html``
so downstream stages develop against a committed snapshot rather than re-hitting
the Vatican every iteration.

The project does not maintain a code-level table of supported URLs.
``encyclicals fetch <url>`` takes the URL directly, derives the slug
from the URL filename via :func:`derive_slug`, and caches the HTML.
Downstream stages (``ingest``, ``parse``, ``render``) read the source
URL back from the page's ``<link rel="canonical">`` tag, so no
slug→URL mapping needs to be committed.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

USER_AGENT = "encyclicals-press/0.1 (+https://github.com/mggarofalo/encyclicals-press)"
REQUEST_INTERVAL_SECONDS = 1.0
TIMEOUT_SECONDS = 30.0

_state: dict[str, float] = {"last_request_at": 0.0}


def _project_root() -> Path:
    # src/encyclicals_press/fetch.py -> project root is two parents above src/.
    return Path(__file__).resolve().parents[2]


def fixture_path(slug: str) -> Path:
    return _project_root() / "tests" / "fixtures" / f"{slug}.html"


# Stripping rules ordered most-specific-first: each captures the project-style
# slug from a vatican.va filename pattern.
_SLUG_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^hf_[a-z-]+_enc_\d+_(.+)$"),
    re.compile(r"^papa-francesco_\d+_enciclica-(.+)$"),
    re.compile(r"^\d+-enciclica-(.+)$"),
    re.compile(r"^\d+-(.+)$"),
)


def derive_slug(url: str) -> str:
    """Derive a project-style slug from a vatican.va document URL.

    Examples:

    * ``.../hf_ben-xvi_enc_20071130_spe-salvi.html`` → ``spe-salvi``
    * ``.../papa-francesco_20150524_enciclica-laudato-si.html`` → ``laudato-si``
    * ``.../20260515-magnifica-humanitas.html`` → ``magnifica-humanitas``

    Falls back to the filename minus extension if none of the patterns
    match — the result is at worst a long-but-stable identifier.
    """
    path = urlparse(url).path or url
    stem = path.rsplit("/", 1)[-1].removesuffix(".html").removesuffix(".htm")
    for pattern in _SLUG_PATTERNS:
        m = pattern.match(stem)
        if m is not None:
            return m.group(1)
    return stem


def _robots_allows(url: str) -> bool:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = RobotFileParser()
    rp.set_url(robots_url)
    try:
        rp.read()
    except Exception:
        # If robots.txt is unreachable, fall through to allow — vatican.va has
        # historically been ambiguous about machine access; the project is
        # already polite (1 req/sec, real UA) and non-commercial.
        return True
    return rp.can_fetch(USER_AGENT, url)


def _throttle() -> None:
    now = time.monotonic()
    elapsed = now - _state["last_request_at"]
    if elapsed < REQUEST_INTERVAL_SECONDS:
        time.sleep(REQUEST_INTERVAL_SECONDS - elapsed)
    _state["last_request_at"] = time.monotonic()


def fetch_encyclical(url: str, slug: str | None = None) -> Path:
    """Fetch *url* and write the HTML to ``tests/fixtures/<slug>.html``.

    If *slug* is omitted, it is derived from the URL via :func:`derive_slug`.
    Returns the path to the written file. Raises ``httpx.HTTPStatusError`` on
    a non-2xx response and ``PermissionError`` if robots.txt disallows the URL.
    """

    if slug is None:
        slug = derive_slug(url)

    if not _robots_allows(url):
        raise PermissionError(f"robots.txt disallows fetching {url!r}")

    _throttle()

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en",
    }
    with httpx.Client(headers=headers, timeout=TIMEOUT_SECONDS, follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()

    out = fixture_path(slug)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(response.content)
    return out
