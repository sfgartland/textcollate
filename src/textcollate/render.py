"""LaTeX output: clean single-edition documents and side-by-side (parallel) documents, with page marks of any editions."""
from __future__ import annotations

import re
import string
import subprocess
from pathlib import Path

from . import marks
from .bitext import Parallel
from .model import Edition
from .tools import ToolError

BABEL = {"de": "ngerman", "en": "english", "fr": "french", "it": "italian", "es": "spanish", "la": "latin", "nl": "dutch",
         "el": "greek", "grc": "greek", "pt": "portuguese", "ru": "russian"}
ESC = [("\\", "\\textbackslash{}"), ("&", "\\&"), ("%", "\\%"), ("$", "\\$"), ("#", "\\#"), ("_", "\\_"), ("{", "\\{"), ("}", "\\}"),
       ("~", "\\textasciitilde{}"), ("^", "\\^{}")]


def esc(t: str) -> str:
    for a, b in ESC:
        t = t.replace(a, b)
    return t.replace("\u2009", "\\,")


def cs_name(s: str) -> str:
    """letters-only control sequence name for an id or footnote key"""
    return "".join("Q" + string.ascii_uppercase[int(c)] if c.isdigit() else (c if c.isalpha() else {"*": "star"}.get(c, "x")) for c in s)


class Styles:
    """mark style per edition: colour, short label, inline/margin"""
    def __init__(self, cfg, edition_ids: list[str]):
        self.ids = edition_ids
        self.by_id = {}
        for i, eid in enumerate(edition_ids):
            ed = cfg.editions.get(eid)
            style = ed.get("mark_style", {}) if ed else {m["id"]: m for m in cfg.data.get("mark_system", [])}.get(eid, {})
            st = {"color": "808080", "label": "", "bold": False, "margin": "none", "inline": True, **style}
            st["macro"] = "tcm" + string.ascii_uppercase[i]
            self.by_id[eid] = st

    def preamble(self, margin_notes: bool) -> str:
        out = []
        for st in self.by_id.values():
            col = f"tccol{st['macro'][3:]}"
            out.append(f"\\definecolor{{{col}}}{{HTML}}{{{st['color'].lstrip('#')}}}")
            lab = esc(st["label"]) + "\\," if st["label"] else ""
            body = f"\\textsuperscript{{\\textbar\\,{lab}#1\\,\\textbar}}"
            if st["bold"]:
                body = f"\\textbf{{{body}}}"
            approx = f"\\textsuperscript{{\\textbar\\,{lab}#1\\,$\\approx$\\,\\textbar}}"
            if st["bold"]:
                approx = f"\\textbf{{{approx}}}"
            side = st["margin"]
            note = ""
            if margin_notes and side in ("left", "right"):
                rev = "\\reversemarginpar" if side == "left" else ""
                rag = "\\raggedleft" if side == "left" else ""
                lbl = st["label"]
                note = "{" + rev + "\\marginnote{\\footnotesize" + rag + "\\textcolor{" + col + "}{" + lbl + "\\,S.\\,#1}}[0pt]}"
            inline = "" if not st["inline"] else f"\\textcolor{{{col}}}{{{body}}}"
            inline_a = "" if not st["inline"] else f"\\textcolor{{{col}}}{{{approx}}}"
            # #1 label, #2 flags: a = approximate, w = inside a word (no space after)
            out.append(f"\\newcommand{{\\{st['macro']}}}[2]{{{note}\\if a#2{inline_a}\\else{inline}\\fi\\if w#2\\else\\,\\fi}}")
        return "\n".join(out)


def to_tex(par: str, styles: Styles, notes: dict[str, str], *, italic=True) -> tuple[str, bool]:
    quote = marks.QUOTE in par
    par = par.replace(marks.QUOTE, "")
    par = re.sub(rf"^((?:\x01M[^\x01]*\x01|\s)*){re.escape(marks.BR)}", r"\1", par)          # a line break cannot open a paragraph
    out, last, depth = [], 0, 0
    for m in marks.SENTINEL.finditer(par):
        out.append(esc(par[last:m.start()]))
        last = m.end()
        kind, args = marks.decode(m.group(0))
        if kind == "M":
            eid, label, flags = args[0], args[1], (args[2] if len(args) > 2 else "")
            if eid in styles.by_id:
                out.append(f"\\{styles.by_id[eid]['macro']}{{{esc(label)}}}{{{flags or 'n'}}}")
        elif kind == "N" and args[0] in notes:
            key = args[0]
            out.append("\\tcnote{" + cs_name(key) + "}{" + ("\\ast" if key == "*" else esc(key)) + "}")
        elif kind == "BR":
            out.append("\\\\")
        elif kind == "I+" and italic:
            out.append("\\emph{"); depth += 1
        elif kind == "I-" and italic and depth:
            out.append("}"); depth -= 1
    out.append(esc(par[last:]))
    out.append("}" * depth)
    tex = "".join(out)
    tex = re.sub(r"(\\tcm[A-Z]\{[^}]*\}\{[a-z]\})\s+", r"\1", tex)      # macros bring their own spacing
    return tex, quote


