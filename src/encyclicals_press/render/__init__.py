"""Render a corpus Markdown file into a typeset PDF.

Pipeline (three stages, each in its own module):

#. :mod:`.corpus_reader` parses the YAML frontmatter and the fenced-div
   Markdown body into a :class:`ParsedCorpus`.
#. :mod:`.typst_emitter` walks the parsed blocks and emits a Typst
   source string that imports the project templates and applies the
   ``edition`` show rule.
#. The bundled ``typst`` compiler turns the source into a PDF.

The only public entry point is :func:`render`. The intermediate forms
are exposed for tests and tooling.
"""

from __future__ import annotations

from pathlib import Path

import typst

from .corpus_reader import Block, ParsedCorpus, read_corpus
from .markdown import (
    escape_typst,
    inline_to_typst,
    inline_to_typst_markup,
    wrap_section_opening,
)
from .typst_emitter import emit_typst

__all__ = [
    "Block",
    "ParsedCorpus",
    "emit_typst",
    "escape_typst",
    "inline_to_typst",
    "inline_to_typst_markup",
    "read_corpus",
    "render",
    "wrap_section_opening",
]


def render(corpus_path: Path, output_path: Path) -> Path:
    """Render the corpus Markdown at *corpus_path* to a PDF at *output_path*.

    Writes the intermediate ``.typ`` file alongside the PDF so failures
    can be debugged without re-running the pipeline. Returns the
    *output_path* for convenience.
    """
    parsed = read_corpus(corpus_path)
    typst_source = emit_typst(parsed)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    typ_path = output_path.with_suffix(".typ")
    typ_path.write_text(typst_source, encoding="utf-8", newline="\n")

    template_root = _template_root()
    typst.compile(
        str(typ_path),
        output=str(output_path),
        root=str(template_root.parent),
        font_paths=[str(template_root / "fonts")],
    )
    return output_path


def _template_root() -> Path:
    # src/encyclicals_press/render/__init__.py -> project root -> templates/
    return Path(__file__).resolve().parents[3] / "templates"
