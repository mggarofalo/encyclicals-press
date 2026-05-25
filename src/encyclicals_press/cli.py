"""Command-line entry point for encyclicals-press."""

from __future__ import annotations

import re
from pathlib import Path

import click

from . import __version__
from .fetch import fetch_encyclical, fixture_path
from .md_writer import write_markdown
from .normalize import normalize
from .parse import parse_with_attempts
from .parse.validate import ParseWarning
from .render import render


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
@click.argument("url")
@click.option(
    "--slug",
    "slug_override",
    default=None,
    help="Override the slug; otherwise derived from the URL filename.",
)
def fetch(url: str, slug_override: str | None) -> None:
    """Fetch URL from vatican.va into tests/fixtures/<slug>.html.

    The slug is derived from the URL filename (the project-style identifier
    inside vatican.va's longer filenames). Pass --slug to override.
    """
    path = fetch_encyclical(url, slug=slug_override)
    click.echo(f"wrote {path}")


_SEVERITY_COLORS = {"error": "red", "warn": "yellow", "info": "cyan"}


def _report_warnings(warnings: list[ParseWarning], strategy_name: str) -> None:
    """Print parse warnings as colored, structured lines on stderr."""
    if not warnings:
        return
    for w in warnings:
        color = _SEVERITY_COLORS.get(w.severity, "white")
        prefix = click.style(f"  {w.severity:>5}", fg=color, bold=True)
        code = click.style(w.code, dim=True)
        click.echo(f"{prefix} {code}  {w.message}", err=True)
    click.echo(click.style(f"  (strategy: {strategy_name})", dim=True, italic=True), err=True)


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
    attempts = parse_with_attempts(fixture.read_text(encoding="utf-8"), slug=slug)
    winning = next(
        (
            a
            for a in attempts
            if a.encyclical is not None and all(w.severity != "error" for w in a.warnings)
        ),
        attempts[-1],
    )
    if winning.encyclical is None:
        raise click.ClickException(
            f"all strategies failed for {slug!r}: "
            + "; ".join(f"{a.strategy_name}: {a.warnings[0].message}" for a in attempts)
        )
    if winning.warnings:
        _report_warnings(winning.warnings, winning.strategy_name)
    encyclical = normalize(winning.encyclical)
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
    root = _project_root()
    output_dir = root / "output"
    targets: list[Path] = []
    if all_:
        targets = sorted(root.glob("corpus/*/*.md"))
        if not targets:
            raise click.ClickException("no corpus documents found")
    else:
        if slug is None:
            raise click.ClickException("specify a <slug> or pass --all")
        matches = list(root.glob(f"corpus/*/{slug}.md"))
        if not matches:
            raise click.ClickException(
                f"no corpus document found for slug {slug!r}; run `encyclicals ingest {slug}` first"
            )
        targets = matches

    for corpus_path in targets:
        slug_name = corpus_path.stem
        pdf_path = output_dir / f"{slug_name}.pdf"
        click.echo(f"rendering {corpus_path.relative_to(root)} -> {pdf_path.relative_to(root)}")
        render(corpus_path, pdf_path)


if __name__ == "__main__":  # pragma: no cover
    main()