def note_defs(notes: dict[str, str]) -> str:
    lines = [f"\\expandafter\\def\\csname tcfn{cs_name(k)}\\endcsname{{{esc(v)}}}" for k, v in notes.items()]
    lines.append("\\newcommand{\\tcnote}[2]{\\begingroup\\def\\thefootnote{#2}\\footnote{\\csname tcfn#1\\endcsname}\\endgroup}")
    return "\n".join(lines)


def paper_opts(cfg) -> str:
    L = cfg.latex
    return f"{L['fontsize']},{L['paper']}"


def preamble(cfg, langs: list[str], styles: Styles, *, landscape=False, extra="", margin_notes=False) -> str:
    L = cfg.latex
    babel = ",".join(dict.fromkeys(BABEL[l] for l in langs if l in BABEL)) or "english"
    geometry = f"{L['paper']}" + (",landscape,margin=1.5cm,top=1.6cm,bottom=1.7cm" if landscape else ",left=3.4cm,right=4cm,top=3cm,bottom=3cm,marginparwidth=2.6cm")
    return f"""\\documentclass[{'9.5pt' if landscape else L['fontsize']},{L['paper']}{',landscape' if landscape else ''}]{{extarticle}}
\\usepackage{{fontspec}}
\\setmainfont{{{L['font']}}}
\\usepackage[{babel}]{{babel}}
\\usepackage{{microtype}}
\\usepackage{{xcolor}}
\\usepackage{{marginnote}}
\\usepackage[{geometry}]{{geometry}}
\\usepackage{{booktabs}}
\\usepackage[hidelinks]{{hyperref}}
\\setlength{{\\parindent}}{{1.3em}}
\\renewcommand*{{\\raggedleftmarginnote}}{{\\raggedright}}
{styles.preamble(margin_notes)}
{extra}
"""


def title_tex(title: str, styles: Styles, notes: dict[str, str]) -> str:
    """titles taken from an edition may carry footnote markers"""
    return to_tex(title, styles, notes)[0] if marks.SENTINEL.search(title) else esc(title)


def header(title: str, legend: str) -> str:
    parts = []
    if title:
        parts.append(f"{{\\Large\\scshape {title}}}\\par")
    if legend:
        parts.append(f"{{\\footnotesize {esc(legend)}}}\\par")
    return ("\\begin{center}" + "\\smallskip ".join(parts) + "\\end{center}\\vspace{0.4em}\n") if parts else ""


def compile_tex(tex: Path, engine: str = "lualatex", runs: int = 2) -> Path:
    for _ in range(runs):
        r = subprocess.run([engine, "-interaction=nonstopmode", "-halt-on-error", tex.name], cwd=tex.parent, capture_output=True, text=True)
        if r.returncode != 0:
            tail = "\n".join(l for l in r.stdout.splitlines() if l.startswith("!") or "Error" in l)[:600]
            raise ToolError(f"{engine} failed on {tex.name}:\n{tail}")
    for ext in (".aux", ".log", ".out", ".toc"):
        tex.with_suffix(ext).unlink(missing_ok=True)
    return tex.with_suffix(".pdf")


# ---------------------------------------------------------------------------------------------- single edition
def single(cfg, ed: Edition, show: list[str], out: dict) -> str:
    styles = Styles(cfg, show)
    notes = ed.notes
    title = out.get("title") or ed.title or ed.label
    body = []
    for p in ed.paragraphs:
        tex, quote = to_tex(p, styles, notes)
        body.append(f"\\begin{{quote}}\\small {tex}\\end{{quote}}" if quote else tex + "\\par")
    legend = ", ".join(f"{styles.by_id[i]['label'] or i}: {cfg.editions.get(i, {}).get('label', i)}" for i in show)
    colophon = out.get("colophon", f"Text: {ed.label}. Page marks: {legend}.")
    return (preamble(cfg, [ed.language], styles, margin_notes=True, extra=note_defs(notes)) +
            f"\\begin{{document}}\n\\thispagestyle{{empty}}\n{header(title_tex(title, styles, notes), '')}\n" +
            "\n\n".join(body) +
            f"\n\n\\vfill\n{{\\footnotesize\\noindent\\rule{{\\linewidth}}{{0.3pt}}\\\\ {esc(colophon)}}}\n\\end{{document}}\n")


