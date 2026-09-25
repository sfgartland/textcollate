# textcollate

Put several versions of the same text side by side, keep the **original pagination** of each, and typeset clean or parallel
LaTeX from them.

Typical situations it was built for (a philosophy student's daily bread):

* you have a **bad scan, a good scan, a website and a translation** of one text, and want one clean text that still says
  where each page of *the edition you cite* begins;
* you want to know **whether two editions really differ** (OCR noise vs. a genuine variant);
* you want a **side-by-side translation** whose columns carry the page numbers of the standard edition.

It grew out of exactly one job -- Heidegger's *Gelassenheit* (Neske 1960) beside *Memorial Address* (Anderson/Freund 1966), with
the page breaks of *Gesamtausgabe* vol. 16 in both -- and `examples/gelassenheit` reproduces that job from a single config file.

```
sources ──▶ editions ──▶ collate ──▶ outputs
pdf text layer   paragraphs        repair OCR slips        single: clean LaTeX with page marks
scan + OCR       + notes           paragraph starts        parallel: German | English with the
html pages       + own page marks  page marks between      standard edition's page breaks
plain text                         editions                in both columns, notes, concordance
```

## Install

```bash
cd ~/programing_linux/textcollate
uv sync                       # no third-party runtime dependencies
uv tool install --editable .  # optional: puts `textcollate` on PATH
textcollate doctor            # checks pdftotext, tesseract, lualatex ...
textcollate fetch-tessdata deu   # OCR language data without sudo (~/.local/share/tessdata)
```

Needs poppler (`pdftotext`, `pdfimages`, `pdftoppm`), tesseract (only for scans), a TeX engine (`lualatex`) and, for some
scan options, ImageMagick.

## Quick start

```bash
textcollate init myproject && cd myproject      # writes textcollate.toml
$EDITOR textcollate.toml                        # declare editions and outputs
textcollate extract                             # build editions -> build/editions/*.json
textcollate compare scan website                # how do two editions differ?
textcollate build                               # LaTeX + PDF in build/out/
textcollate bib                                 # biblatex entries for editions and outputs
```

A minimal project:

```toml
[[edition]]                       # a clean transcription, one HTML file per page
id = "web"; label = "Website"; language = "de"
[edition.source]
type = "html-pages"; pattern = "html/p{page}.html"; pages = "517-525"
[edition.mark_style]
label = "GA 16"; color = "8B1E1E"; bold = true; margin = "left"

[[edition]]                       # a scan whose text layer is fine
id = "scan"; label = "Neske 1960"; language = "de"
[edition.source]
type = "pdf-text"; path = "neske.pdf"; pages = "13-30"
[edition.pages]
first = 11                        # printed label of the first page listed
[edition.layout]
paragraphs = "shortline"

[[output]]
id = "clean"; kind = "single"; edition = "scan"; marks = ["scan", "web"]
[output.collate]                  # repair the scan against the website, take its page breaks
refs = ["web"]; paragraph_starts = ["web"]; marks_from = ["web"]
```

## Concepts

* **Edition** -- one version of the text, reduced to *paragraphs* in which zero-width sentinels carry structure
  (`marks.py`): page marks of any edition, footnote markers, emphasis, line breaks. Because marks travel inside the text, every
  later stage keeps them in the right place.
* **Trust** -- born-digital text (html, text) counts 1.0, OCR 0.5. When two editions repair each other the more trustworthy
  one wins; every correction is written to `build/reports/*.collate.txt`.
* **Collate** (same language) -- word-level alignment (`collate.py`). Fixes OCR slips, restores words a text layer dropped,
  takes paragraph starts from the reference, and carries page marks across, including a page break *inside a word*
  (`Be|denken`).
* **Bitext** (two languages) -- paragraph blocks by dynamic programming over anchors + length, then sentence groups
  (`bitext.py`). A page mark falls exactly where a sentence group starts, otherwise it is placed proportionally and flagged
  approximate (`≈`).
* **Outputs** -- `single` (clean article-style LaTeX; page marks inline and in the margin) and `parallel` (paracol, landscape,
  footnotes of the translation preserved, concordance table of page numbers).

See [docs/config.md](docs/config.md) (every option), [docs/workflows.md](docs/workflows.md) (recipes),
[docs/ocr.md](docs/ocr.md) (OCR engines, italics, scans), [docs/lessons.md](docs/lessons.md) (what went wrong the first time).

## Claude Code plugin

`plugin/` packages the workflows as skills (compare editions, page-marked LaTeX, parallel translation). Install:

```bash
claude plugin marketplace add ~/programing_linux/textcollate
claude plugin install textcollate@textcollate
```

The skills call `textcollate` (on PATH after `uv tool install`, or `uv run --project $TEXTCOLLATE_HOME textcollate`).

## Development

```bash
uv run pytest -q          # unit tests + a toy project built end to end (PDF included)
uv run ruff check .
```

Limits worth knowing: alignment uses `difflib` (fine for a chapter or article; for a whole book collate chapter by chapter);
OCR output is only as good as the scan (see docs/ocr.md); italics are not detected by tesseract -- restore them with
`[[edition.italic]]` or use an OCR engine that emits Markdown (`engine = "command"`).
