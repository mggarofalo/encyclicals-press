#!/usr/bin/env bash
# Render every corpus document to output/*.pdf.
set -euo pipefail
cd "$(dirname "$0")/.."
uv sync --frozen
uv run encyclicals build --all
