"""One-shot batch fetch — drives encyclicals_press.fetch in a single process so
the 1 req/sec throttle is honored across all URLs.

Local-only convenience; not committed to the public repo's intended workflow.
"""

from __future__ import annotations

import sys

from encyclicals_press.fetch import fetch_encyclical

URLS = [
    # Paul VI (7 encyclicals)
    "https://www.vatican.va/content/paul-vi/en/encyclicals/documents/hf_p-vi_enc_06081964_ecclesiam.html",
    "https://www.vatican.va/content/paul-vi/en/encyclicals/documents/hf_p-vi_enc_29041965_mense-maio.html",
    "https://www.vatican.va/content/paul-vi/en/encyclicals/documents/hf_p-vi_enc_03091965_mysterium.html",
    "https://www.vatican.va/content/paul-vi/en/encyclicals/documents/hf_p-vi_enc_15091966_christi-matri.html",
    "https://www.vatican.va/content/paul-vi/en/encyclicals/documents/hf_p-vi_enc_26031967_populorum.html",
    "https://www.vatican.va/content/paul-vi/en/encyclicals/documents/hf_p-vi_enc_24061967_sacerdotalis.html",
    "https://www.vatican.va/content/paul-vi/en/encyclicals/documents/hf_p-vi_enc_25071968_humanae-vitae.html",
]


def main() -> int:
    failures: list[tuple[str, str]] = []
    for i, url in enumerate(URLS, 1):
        try:
            path = fetch_encyclical(url)
            print(f"[{i:>2}/{len(URLS)}] OK  {path.name}")
        except Exception as exc:
            print(f"[{i:>2}/{len(URLS)}] ERR {url} -> {exc}", file=sys.stderr)
            failures.append((url, str(exc)))
    if failures:
        print(f"\n{len(failures)} failure(s):", file=sys.stderr)
        for url, err in failures:
            print(f"  {url}: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
