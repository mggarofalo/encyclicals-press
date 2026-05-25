"""Polite client for fetching encyclical HTML from vatican.va.

Single-document fetch. Caches the response body to ``tests/fixtures/<slug>.html``
so downstream stages develop against a committed snapshot rather than re-hitting
the Vatican every iteration.
"""

from __future__ import annotations

import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from ._url_map import url_for

USER_AGENT = "encyclicals-press/0.1 (+https://github.com/mggarofalo/encyclicals-press)"
REQUEST_INTERVAL_SECONDS = 1.0
TIMEOUT_SECONDS = 30.0

_last_request_at: float = 0.0


def _project_root() -> Path:
    # src/encyclicals_press/fetch.py -> project root is two parents above src/.
    return Path(__file__).resolve().parents[2]


def fixture_path(slug: str) -> Path:
    return _project_root() / "tests" / "fixtures" / f"{slug}.html"


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
    global _last_request_at
    now = time.monotonic()
    elapsed = now - _last_request_at
    if elapsed < REQUEST_INTERVAL_SECONDS:
        time.sleep(REQUEST_INTERVAL_SECONDS - elapsed)
    _last_request_at = time.monotonic()


def fetch_encyclical(slug: str) -> Path:
    """Fetch *slug* from vatican.va and write the HTML to ``tests/fixtures/<slug>.html``.

    Returns the path to the written file. Raises ``httpx.HTTPStatusError`` on a
    non-2xx response and ``PermissionError`` if robots.txt disallows the URL.
    """

    url = url_for(slug)

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
