# Encyclicals the parser has been tested against

The repository ships with lorem-ipsum'd fixtures for the documents below; if you want to render the real text, run `encyclicals fetch <url>` against any of these URLs and the pipeline will fill in. The slug is derived from the URL filename automatically.

The project doesn't maintain a code-level URL → slug mapping. This list is documentation, not configuration.

## Paul VI

| Slug | Title | Promulgated | URL |
| --- | --- | --- | --- |
| `ecclesiam-suam` | *Ecclesiam Suam* | 1964-08-06 | <https://www.vatican.va/content/paul-vi/en/encyclicals/documents/hf_p-vi_enc_06081964_ecclesiam.html> |
| `mense-maio` | *Mense Maio* | 1965-04-29 | <https://www.vatican.va/content/paul-vi/en/encyclicals/documents/hf_p-vi_enc_29041965_mense-maio.html> |
| `mysterium-fidei` | *Mysterium Fidei* | 1965-09-03 | <https://www.vatican.va/content/paul-vi/en/encyclicals/documents/hf_p-vi_enc_03091965_mysterium.html> |
| `christi-matri` | *Christi Matri* | 1966-09-15 | <https://www.vatican.va/content/paul-vi/en/encyclicals/documents/hf_p-vi_enc_15091966_christi-matri.html> |
| `populorum-progressio` | *Populorum Progressio* | 1967-03-26 | <https://www.vatican.va/content/paul-vi/en/encyclicals/documents/hf_p-vi_enc_26031967_populorum.html> |
| `sacerdotalis-caelibatus` | *Sacerdotalis Caelibatus* | 1967-06-24 | <https://www.vatican.va/content/paul-vi/en/encyclicals/documents/hf_p-vi_enc_24061967_sacerdotalis.html> |
| `humanae-vitae` | *Humanae Vitae* | 1968-07-25 | <https://www.vatican.va/content/paul-vi/en/encyclicals/documents/hf_p-vi_enc_25071968_humanae-vitae.html> |

The `ecclesiam`, `mysterium`, `populorum`, and `sacerdotalis` URLs use abbreviated filenames on vatican.va — pass `--slug` to land them on full slugs: `encyclicals fetch <url> --slug populorum-progressio` (and so on).

## John Paul II

| Slug | Title | Promulgated | URL |
| --- | --- | --- | --- |
| `redemptor-hominis` | *Redemptor Hominis* | 1979-03-04 | <https://www.vatican.va/content/john-paul-ii/en/encyclicals/documents/hf_jp-ii_enc_04031979_redemptor-hominis.html> |
| `dives-in-misericordia` | *Dives in Misericordia* | 1980-11-30 | <https://www.vatican.va/content/john-paul-ii/en/encyclicals/documents/hf_jp-ii_enc_30111980_dives-in-misericordia.html> |
| `laborem-exercens` | *Laborem Exercens* | 1981-09-14 | <https://www.vatican.va/content/john-paul-ii/en/encyclicals/documents/hf_jp-ii_enc_14091981_laborem-exercens.html> |
| `slavorum-apostoli` | *Slavorum Apostoli* | 1985-06-02 | <https://www.vatican.va/content/john-paul-ii/en/encyclicals/documents/hf_jp-ii_enc_19850602_slavorum-apostoli.html> |
| `dominum-et-vivificantem` | *Dominum et Vivificantem* | 1986-05-18 | <https://www.vatican.va/content/john-paul-ii/en/encyclicals/documents/hf_jp-ii_enc_18051986_dominum-et-vivificantem.html> |
| `redemptoris-mater` | *Redemptoris Mater* | 1987-03-25 | <https://www.vatican.va/content/john-paul-ii/en/encyclicals/documents/hf_jp-ii_enc_25031987_redemptoris-mater.html> |
| `sollicitudo-rei-socialis` | *Sollicitudo Rei Socialis* | 1987-12-30 | <https://www.vatican.va/content/john-paul-ii/en/encyclicals/documents/hf_jp-ii_enc_30121987_sollicitudo-rei-socialis.html> |
| `redemptoris-missio` | *Redemptoris Missio* | 1990-12-07 | <https://www.vatican.va/content/john-paul-ii/en/encyclicals/documents/hf_jp-ii_enc_07121990_redemptoris-missio.html> |
| `centesimus-annus` | *Centesimus Annus* | 1991-05-01 | <https://www.vatican.va/content/john-paul-ii/en/encyclicals/documents/hf_jp-ii_enc_01051991_centesimus-annus.html> |
| `veritatis-splendor` | *Veritatis Splendor* | 1993-08-06 | <https://www.vatican.va/content/john-paul-ii/en/encyclicals/documents/hf_jp-ii_enc_06081993_veritatis-splendor.html> |
| `evangelium-vitae` | *Evangelium Vitae* | 1995-03-25 | <https://www.vatican.va/content/john-paul-ii/en/encyclicals/documents/hf_jp-ii_enc_25031995_evangelium-vitae.html> |
| `ut-unum-sint` | *Ut Unum Sint* | 1995-05-25 | <https://www.vatican.va/content/john-paul-ii/en/encyclicals/documents/hf_jp-ii_enc_25051995_ut-unum-sint.html> |
| `fides-et-ratio` | *Fides et Ratio* | 1998-09-14 | <https://www.vatican.va/content/john-paul-ii/en/encyclicals/documents/hf_jp-ii_enc_14091998_fides-et-ratio.html> |
| `ecclesia-de-eucharistia` | *Ecclesia de Eucharistia* | 2003-04-17 | <https://www.vatican.va/content/john-paul-ii/en/encyclicals/documents/hf_jp-ii_enc_20030417_eccl-de-euch.html> |

The 2003 *Ecclesia de Eucharistia* URL is the exception to the slug-from-URL rule — vatican.va abbreviates its filename as `eccl-de-euch`, so the slug must be passed explicitly: `encyclicals fetch <url> --slug ecclesia-de-eucharistia`.

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

The `fetch` step caches the HTML under `input/<slug>.html` (gitignored). The `ingest` step parses it and writes `corpus/<pope>/<slug>.md` (also gitignored — both directories are local working state, never committed). The `build` step renders the corpus markdown to a PDF in `output/`.

If the parser misreads a field you can either:

* hand-edit the corpus markdown (`ingest` refuses to overwrite without `--force`), or
* register a `DocConfig` for the slug in code — see `src/encyclicals_press/_overrides.py`.
