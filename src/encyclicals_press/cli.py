"""Command-line entry point for encyclicals-press."""

from __future__ import annotations

import click

from . import __version__
from .fetch import fetch_encyclical


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
    raise click.ClickException("ingest is not implemented yet (Stage 4)")


@main.command()
@click.argument("slug", required=False)
@click.option("--all", "all_", is_flag=True, help="Render every corpus document.")
def build(slug: str | None, all_: bool) -> None:
    """Render <slug> (or --all corpus files) to output/<slug>.pdf."""
    raise click.ClickException("build is not implemented yet (Stage 5)")


if __name__ == "__main__":  # pragma: no cover
    main()
