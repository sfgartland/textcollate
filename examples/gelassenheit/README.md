# Example: Heidegger, *Gelassenheit* / *Memorial Address*

Reproduces the German text (Neske 1960) with the page breaks of GA 16, and the German-English parallel edition
(*Discourse on Thinking*, Anderson/Freund 1966).

```bash
./link_sources.sh                       # symlinks the source files (not in the repository: copyrighted scans)
uv run textcollate doctor -c . --lang deu eng
uv run textcollate build -c .           # -> build/out/de-clean.pdf, build/out/de-en.pdf
uv run textcollate check de-en -c .     # 71 content anchors, same order in both languages
```

What it shows, edition by edition (`textcollate.toml`):

| edition | source | why |
|---|---|---|
| `ga16` | beyng.com html for pp. 517-520, 523-525; OCR of the image-only scan for 521, 522, 527, 529 | the page breaks to cite |
| `arendt` | OCR of Arendt's copy of Neske 1959 (single pages + double-page spreads) | a second OCR of the same typesetting; fixes slips on pages the GA 16 scan hides |
| `neske60` | text layer of the Internet Archive scan | the text we typeset |
| `dot` | OCR of the 1-bit text masks of the English scan | the translation, with its five notes |

Pages 526 and 528 of the GA 16 scan are blank placeholders; their breaks are declared with `mark_at`.
Expected: 13 GA 16 marks in both columns (`build/reports/de-en.align.txt`), anchors 71/71 (German) and 71/71 (English).
