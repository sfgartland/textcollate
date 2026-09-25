# Configuration reference

One TOML file (default `./textcollate.toml`). Relative paths are relative to the file; `~` and `${VAR}` are expanded.

## `[project]`, `[latex]`

| key | meaning |
|---|---|
| `project.name`, `title`, `author` | free metadata |
| `project.build_dir` | default `build/` next to the config |
| `latex.engine` | `lualatex` (default) or `xelatex` |
| `latex.font`, `paper`, `fontsize` | `TeX Gyre Pagella`, `a4paper`, `10pt` |

## `[[edition]]`

`id`, `language` (`de`, `en`, `fr`, ...) are required; `label` is the human name. An edition has **one** `[edition.source]`
or several `[[edition.part]]` (pages from different files -- e.g. a website for most pages and an OCR of the scan for the rest;
parts are put in page order when all labels are numeric).

### Source types

| `type` | keys |
|---|---|
| `pdf-text` | `path`, `pages` (`"13-30"`, `"1,3,5-7"`, list): the PDF's own text layer *with geometry* (`pdftotext -bbox-layout`) |
| `pdf-ocr` | `path`, `pages`, `lang`, `psm` (4), `images` = `render` (`dpi`) / `native` (embedded image, optional `scale` %) / `smask` (1-bit text mask of MRC scans), `invert`, `split = 2` (double-page spreads), `tessdata_dir`, `engine = "command"` + `command` (see docs/ocr.md) |
| `html-pages` | `pattern` (with `{page}`), `pages`, `body` (regex, one group), `paragraph` (regex), `drop` (regexes of paragraphs to discard, default folio numbers), `skip_missing` |
| `text` | `path`, `page_break` (regex, default form feed), `paragraph_break` |

`pdf-text` extras for awkward scans: `spreads = true` (each PDF page is a double-page spread; give `labels` as a list with `""` for blank
halves), `despace = true` (letter-spaced words "F r a g e n" are re-joined by word gaps), `drop_superscripts = true` (superscript note
numbers are removed), `margin_marks = {edition = "va", regex = '\d{1,3}', sequence = true}` (numbers standing in the margin are the page
numbers of *another* edition and become page marks of it; `sequence` repairs OCR misreads such as 50 for 30; the mark style comes from a
`[[mark_system]] id = "va", label = "VA"` table).

Every source also takes `trust` (default 1.0 for html/text, 0.5 for OCR/text layers) and `labels`.

### `[edition.pages]` (or `labels` inside a part) -- the edition's own page labels

`{first = 11}` label of the first listed page, counting up · `{offset = -2}` label = source page + offset · `{list = [...]}`
explicit · nothing: the source page number.

### `[edition.layout]` -- paragraphs from geometry

| key | meaning |
|---|---|
| `paragraphs` | `indent` (first-line indent), `shortline` (short last line + capital next), `both` |
| `indent_frac` (0.035), `short_frac` (0.10), `centred_frac` (0.10) | thresholds as fractions of the text width |
| `quote_frac` (`[0.04, 0.10]`) | indentation range of block quotations (must span several lines) |
| `furniture` | regexes (full-line) for running heads etc.; digit-only lines at the page edge are dropped (`drop_folios`) |
| `title` | regexes for title lines (split off into `edition.title`) |
| `notes` | `{min_y = 2000}` or `{frac = 0.75}`, `height_ratio = 0.85`: small lines at the bottom are footnotes; `note_split` regex |
| `drop_tokens` | regexes of stray tokens to delete (OCR debris, e.g. `['^[A-Z]$']`) |
| `drop_paragraphs` | regexes of whole paragraphs to delete after reconstruction (their page marks move to the next paragraph) |
| `line_numbers` | `{step = 5, max = 45}`: critical editions number every fifth line in the margin; leading multiples left of the text block are dropped |
| `notes` variants | `{marker_lines = true}` (a small superscript marker line near the foot opens the notes), `{start_re = '^\d{1,2}\)\s', min_frac = 0.6}` (the first line in the lower part that looks like a note start opens them) |
| `note_scope`, `note_marker_re`, `note_marker_map` | `note_scope = "page"`: numbering restarts on every page (keys become `page:n`); `note_marker_re`: regex with one group for markers glued to words (`essence1`); `note_marker_map`: OCR misreads of the key (`{"!" = "1"}`) |
| `hyphens` | `{mode = "join"\|"lexicon", wordlist = [...], keep = ["warm-hearted"]}`; `join` always merges line-end hyphenation, `lexicon` only if the joined word is in the list |

### `[edition.clean]`, notes, emphasis, extra breaks

* `[edition.clean]` -- `replace = [["mina","mind"]]`, `regex = [[pattern, repl]]`, `drop = ["®"]`, `normalise = true`,
  `quotes = "de"|"en"|"none"`, `abbrev = ["d. h.", "z. B."]`, `dashes`, `debris`, `space_punct`.
* `[[edition.note_marker]]` -- `key`, `after = "text the marker follows"` (footnote texts come from the small bottom lines, or
  `[[edition.note]] key, text`). A missing anchor is an error, not a silent skip.
* `[[edition.italic]]` -- `context`, `phrase`: restores emphasis the OCR lost.
* `[[edition.mark_at]]` -- `edition`, `label`, `before`/`after`, `flags`: declares a page break of *another* edition by a text
  anchor, for breaks no source provides (e.g. pages the reference scan hides).
* `[edition.mark_style]` -- how this edition's page marks look: `label` ("GA 16"), `color` (hex), `bold`, `margin`
  (`left`/`right`/`none`), `inline` (true).
* `[edition.bib]` -- fields of a biblatex entry (`type`, `author`, `title`, ...) for `textcollate bib`.

## `[[output]]`

Common: `id`, `kind`, `title`, `marks` (whose page marks to show, in style order), `tex` (path), `colophon`.

**`kind = "single"`** -- `edition`; optional `[output.collate]`:
`refs = [ids]` (in priority order), `repair` (true), `paragraph_starts = [ids]`, `marks_from = [ids]`.

**`kind = "parallel"`** -- `left`, `right`, optional `[output.left_collate]` / `[output.right_collate]`, `transfer = [ids]`
(editions whose page marks are carried from the left text into the right by alignment), `concordance = id`,
`legend`, `left_title`, `right_title`, `auto_anchors` (true), `pins = [[left_index, right_index]]`, and any number of

```toml
[[output.anchor]]     # content anchors: regexes that must occur in both texts, in the same order
left = "Gegenwart des Meisters"
right = "master.s presence in the work"
```

`textcollate check <output>` verifies the anchors (exit code 2 when some are absent or out of order).

## Marks in the text

`\x01M|<edition>|<label>|<flags>\x01` -- flags `w` (inside a word) and `a` (approximate). See `src/textcollate/marks.py`.
