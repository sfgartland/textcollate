# Lessons from the first job (Heidegger, *Gelassenheit*)

These are the things that went wrong; the tool and the skills are built to make them hard to repeat.

* **A "complete" PDF was full of blank pages.** The GA 16 scan had ~180 `Hidden page` placeholders (a Google-Books-style preview).
  The address appeared complete in the table of contents. -> `extract` prints page counts; look at the pages; `mark_at` for
  breaks no source has.
* **Do not overwrite the source.** The untouched scan was replaced by a processed copy once and had to be fetched again
  (and the download host was blocked). -> keep originals; outputs go to `build/`.
* **Sharpening is not thresholding.** An unsharp mask followed by a hard threshold produced hollow letters. Compare candidates
  on a crop and *look*; smooth grey beat 1-bit at the same size.
* **Trust levels.** Born-digital text may repair an OCR text; the reverse is a bug. Words merely *present in the reference*
  are not "valid words": OCR garbage in a weak reference must not license a merge (`STRONG` vocabulary).
* **Paragraph structure comes from the page, not from the OCR.** Two short-line breaks I had thrown away as noise were real
  paragraph starts; the alignment with the translation (paragraph counts 1:1) exposed it. Cross-check paragraph counts
  between languages.
* **Page breaks fall inside words** (`Be-|denken`); a website may have dropped the fragment. Marks need a word-internal form.
* **Marks in a translation are approximate.** Word order differs; sentence alignment gets within a sentence. Say so (`≈`).
* **Footnote markers are read as quote marks** by OCR. Find them on the image, then declare them (`note_marker`).
* **Silent skips are bugs.** A missing anchor for a note marker did nothing for an hour. Now it raises.
* **Verify twice:** by word diff against an independent edition and by rendering the PDF.

## Second job (Husserl *Krisis*, Heidegger *Die Frage nach der Technik*, German | English)

* **Read the PDF's page structure before configuring.** One German scan was two-page spreads with a second edition's page numbers
  in the margin and OCR misreads in them (`50` for `30`); the fix (spreads, margin marks, sequence repair) is general.
* **Superscripts are not text.** Editorial note numbers inside lines (`ursprünglicher11`) and letterspacing (`F r a g e n`) come from
  word boxes, not from the text: use their geometry.
* **A text layer can be scrambled or unusable; re-OCR the embedded image** (`images = "native"`), then footnotes and page furniture
  behave. Compare the two before choosing.
* **Notes restart every page in some editions**: give them page-scoped keys.
* **The reference edition may start mid-section** (Hua VI p. 161 begins inside §46, Carr's p. 161 at §47): the first German
  paragraph has no English counterpart; the alignment handles it, the concordance shows it.
