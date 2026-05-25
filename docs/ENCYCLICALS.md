# Encyclicals the parser has been tested against

The repository ships with lorem-ipsum'd fixtures for the documents below; if you want to render the real text, run `encyclicals fetch <url>` against any of these URLs and the pipeline will fill in. The slug is derived from the URL filename automatically.

The project doesn't maintain a code-level URL → slug mapping. This list is documentation, not configuration.

## Benedict XVI

| Slug | Title | Promulgated | URL |
| --- | --- | --- | --- |
| `deus-caritas-est` | *Deus Caritas Est* | 2005-12-25 | <https://www.vatican.va/content/benedict-xvi/en/encyclicals/documents/hf_ben-xvi_enc_20051225_deus-caritas-est.html> |
| `spe-salvi` | *Spe Salvi* | 2007-11-30 | <https://www.vatican.va/content/benedict-xvi/en/encyclicals/documents/hf_ben-xvi_enc_20071130_spe-salvi.html> |
| `caritas-in-veritate` | *Caritas in Veritate* | 2009-06-29 | <https://www.vatican.va/content/benedict-xvi/en/encyclicals/documents/hf_ben-xvi_enc_20090629_caritas-in-veritate.html> |

## Francis

| Slug | Title | Promulgated | URL |
| --- | --- | --- | --- |
| `lumen-fidei` | *Lumen Fidei* | 2013-06-29 | <https://www.vatican.va/content/francesco/en/encyclicals/documents/papa-francesco_20130629_enciclica-lumen-fidei.html> |
| `laudato-si` | *Laudato Si'* | 2015-05-24 | <https://www.vatican.va/content/francesco/en/encyclicals/documents/papa-francesco_20150524_enciclica-laudato-si.html> |
| `fratelli-tutti` | *Fratelli Tutti* | 2020-10-03 | <https://www.vatican.va/content/francesco/en/encyclicals/documents/papa-francesco_20201003_enciclica-fratelli-tutti.html> |
| `dilexit-nos` | *Dilexit Nos* | 2024-10-24 | <https://www.vatican.va/content/francesco/en/encyclicals/documents/20241024-enciclica-dilexit-nos.html> |

## Leo XIV

| Slug | Title | Promulgated | URL |
| --- | --- | --- | --- |
| `magnifica-humanitas` | *Magnifica Humanitas* | 2026-05-15 | <https://www.vatican.va/content/leo-xiv/en/encyclicals/documents/20260515-magnifica-humanitas.html> |

## Bringing in a new document

```sh
uv run encyclicals fetch <url>
uv run encyclicals ingest <slug>
uv run encyclicals build <slug>
```

The `fetch` step caches the HTML under `tests/fixtures/<slug>.html`. The `ingest` step parses it and writes `corpus/<pope>/<slug>.md`. The `build` step renders the corpus markdown to a PDF in `output/`.

If the parser misreads a field you can either:

* hand-edit the corpus markdown (`ingest` refuses to overwrite without `--force`), or
* register a `DocConfig` for the slug in code — see `src/encyclicals_press/_overrides.py`.
