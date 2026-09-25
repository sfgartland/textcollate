---
name: page-marked-latex
description: Use when the user wants a clean LaTeX (or typeset PDF) version of a text taken from a scan/PDF/website, with the page breaks of a standard edition marked ("original pagination", "GA 16 pages", "Akademie-Ausgabe", "A/B pagination", "Bekker numbers", "page references so it is easy to cite"). Also for turning an OCR'd scan into clean text while keeping page references, and for extracting a page range of a PDF as its own file. Drives the `textcollate` CLI.
---

# Clean LaTeX with original pagination

CLI: `textcollate` (the plugin's `bin/` launcher puts it on PATH; it uses an installed copy, `$TEXTCOLLATE_HOME`, or fetches it from GitHub with `uvx` -- needs only `uv`; poppler, tesseract and a TeX engine are checked by `textcollate doctor`). Reference project:
`examples/gelassenheit/` in the repository (German text, Neske pages + GA 16 pages).

## Procedure

1. Identify **which edition supplies the text** (best OCR / text layer) and **which edition's page numbers** the user cites.
   The two may be different sources; the citing edition only needs to give the words around its page breaks (a website that
   publishes book pages, a second scan, even a list of anchors).
2. Extract the page range as its own PDF when asked: `qpdf in.pdf --pages . 13-30 -- out.pdf` (mind the offset between printed
   page and PDF page; check with `pdftotext -f N -l N` that the first and last page are right).
3. Set up the project (see the `collate-editions` skill for source inventory; scans: `textcollate fetch-tessdata deu`).
   Output: `[[output]] kind = "single" edition = "TEXT" marks = ["TEXT", "CITED"]` with
   `[output.collate] refs = ["CITED", ...] paragraph_starts = ["CITED"] marks_from = ["CITED"]`.
4. Pages of the cited edition that no source provides: declare the break with `[[edition.mark_at]]`
   (`edition`, `label`, `before = "the first words of that page"`), and say so in the answer.
5. Restore emphasis the OCR loses: `[[edition.italic]]`, from images or another edition; never guess.
6. `textcollate build <id>`; open the PDF (`pdftoppm -r 80`) and check: title, page marks (inline and margin), page breaks that
   fall inside a word, block quotations, footnotes, no stray OCR debris.
7. Give the user: the `.tex`, the `.pdf`, and a bib entry (`textcollate bib`) with the edition it is based on. Keep the old
   outputs when asked ("keep the old ones") -- use a new `id`.

## Rules

* Say which parts are OCR and unproofread. Do not present them as verified text.
* Page marks that could not be placed must be reported, not dropped silently. `textcollate` errors on missing anchors; read
  the collate report (`marks carried over`).
* Compile with the configured engine; a LaTeX error is a bug to fix, not a reason to skip the PDF.
