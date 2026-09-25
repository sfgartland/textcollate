---
name: parallel-translation
description: Use when the user wants a side-by-side (dual column, parallel, bilingual, interlinear-ish) layout of a text and its translation, especially with page references of a standard edition in both columns, preserved translator's footnotes, or a check that the translation covers the same material as the original. Trigger on "German on one side and English on the other", "dual page layout", "does the English cover the same as the German", "page mapping between original and translation". Drives the `textcollate` CLI.
---

# Parallel text with page mapping

CLI: `textcollate` (else `uv run --project ${TEXTCOLLATE_HOME:-~/programing_linux/textcollate} textcollate`). Reference project:
`~/programing_linux/textcollate/examples/gelassenheit/` (German left, English right, GA 16 pages in both).

## Procedure

1. Prepare the **original** as in the `page-marked-latex` skill (collated, with the standard edition's marks).
2. Prepare the **translation** as an edition. A PDF whose own text layer is scrambled or missing: `pdf-ocr` (`images = "smask"`
   for MRC scans, else `render`). Translator's footnotes: `notes = {min_y = ...}` for the small bottom lines and one
   `[[edition.note_marker]]` per note. **Find marker positions on the page image** -- OCR reads a superscript as a quote mark.
3. `[[output]] kind = "parallel" left right transfer = ["STANDARD"] marks = [LEFT, RIGHT, "STANDARD"] concordance = "STANDARD"`.
4. **Coverage check.** Write 30-70 `[[output.anchor]]` pairs (a distinctive phrase in each language, in order through the text)
   and run `textcollate check <id>`: all must be found, in the same order, in both texts. Report differences of substance
   (omissions, place names swapped, added notes, terminology) -- they are usually the useful finding.
5. `textcollate build <id>`; read `build/reports/<id>.align.txt`: block shapes and, for every carried page mark, the German and
   English context. Marks flagged `approx` sit inside a sentence by proportion; say that they are approximate.
6. Look at the PDF: both titles, marks in both columns, footnotes at the bottom of the right column, the concordance table.

## Rules

* The translation's own page numbers appear in the concordance; the standard edition's marks are *carried*, not read from
  the translation. Never claim they are exact beyond sentence starts.
* Cite the published editions in the bibliography (`[edition.bib]`); the parallel PDF is a working edition.
* A translation that differs materially from the original (added or dropped sentences) may break the alignment; then pin
  paragraph pairs (`pins`) or add anchors, and mention it.
