# Workflows

All three start with `textcollate doctor` and end with a look at the PDF (`pdftoppm -r 80`) -- not only at the log.

## 1. Which version is better / do two editions differ?

1. Declare both as `[[edition]]` (`pdf-text` if the text layer is decent, `pdf-ocr` otherwise), give each its own page labels.
2. `textcollate extract` -- check paragraph counts and the first/last own page label it prints.
3. `textcollate compare a b` -> `build/reports/compare_a_b.md`. The report separates
   *ocr-like* (one word, edit distance <= 2), *spacing/hyphenation* and *substantive* differences. Only the last need reading.
4. If one edition is born digital (html, text) let it repair the weaker one (`[output.collate]`) and read
   `build/reports/*.collate.txt`: every correction is listed, plus the `unresolved` differences -- those are either genuine
   variants or errors in the *reference*.

## 2. Clean LaTeX with the original pagination

Goal: the text of edition A, typeset cleanly, with the page breaks of the edition B you cite.

1. A = the edition with the best text (`pdf-text`/`pdf-ocr`), B = whatever knows B's pages (a website, another scan, ...).
   B only needs the words around each page break.
2. `[output] kind = "single" edition = "A" marks = ["A", "B"]` with `[output.collate] refs = ["B"] marks_from = ["B"]`.
3. Pages of B that no source provides: `[[edition.mark_at]] edition = "B" label = 526 before = "first words of that page"`.
4. `textcollate build` and check: every page of B present (`textcollate extract` prints the count), the joins across
   page breaks (in-word breaks show as `Be|denken`), italics (`[[edition.italic]]`).

## 3. Side-by-side translation with the standard edition's page numbers

1. Left = the collated original (`left_collate` as above), right = the translation (usually a PDF: `pdf-ocr` with
   `images = "smask"` if it is an MRC scan, else `render`).
2. `[[output]] kind = "parallel" left right transfer = ["B"] marks = ["A", "T", "B"] concordance = "B"`.
3. Add 30-70 content `[[output.anchor]]` pairs (a distinctive phrase in each language) and run `textcollate check <id>`:
   they prove the translation covers the same ground *in the same order* and steer the paragraph alignment.
4. Read `build/reports/<id>.align.txt`: the block shapes (`1:1` mostly; `2:1` where one text splits a paragraph) and, for every
   carried page mark, the German and English context. `approx` marks are positioned inside a sentence by proportion.
5. Translator's footnotes: give the footnote lines' region (`notes = {min_y = ...}`) and one `[[edition.note_marker]]` per
   note; the marker positions have to be checked on the page image (OCR usually reads a superscript as a quote mark).

## Checklist that would have saved hours

* Look at pages before believing the text: blank `Hidden page` placeholders, cropped facing pages, watermarks.
* A source is *born digital* only if you can tell why (html text). A PDF text layer of a scan is OCR.
* Keep the untouched original. Never write the processed file over it.
* Verify programmatically (word diff against a second edition, anchors in order, the count of page marks) and look at the
  rendered PDF at least once per page type.
