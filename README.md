# encyclicals-press

A typesetting pipeline that fetches papal encyclicals from vatican.va, normalizes them into a Git-tracked Markdown corpus, and renders them as dignified PDF editions via Typst. The design language is U.S. Supreme Court slip opinion: Century Schoolbook body, no drop caps, marginal paragraph numbers, italic small-caps rubric blocks, restraint over ornament. *Standard Ebooks for encyclicals* — not another aggregator.

## Why

Vatican.va's HTML is structurally loose and visually inconsistent; the PDFs it offers are afterthoughts. Papal encyclicals are magisterial documents cited by paragraph (LS §49) — the typographic genre they share is not the devotional missal but the published opinion of a high court. This project treats them that way.

## Quick start

```bash
uv sync
uv run encyclicals build spe-salvi    # produces output/spe-salvi.pdf
uv run encyclicals build --all        # renders the whole corpus
```

Adding a new encyclical:

```bash
uv run encyclicals fetch <slug>       # cache the vatican.va HTML
uv run encyclicals ingest <slug>      # parse -> corpus/<pope>/<slug>.md
uv run encyclicals build <slug>       # corpus markdown -> PDF
```

The slug is the project's stable identifier (e.g. `spe-salvi`, `caritas-in-veritate`). Register new slugs in `src/encyclicals_press/_url_map.py`.

## Pipeline

```
vatican.va HTML
      │  fetch.py        (httpx, 1 req/sec, polite)
      ▼
tests/fixtures/<slug>.html
      │  parse/          (pluggable heuristics + validation + self-healing)
      ▼
Encyclical (pydantic model — paragraphs, footnotes, metadata)
      │  normalize.py    (smart quotes, dashes, NBSP cleanup)
      │  md_writer.py    (YAML frontmatter + fenced-div Markdown)
      ▼
corpus/<pope>/<slug>.md   ← the project's actual product, hand-editable
      │  render.py       (custom md→Typst, no Pandoc dep)
      ▼
output/<slug>.pdf
```

The corpus directory is the long-lived artifact. Re-running `fetch` and `ingest` is idempotent against the source HTML, but `ingest` refuses to overwrite an existing corpus file without `--force` — once you've hand-corrected something in the Markdown, it stays.

## Typography

* **Trim:** 6"×9", U.S. Reports proportions.
* **Body:** TeX Gyre Schola 11pt on 14pt leading, justified, old-style figures.
* **Marginalia:** Inter 7pt for paragraph numbers in the outer margin; Inter 8pt small caps for running headers.
* **Section openings:** first 3–5 words in real small caps, no drop cap, no ornament.
* **Chapter dividers:** centered Roman numeral with the section title beneath in small caps.
* **Footnotes:** hung, at page foot, 9pt, with rule above.
* **Title page:** sober and centered — display title, "ENCYCLICAL LETTER" rubric, pope's name in small caps, Latin incipit at the foot, year in Roman numerals.
* **Salutation:** italic small caps as a rubric preamble before the numbered body, directly parallel to SCOTUS's "JUSTICE X delivered the opinion of the Court."

Fonts are vendored under `templates/fonts/` so CI builds are reproducible.

## Parser flexibility

Vatican.va's HTML drifts across pontificates. The parser is designed for it: every decision point — where the title lives, what counts as a heading, how to find footnote definitions, where the dateline sits — is a named, single-responsibility function on a `Strategy` bundle. The default strategy handles every document the project currently ships; novel layouts hit a permissive fallback before the parser gives up.

Three knobs, in increasing power:

* **Override one field on a strategy.** `DEFAULT_STRATEGY.replace(find_title=my_finder)` swaps the title-paragraph locator without touching anything else.
* **Register a named strategy** and point a document at it from the URL_MAP:
  ```python
  URL_MAP["my-doc"] = DocConfig(url="...", strategy="my-strategy")
  ```
* **Field-level overrides** for individual documents (no code change):
  ```python
  URL_MAP["weird-doc"] = DocConfig(
      url="...",
      overrides={"incipit": "Magnifica humanitas"},
  )
  ```

After parsing, a validation pass checks for missing fields, paragraph-number gaps, and footnote ref/def mismatches. Errors trigger fallback to the next strategy; warnings surface to the user without blocking the ingest.

## Contributing a new encyclical

1. Find the canonical English-language vatican.va URL for the document.
2. Add it to `URL_MAP` in `src/encyclicals_press/_url_map.py` (plain URL string, or `DocConfig(...)` for a strategy/overrides).
3. `uv run encyclicals fetch <slug>` — caches the HTML to `tests/fixtures/`.
4. `uv run encyclicals ingest <slug>` — produces `corpus/<pope>/<slug>.md`. Validation warnings, if any, print to stderr.
5. If the parser stumbles, either:
   * write a custom strategy (see `parse/strategies.py`) and register it,
   * patch the offending field via `DocConfig.overrides`, or
   * hand-edit the corpus Markdown — `ingest` won't overwrite without `--force`.
6. `uv run encyclicals build <slug>` and inspect the PDF.
7. PR with the new corpus file, the cached fixture, and any heuristic tweaks.

## Status

The repository currently ships eight encyclicals across three pontificates, all parsing cleanly without per-document overrides:

* **Benedict XVI:** *Deus Caritas Est* (2005), *Spe Salvi* (2007), *Caritas in Veritate* (2009)
* **Francis:** *Lumen Fidei* (2013), *Laudato Si'* (2015), *Fratelli Tutti* (2020), *Dilexit Nos* (2024)
* **Leo XIV:** *Magnifica Humanitas* (2026)

PDFs build via `uv run encyclicals build --all`; CI uploads them as artifacts.

See [COPYRIGHT.md](COPYRIGHT.md) for licensing.
