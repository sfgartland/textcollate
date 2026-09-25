---
name: collate-editions
description: Use when the user has several versions of the same text (scans, PDFs, a website, a transcription, a translation) and wants to compare them, decide which is better, find out whether they really differ, repair OCR errors in one from another, or check that a source is complete. Trigger on "compare these two editions/versions/scans", "is this scan complete", "hidden pages", "which text is cleaner", "differences between the German and the Neske text", "fix the OCR using the other copy". Drives the `textcollate` CLI.
---

# Compare editions of a text

Uses the `textcollate` CLI (source and docs: https://github.com/sfgartland/textcollate). Run it as `textcollate ...`: the plugin's `bin/`
launcher puts it on PATH and falls back to `uvx --from git+https://github.com/sfgartland/textcollate textcollate ...` (needs only `uv`).
Run `textcollate doctor` first: it checks poppler, tesseract, a TeX engine and OCR language data.

## Procedure

1. **Inventory the sources first.** For every file: `pdfinfo`, then `pdftotext -f N -l N` on a few pages (first, middle, last,
   and the pages you need). Does it have a text layer or is it an image? Are there placeholder pages ("Hidden page",
   blank)? `pdfimages -list` shows pages without an image. Report what you found before building anything.
2. **Never modify originals.** Work in a project directory (`textcollate init DIR`); outputs go to `build/`.
3. **Write `textcollate.toml`**: one `[[edition]]` per version (source type `pdf-text`, `pdf-ocr`, `html-pages`, `text`),
   its own page labels (`[edition.pages]`). Copy from the example projects in the repository (`examples/gelassenheit/`, `examples/resem-phen/`).
   For scans, `textcollate doctor --lang deu` and `textcollate fetch-tessdata deu` if the language data is missing.
4. `textcollate extract` -- read the summary (paragraph count, own page labels first..last). A wrong count is a layout
   problem: tune `[edition.layout]` (`paragraphs`, `indent_frac`, `furniture`, `notes`).
5. `textcollate compare A B` -> `build/reports/compare_A_B.md`. Read the *substantive* rows; treat *ocr-like* rows as noise
   unless they cluster. Genuine variants between editions are the interesting result -- say which edition reads what.
6. To repair the weaker edition from the stronger one: an `[[output]] kind = "single"` with `[output.collate] refs = [...]`;
   read `build/reports/<id>.collate.txt` (every correction is listed; `unresolved` = variants or errors in the reference).

## Rules

* Born-digital text (html, plain text) may repair OCR, never the reverse. Do not call a PDF text layer of a scan born-digital.
* Verify by two independent means (word diff against another edition; rendering the pages you care about) before saying a
  text is correct. State what was *not* verified (unproofread OCR, italics).
* Report page-level facts precisely: which pages are missing/blank, which page range covers which material.