# ---------------------------------------------------------------------------------------------- parallel
def concordance(par: Parallel, left: Edition, right: Edition, of: str) -> list[tuple[str, str, str]]:
    """for each page mark of edition `of` (any edition, or the left one itself): the page of left and right it falls on"""
    rows: dict[str, list] = {}
    for side, texts in (("l", [p for b in par.blocks for p in b.left]), ("r", [p for b in par.blocks for p in b.right])):
        cur = {left.id: None, right.id: None}
        own = left.id if side == "l" else right.id
        for t in texts:
            for m in marks.SENTINEL.finditer(t):
                kind, a = marks.decode(m.group(0))
                if kind != "M":
                    continue
                eid, label, flags = a[0], a[1], (a[2] if len(a) > 2 else "")
                if eid == own:
                    cur[own] = label
                if eid == of:
                    rows.setdefault(label, [None, None])[0 if side == "l" else 1] = (cur[own], "a" in flags)
    out = []
    for g, v in rows.items():
        lp = v[0][0] if v[0] and v[0][0] else (g if of == left.id else "")
        rp = f"{v[1][0]}{'≈' if v[1][1] else ''}" if v[1] and v[1][0] else ""
        out.append((g, lp or "", rp))
    return out


def parallel(cfg, par: Parallel, left: Edition, right: Edition, show: list[str], out: dict) -> str:
    styles = Styles(cfg, show)
    langs = [left.language, right.language]
    notes = {**left.notes, **right.notes}
    L = esc(out["left_title"]) if out.get("left_title") else title_tex(left.title or left.label, styles, notes)
    R = esc(out["right_title"]) if out.get("right_title") else title_tex(right.title or right.label, styles, notes)
    rows = []
    for b in par.blocks:
        l = "\n\n".join((lambda t: (f"\\begin{{quote}}\\small {t[0]}\\end{{quote}}" if t[1] else t[0] + "\\par"))(to_tex(p, styles, notes)) for p in b.left)
        r = "\n\n".join((lambda t: (f"\\begin{{quote}}\\small {t[0]}\\end{{quote}}" if t[1] else t[0] + "\\par"))(to_tex(p, styles, notes)) for p in b.right)
        rows.append(f"{l}\n\\switchcolumn\n{r}\n\\switchcolumn*\n")
    conc = concordance(par, left, right, out.get("concordance", show[-1] if show else ""))
    of_id = out.get("concordance", show[-1] if show else "")
    two_col = of_id == left.id
    table = "\n".join((f"  {esc(g)} & {esc(b)} \\\\" if two_col else f"  {esc(g)} & {esc(a)} & {esc(b)} \\\\") for g, a, b in conc)
    extra = "\\usepackage{paracol}\n\\setlength{\\columnsep}{1.2cm}\\setlength{\\columnseprule}{0.3pt}\\footnotelayout{c}\\raggedbottom\n" + \
            note_defs(notes)
    legend = out.get("legend", "")
    tail = ""
    if conc:
        ref_label = esc(cfg.editions.get(of_id, {}).get("label", "reference"))
        cols, head = ("rc", f"{ref_label} & {esc(right.label)}") if two_col else ("rcc", f"{ref_label} & {esc(left.label)} & {esc(right.label)}")
        tail = ("\\bigskip\\begin{center}\\footnotesize\\begin{tabular}{" + cols + "}\\toprule\n" + head + " \\\\ \\midrule\n" + table +
                "\n\\bottomrule\\end{tabular}\\\\[0.3em]\\emph{Where each page of the reference edition begins. $\\approx$ = position carried into the translation by sentence alignment.}\\end{center}\n")
    return (preamble(cfg, langs, styles, landscape=True, extra=extra, margin_notes=False) +
            f"\\begin{{document}}\n\\pagestyle{{empty}}\n{header(esc(out.get('title', '')), legend)}"
            f"\\begin{{paracol}}{{2}}\n\\selectlanguage{{{BABEL.get(left.language, 'english')}}}\n{{\\centering\\Large\\scshape {L}\\par}}\\vspace{{0.4em}}\n\\switchcolumn\n"
            f"\\selectlanguage{{{BABEL.get(right.language, 'english')}}}\n{{\\centering\\Large\\scshape {R}\\par}}\\vspace{{0.4em}}\n\\switchcolumn*\n\n" +
            "\n".join(rows) + "\n\\end{paracol}\n" + tail + "\\end{document}\n")
