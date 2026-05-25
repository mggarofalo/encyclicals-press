# encyclicals-press

> *Standard Ebooks, but for papal encyclicals.*

Vatican.va publishes encyclicals as HTML — the canonical online source, and the format this project ingests.

This project converts that HTML into a Markdown corpus suited to hand editing, then typesets the result as PDF. The design language is **U.S. Supreme Court slip opinion** — Century-family body, no drop caps, paragraph numbers in the outer margin, italic small-caps rubric blocks. Restraint over ornament.

Encyclicals are magisterial documents cited by paragraph (e.g., *Laudato si'* §49). They share a typographic genre with the published opinions of high courts, and this project sets them in that register.

## Quick start

```sh
uv sync
uv run encyclicals fetch https://www.vatican.va/content/.../some-encyclical.html
uv run encyclicals ingest <slug>
uv run encyclicals build <slug>
```

That's the whole pipeline. The slug is derived from the URL filename. A PDF lands in `output/`. URLs for the documents the parser has been tested against live in [`docs/ENCYCLICALS.md`](docs/ENCYCLICALS.md).

## What's in the box

```
vatican.va HTML
      │  fetch.py        polite httpx (1 req/sec, real UA, robots.txt)
      ▼
tests/fixtures/<slug>.html
      │  parse/          pluggable heuristics + validation + self-healing
      ▼
Encyclical (Pydantic)
      │  normalize.py    smart quotes, dashes, NBSP cleanup
      │  md_writer.py    YAML frontmatter + fenced-div Markdown
      ▼
corpus/<pope>/<slug>.md   ← hand-editable; the project's real artifact
      │  render/         corpus markdown → Typst source → PDF
      ▼
output/<slug>.pdf
```

The corpus directory is the long-lived artifact. Re-running `fetch` and `ingest` is idempotent against the source HTML, but `ingest` won't overwrite an existing corpus file without `--force` — once you've hand-corrected something in the Markdown, it stays.

## Typography

* **6"×9" trim**, U.S. Reports proportions. Mirrored margins (inside 0.75", outside 1.0").
* **TeX Gyre Schola 11pt on 14pt leading**, justified, old-style figures. Vendored under `templates/fonts/` so CI builds are reproducible.
* **Inter** sparingly, on folios and rubric labels.
* **Marginal paragraph numbers** in the outer margin (right on recto, left on verso) — the SCOTUS-citation flourish you'd recognize from a *U.S. Reports* volume.
* **Section openings** in small caps for the first three to five words. No drop caps.
* **Roman-numeral chapter dividers** centered, with the chapter title in small caps beneath.
* **Hung footnotes** at page foot with a 30% rule above.
* **Title pages** sober and centered. Display title in smallcaps, `ENCYCLICAL LETTER` rubric, italic Latin incipit, year in Roman numerals.

The visual register throughout is *Reports of the Supreme Court of the United States*: hierarchy, restraint, and citability over ornament.

## Why lorem-ipsum?

The committed fixtures and corpus markdown carry **lorem ipsum**, not the real encyclical translations. Vatican translations are © Libreria Editrice Vaticana; we'd rather not bake them into a public repository. The fixtures preserve every structural element the parser depends on — paragraph numbers, footnote anchors, section headings, title-block metadata, the dateline — so the parser, validation, and tests still exercise the real shape. Only the prose is replaced.

When you `fetch` a real URL, your working tree fills in with the actual translation. The PDFs render with real text. The repository stays clean.

See [COPYRIGHT.md](COPYRIGHT.md) for the full statement.

## A new encyclical

```sh
uv run encyclicals fetch <vatican.va URL>
```

The slug comes from the URL filename. The HTML is cached under `tests/fixtures/`. The parser's `<link rel="canonical">` extraction recovers `source_url` so nothing else needs to be told.

```sh
uv run encyclicals ingest <slug>
```

This walks the parser's strategy chain, runs the validation pass, and writes `corpus/<pope>/<slug>.md`. Warnings (paragraph-number gaps, footnote ref/def mismatches, missing fields) print to stderr; they're informational and don't fail the ingest.

```sh
uv run encyclicals build <slug>
```

This emits a `.typ` source file alongside the PDF for debugging. `--all` walks every corpus document.

If the parser stumbles on something unusual, you have three options, in increasing order of effort:

1. **Hand-edit the corpus Markdown.** It's plain text. `ingest` won't overwrite without `--force`.
2. **Register a `DocConfig` override** in `src/encyclicals_press/_overrides.py` with `overrides={"field": value}`. Applied after parsing, before validation.
3. **Write a custom `Strategy`** — see `src/encyclicals_press/parse/strategies.py`. Swap any single heuristic (`find_title`, `is_heading`, `chapter_preamble_numeral`, ...) without reimplementing the whole parser.

## Project shape

```
src/encyclicals_press/
├── fetch.py          httpx client + slug derivation
├── parse/            HTML → Encyclical (strategies + validation + self-healing)
├── schema.py         Pydantic models
├── normalize.py      typographic cleanup
├── md_writer.py      Encyclical → corpus Markdown
├── render/           corpus Markdown → Typst → PDF
├── cli.py            click entry point
└── _overrides.py     optional per-slug DocConfig registry

templates/
├── default.typ       page layout, headers, body styles
├── lib/              title-page, colophon, typography helpers
└── fonts/            TeX Gyre Schola + Inter (vendored)

corpus/<pope>/        the long-lived hand-editable artifact
tests/fixtures/       committed snapshot of vatican.va HTML (lorem-ipsum'd)
docs/ENCYCLICALS.md   URLs the parser has been tested against
scripts/              dev tools (lorem_fixtures.py, build-all.sh)
```

The parser's flexibility is the part to read first if you're curious about how this is supposed to scale: every decision lives in a single-responsibility function on a `Strategy` bundle, and the default strategy chain self-heals via a permissive fallback when the default's heuristics would discard real content.

## License

Code, templates, tooling: MIT. Encyclical text: © Libreria Editrice Vaticana — not committed here. [COPYRIGHT.md](COPYRIGHT.md) has the full posture.
