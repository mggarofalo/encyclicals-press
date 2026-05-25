"""Polite client for fetching encyclical HTML from vatican.va.

Implemented in Stage 2.
"""

from __future__ import annotations

from pathlib import Path


def fetch_encyclical(slug: str) -> Path:
    """Fetch the encyclical identified by *slug* and cache it under tests/fixtures."""
    raise NotImplementedError("fetch is implemented in Stage 2")
