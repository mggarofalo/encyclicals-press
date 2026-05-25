"""Command-line entry point for encyclicals-press."""

from __future__ import annotations

import re
from pathlib import Path

import click

from . import __version__
from .fetch import fetch_encyclical, fixture_path
from .md_writer import write_markdown
from .normalize import normalize
from .parse import parse as parse_html


def _project_root() -> Path:
    # src/encyclicals_press/cli.py -> project root is two parents above src/.
    return Path(__file__).resolve().parents[2]


def _pope_slug(pope: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", pope.lower()).strip("-")


def _corpus_path(pope: str, slug: str) -> Path:
    return _project_root() / "corpus" / _pope_slug(pope) / f"{slug}.md"


@click.group()
@click.version_option(__version__, prog_name="encyclicals")
def main() -> None:
    """Fetch, ingest, and typeset papal encyclicals."""


@main.command()
@click.argument("slug")
def fetch(slug: str) -> None:
    """Fetch <slug> from vatican.va into tests/fixtures/<slug>.html."""
    path = fetch_encyclical(slug)
    click.echo(f"wrote {path}")


@main.command()
@click.argument("slug")
@click.option("--force", is_flag=True, help="Overwrite an existing corpus file.")
def ingest(slug: str, force: bool) -> None:
    """Parse the cached HTML for <slug> into the Markdown corpus."""
    fixture = fixture_path(slug)
    if not fixture.exists():
        raise click.ClickException(
            f"fixture {fixture} not found; run `encyclicals fetch {slug}` first"
        )
    encyclical = normalize(parse_html(fixture.read_text(encoding="utf-8"), slug=slug))
    target = _corpus_path(encyclical.pope, slug)
    if target.exists() and not force:
        raise click.ClickException(f"refusing to overwrite {target} (pass --force to allow)")
    write_markdown(encyclical, target)
    click.echo(f"wrote {target}")


@main.command()
@click.argument("slug", required=False)
@click.option("--all", "all_", is_flag=True, help="Render every corpus document.")
def build(slug: str | None, all_: bool) -> None:
    """Render <slug> (or --all corpus files) to output/<slug>.pdf."""
    raise click.ClickException("build is not implemented yet (Stage 5)")


if __name__ == "__main__":  # pragma: no cover
    main()
