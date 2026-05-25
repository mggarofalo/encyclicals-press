"""Tests for the strategy abstraction and the self-healing chain."""

from __future__ import annotations

from pathlib import Path

import pytest

from encyclicals_press import _url_map
from encyclicals_press.parse import (
    DEFAULT_CHAIN,
    DEFAULT_STRATEGY,
    PERMISSIVE_STRATEGY,
    ParseAttempt,
    parse,
    parse_with_attempts,
)
from encyclicals_press.parse.strategies import get as get_strategy
from encyclicals_press.parse.strategies import register

FIXTURE = Path(__file__).parent / "fixtures" / "spe-salvi.html"
SPE_SALVI_FOOTNOTE_COUNT = 40


@pytest.fixture(scope="module")
def html() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def test_default_strategy_parses_spe_salvi(html: str) -> None:
    enc = parse(html, slug="spe-salvi", emit_warnings=False)
    assert enc.title == "Spe Salvi"
    assert enc.pope == "Benedict XVI"
    assert len(enc.footnotes) == SPE_SALVI_FOOTNOTE_COUNT


def test_strategy_replace_returns_new_strategy() -> None:
    custom = DEFAULT_STRATEGY.replace(name="custom")
    assert custom.name == "custom"
    assert custom is not DEFAULT_STRATEGY
    # Unrelated fields are preserved verbatim.
    assert custom.find_body is DEFAULT_STRATEGY.find_body


def test_strategy_is_frozen() -> None:
    with pytest.raises(AttributeError):
        DEFAULT_STRATEGY.name = "should-fail"  # type: ignore[misc]


def test_named_strategy_lookup() -> None:
    assert get_strategy("default") is DEFAULT_STRATEGY
    assert get_strategy("permissive") is PERMISSIVE_STRATEGY
    with pytest.raises(KeyError):
        get_strategy("unregistered-name")


def test_register_makes_strategy_lookable() -> None:
    custom = DEFAULT_STRATEGY.replace(name="test-register-target")
    register(custom)
    assert get_strategy("test-register-target") is custom


def test_chain_returns_first_clean_attempt(html: str) -> None:
    attempts = parse_with_attempts(html, slug="spe-salvi")
    # Spe Salvi should succeed on the very first strategy.
    assert len(attempts) == 1
    assert attempts[0].strategy_name == "default"
    assert attempts[0].encyclical is not None


def test_default_chain_includes_permissive_fallback() -> None:
    assert DEFAULT_STRATEGY in DEFAULT_CHAIN
    assert PERMISSIVE_STRATEGY in DEFAULT_CHAIN
    # The default must come first — permissive is the fallback.
    assert DEFAULT_CHAIN[0] is DEFAULT_STRATEGY


def test_explicit_strategy_bypasses_chain(html: str) -> None:
    attempts = parse_with_attempts(html, slug="spe-salvi", strategy=PERMISSIVE_STRATEGY)
    assert len(attempts) == 1
    assert attempts[0].strategy_name == "permissive"


def test_crashing_strategy_is_caught(html: str) -> None:
    def boom(_tree):
        raise RuntimeError("simulated parser crash")

    crashing = DEFAULT_STRATEGY.replace(name="crash-test", find_body=boom)
    attempts = parse_with_attempts(html, slug="spe-salvi", strategies=[crashing])
    assert attempts[0].encyclical is None
    assert any(w.code == "strategy-crashed" for w in attempts[0].warnings)


def test_chain_falls_back_after_failure(html: str) -> None:
    def boom(_tree):
        raise RuntimeError("simulated")

    crashing = DEFAULT_STRATEGY.replace(name="will-crash", find_body=boom)
    chain = [crashing, DEFAULT_STRATEGY]
    attempts = parse_with_attempts(html, slug="spe-salvi", strategies=chain)
    assert len(attempts) == len(chain)
    assert attempts[0].encyclical is None
    assert attempts[1].encyclical is not None
    assert attempts[1].encyclical.title == "Spe Salvi"


def test_doc_config_overrides_patch_fields(html: str, monkeypatch) -> None:
    monkeypatch.setitem(
        _url_map.URL_MAP,
        "spe-salvi",
        _url_map.DocConfig(
            url=_url_map.URL_MAP["spe-salvi"]
            if isinstance(_url_map.URL_MAP["spe-salvi"], str)
            else _url_map.URL_MAP["spe-salvi"].url,
            overrides={"incipit": "Custom Override"},
        ),
    )
    enc = parse(html, slug="spe-salvi", emit_warnings=False)
    assert enc.incipit == "Custom Override"


def test_doc_config_strategy_name_uses_specific_strategy(html: str, monkeypatch) -> None:
    monkeypatch.setitem(
        _url_map.URL_MAP,
        "spe-salvi",
        _url_map.DocConfig(
            url=_url_map.URL_MAP["spe-salvi"]
            if isinstance(_url_map.URL_MAP["spe-salvi"], str)
            else _url_map.URL_MAP["spe-salvi"].url,
            strategy="permissive",
        ),
    )
    attempts = parse_with_attempts(html, slug="spe-salvi")
    assert attempts[0].strategy_name == "permissive"


def test_parse_attempt_dataclass_carries_warnings(html: str) -> None:
    attempts = parse_with_attempts(html, slug="spe-salvi")
    assert isinstance(attempts[0], ParseAttempt)
    assert hasattr(attempts[0], "warnings")
    # Spe Salvi should parse cleanly with no errors.
    assert not any(w.severity == "error" for w in attempts[0].warnings)
