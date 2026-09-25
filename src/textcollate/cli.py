"""textcollate command line."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__, bib, bitext, collate, editions, qa, render, tools
from .config import ConfigError, load
from .model import Edition

TEMPLATE = '''# textcollate project
[project]
name = "my-text"
title = "My text"
author = "Author"

[latex]
font = "TeX Gyre Pagella"

# --- editions: every version of the text you have -----------------------------------------------------
[[edition]]
id = "clean"                      # e.g. a born-digital transcription (html pages, plain text ...)
label = "Website"
language = "de"
[edition.source]
type = "html-pages"               # pdf-text | pdf-ocr | html-pages | text
pattern = "html/page.{page}.html"
pages = "1-10"
[edition.mark_style]
label = "W"
color = "8B1E1E"

[[edition]]
id = "scan"
label = "Scan 1960"
language = "de"
[edition.source]
type = "pdf-text"                 # or pdf-ocr with lang = "deu"
path = "scan.pdf"
pages = "13-30"
[edition.pages]
first = 11                        # printed page label of the first page listed (or offset = -2)
[edition.layout]
paragraphs = "shortline"          # indent | shortline | both
[edition.mark_style]
label = "S"
color = "808080"
margin = "right"

# --- outputs ---------------------------------------------------------------------------------------------
[[output]]
id = "clean-latex"
kind = "single"                   # single | parallel
edition = "scan"
marks = ["scan", "clean"]         # whose page marks to show
[output.collate]
refs = ["clean"]                  # repair OCR slips against these, take paragraph starts and page marks from them
paragraph_starts = ["clean"]
marks_from = ["clean"]
'''


def _cfg(args):
    return load(args.config)


def cmd_doctor(args) -> int:
    langs = list(args.lang or [])
    if not langs:
        try:                                              # OCR languages the project needs, if there is a project here
            langs = sorted({p.get("lang") for e in _cfg(args).editions.values() for p in (e.get("part") or [e.get("source", {})]) if p.get("lang")})
        except ConfigError:
            pass
    bad = 0
    for name, ok, why in tools.doctor(langs or ["eng"]):
        print(f"{'ok ' if ok else 'MISSING'}  {name:22s} {why}")
        bad += (not ok and "optional" not in why)
    return 1 if bad else 0


def cmd_fetch(args) -> int:
    d = tools.fetch_tessdata(args.langs, args.dest)
    print(f"tessdata in {d}; set TESSDATA_PREFIX={d} or `tessdata_dir` in a source")
    return 0


def cmd_init(args) -> int:
    d = Path(args.dir)
    d.mkdir(parents=True, exist_ok=True)
    f = d / "textcollate.toml"
    if f.exists() and not args.force:
        print(f"{f} exists (use --force)")
        return 1
    f.write_text(TEMPLATE, encoding="utf-8")
    print(f"wrote {f}")
    return 0


def cmd_extract(args) -> int:
    cfg = _cfg(args)
    for eid in args.editions or list(cfg.editions):
        e = editions.build(cfg, eid)
        cen = qa.mark_census(e)
        print(f"{eid}: {len(e.paragraphs)} paragraphs, notes {sorted(e.notes)}, own marks {len(cen.get(eid, []))} "
              f"({cen.get(eid, ['-'])[0]}..{cen.get(eid, ['-'])[-1]})")
    return 0


def cmd_compare(args) -> int:
    cfg = _cfg(args)
    a, b = editions.get(cfg, args.a), editions.get(cfg, args.b)
    md, stats = collate.compare(a, b)
    out = Path(args.out) if args.out else cfg.build_dir / "reports" / f"compare_{args.a}_{args.b}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    print(json.dumps(stats), "->", out)
    return 0


def _collated(cfg, ed_id: str, spec: dict | None, tag: str) -> Edition:
    ed = editions.get(cfg, ed_id)
    if not spec:
        return ed
    refs = [editions.get(cfg, r) for r in spec.get("refs", [])]
    ed2, rep = collate.collate(ed, refs, repair=spec.get("repair", True), paragraph_starts=spec.get("paragraph_starts"),
                               marks_from=spec.get("marks_from"))
    rp = cfg.build_dir / "reports" / f"{tag}.collate.txt"
    rp.parent.mkdir(parents=True, exist_ok=True)
    rp.write_text(rep.text(), encoding="utf-8")
    ed2.save(cfg.build_dir / "editions" / f"{tag}.json")
    print(f"  collated {ed_id}: {len(rep.log)} corrections, {len(rep.starts_added)} paragraph starts, {len(rep.marks_moved)} marks ({rp})")
    return ed2


def build_output(cfg, out: dict, pdf: bool) -> Path:
    oid, kind = out["id"], out.get("kind", "single")
    outdir = cfg.build_dir / "out"
    outdir.mkdir(parents=True, exist_ok=True)
    tex_path = Path(out.get("tex", outdir / f"{oid}.tex"))
    if kind == "single":
        ed = _collated(cfg, out["edition"], out.get("collate"), f"{oid}")
        show = out.get("marks", [ed.id])
        tex = render.single(cfg, ed, show, out)
    elif kind == "parallel":
        left = _collated(cfg, out["left"], out.get("left_collate"), f"{oid}.left")
        right = _collated(cfg, out["right"], out.get("right_collate"), f"{oid}.right")
        par = bitext.align(left, right, anchors=[(a["left"], a["right"]) for a in out.get("anchor", [])],
                           auto_anchors=out.get("auto_anchors", True), pins=[tuple(p) for p in out.get("pins", [])],
                           marks_from=out.get("transfer", []))
        (cfg.build_dir / "reports").mkdir(parents=True, exist_ok=True)
        blocks = ", ".join(f"{len(b.left)}:{len(b.right)}" for b in par.blocks)
        (cfg.build_dir / "reports" / f"{oid}.align.txt").write_text(f"blocks (left:right paragraphs): {blocks}\n\n" + "\n".join(par.report) + "\n", encoding="utf-8")
        show = out.get("marks", [left.id, right.id, *out.get("transfer", [])])
        tex = render.parallel(cfg, par, left, right, show, out)
        print(f"  aligned {len(par.blocks)} blocks, {len(par.report)} marks carried over")
        if out.get("anchor"):
            rep = qa.anchor_order(left, right, out["anchor"])
            print(f"  anchor check: {rep['left_in_order']}/{rep['anchors']} in order on the left, {rep['right_in_order']}/{rep['anchors']} on the right")
    else:
        raise ConfigError(f"output {oid}: unknown kind {kind!r}")
    tex_path.parent.mkdir(parents=True, exist_ok=True)
    tex_path.write_text(tex, encoding="utf-8")
    if pdf:
        return render.compile_tex(tex_path, cfg.latex["engine"])
    return tex_path


def cmd_build(args) -> int:
    cfg = _cfg(args)
    if args.refresh:
        for f in (cfg.build_dir / "editions").glob("*.json"):
            f.unlink()
    outs = [cfg.output(o) for o in args.outputs] if args.outputs else cfg.outputs
    if not outs:
        print("no [[output]] in the config")
        return 1
    for o in outs:
        print(f"{o['id']} ({o.get('kind', 'single')})")
        print("  ->", build_output(cfg, o, not args.no_pdf))
    return 0


def cmd_bib(args) -> int:
    print(bib.entries(_cfg(args)))
    return 0


def cmd_check(args) -> int:
    cfg = _cfg(args)
    o = cfg.output(args.output)
    if o.get("kind") != "parallel":
        print("check applies to parallel outputs")
        return 1
    left, right = editions.get(cfg, o["left"]), editions.get(cfg, o["right"])
    left = _collated(cfg, o["left"], o.get("left_collate"), f"{o['id']}.left")
    rep = qa.anchor_order(left, right, o.get("anchor", []))
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    return 0 if rep["anchors"] == rep["left_in_order"] == rep["right_in_order"] else 2


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="textcollate", description=__doc__)
    ap.add_argument("--version", action="version", version=__version__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def with_cfg(p):
        p.add_argument("-c", "--config", default="textcollate.toml", help="project file or directory (default: ./textcollate.toml)")
        return p

    p = with_cfg(sub.add_parser("doctor", help="check external tools and OCR language data")); p.add_argument("--lang", nargs="*"); p.set_defaults(fn=cmd_doctor)
    p = sub.add_parser("fetch-tessdata", help="download tesseract language models to ~/.local/share/tessdata (no sudo)"); p.add_argument("langs", nargs="+"); p.add_argument("--dest"); p.set_defaults(fn=cmd_fetch)
    p = sub.add_parser("init", help="write a starter textcollate.toml"); p.add_argument("dir", nargs="?", default="."); p.add_argument("--force", action="store_true"); p.set_defaults(fn=cmd_init)
    p = with_cfg(sub.add_parser("extract", help="build editions (paragraphs, notes, own page marks) into build/editions")); p.add_argument("editions", nargs="*"); p.set_defaults(fn=cmd_extract)
    p = with_cfg(sub.add_parser("compare", help="word-level comparison of two editions")); p.add_argument("a"); p.add_argument("b"); p.add_argument("--out"); p.set_defaults(fn=cmd_compare)
    p = with_cfg(sub.add_parser("build", help="build [[output]]s (LaTeX + PDF)")); p.add_argument("outputs", nargs="*"); p.add_argument("--no-pdf", action="store_true"); p.add_argument("--refresh", action="store_true", help="rebuild all editions from the sources"); p.set_defaults(fn=cmd_build)
    p = with_cfg(sub.add_parser("bib", help="print biblatex entries for editions and outputs")); p.set_defaults(fn=cmd_bib)
    p = with_cfg(sub.add_parser("check", help="anchor coverage check of a parallel output")); p.add_argument("output"); p.set_defaults(fn=cmd_check)
    args = ap.parse_args(argv)
    try:
        return args.fn(args)
    except (ConfigError, tools.ToolError, KeyError) as e:
        print(f"textcollate: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
