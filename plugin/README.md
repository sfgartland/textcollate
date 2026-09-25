# textcollate plugin

Three skills that drive the `textcollate` CLI (repository root):

* `collate-editions` -- inventory and compare versions of a text, repair OCR from a better edition
* `page-marked-latex` -- clean LaTeX with the page breaks of a standard edition
* `parallel-translation` -- side-by-side translation with page mapping and preserved footnotes

Install from the repository root:

```bash
claude plugin marketplace add ~/programing_linux/textcollate
claude plugin install textcollate@textcollate
uv tool install --editable ~/programing_linux/textcollate     # puts `textcollate` on PATH
```

If the CLI is not on PATH the skills fall back to `uv run --project ${TEXTCOLLATE_HOME:-~/programing_linux/textcollate} textcollate`.
