# OCR: engines, scans and italics

## What tesseract gives, and does not

tesseract (LSTM) returns words with boxes and confidence, but **no italic/bold information**, and its layout analysis
ignores footnotes and columns unless you tell it (`psm`). textcollate uses the boxes for paragraph and footnote logic.

Things that improved results a lot in practice:

* **Feed it a clean image.** For MRC-compressed scans (background JPEG 2000 + a 1-bit mask) `images = "smask"` OCRs the mask:
  crisper than any render. For small scans (575 px wide) upscale first (`images = "native"`, `scale = 300`).
* **Language data.** `textcollate fetch-tessdata deu` (tessdata_best). German with `eng` data gives "gewöhnlichen" -> "gewähnlichen".
* **Double-page spreads.** `split = 2`.
* **A second OCR of the same edition** as a reference (`refs = [...]`): independent errors cancel.

## Italics and other formatting

Options, roughly from cheap to heavy:

1. **Declare them** -- `[[edition.italic]] context/phrase`. Fine for a dozen emphases; that is how the example does it.
2. **Markdown-producing OCR** via `engine = "command"`: any tool that prints Markdown for one page image can drive an edition;
   `*italic*` / `_italic_` become emphasis, blank lines become paragraphs. Candidates (untested here, chosen by what they are
   built for): Mistral OCR (hosted, Markdown with italics and footnotes), olmOCR / Qwen-VL / other vision-language models
   (local GPU), Marker or Docling (layout-aware PDF -> Markdown pipelines), a script that shows the page image to a
   multimodal model and asks for a transcription with `*italics*`. Vision-language OCR is the best at formatting and at
   reading order, and the worst at *faithfulness*: it "corrects" and occasionally invents. Always collate its output against
   a second edition; the report shows what it changed.
3. **Kraken/eScriptorium** for old or unusual typefaces you can train on; still no italics unless you train them as a class.
4. **Word-level slant detection** on tesseract's word boxes (italic words are sheared ~12-15 degrees) is a cheap, offline way
   to *find* italic words; not implemented yet -- the hook would be a post-pass over `PageData` lines.

`engine = "command"`:

```toml
[edition.source]
type = "pdf-ocr"; path = "book.pdf"; pages = "12-40"; images = "render"; dpi = 300
engine = "command"
command = "my-ocr --markdown {image}"       # prints the page as Markdown on stdout
```

Results are cached under `build/cache/ocr-cmd/` (keyed by command and page), so a paid OCR runs once.
