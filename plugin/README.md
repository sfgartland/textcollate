# textcollate plugin

Three skills that drive the [`textcollate`](https://github.com/sfgartland/textcollate) CLI:

* `collate-editions` -- inventory and compare versions of a text, repair OCR from a better edition
* `page-marked-latex` -- clean LaTeX with the page breaks of a standard edition
* `parallel-translation` -- side-by-side translation with page mapping and preserved footnotes

## Install (from inside Claude Code, or a shell)

```
/plugin marketplace add sfgartland/textcollate
/plugin install textcollate@textcollate
```

(shell: `claude plugin marketplace add sfgartland/textcollate && claude plugin install textcollate@textcollate`)

The plugin ships a `bin/textcollate` launcher, so the skills just run `textcollate ...`. It uses an installed copy if there is one,
else `$TEXTCOLLATE_HOME` (a checkout), else it fetches the CLI from GitHub with `uvx` -- so the only prerequisite for the CLI itself is
[`uv`](https://docs.astral.sh/uv/). For scans you also need poppler and tesseract, for typesetting a TeX engine (`lualatex`);
`textcollate doctor` tells you what is missing.

Permanent CLI install (optional): `uv tool install git+https://github.com/sfgartland/textcollate`
