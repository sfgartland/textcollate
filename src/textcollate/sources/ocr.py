"""OCR of scanned PDFs with tesseract, keeping line geometry (TSV output).

part settings:
  images = "render"   pdftoppm at `dpi` (default 300)
         = "native"   the embedded page image (pdfimages), optionally upscaled by `scale` percent (needs ImageMagick)
         = "smask"    the 1-bit text mask of MRC-compressed scans (very clean input for OCR)
  lang, psm, tessdata_dir, invert (bool)
  split = 2           each image is a double-page spread: OCR both halves as separate pages (labels: 2 per source page)
  engine = "tesseract" (default: line geometry, no italics)
         = "command"   any OCR that prints Markdown for one page image, e.g.
                       command = "my-ocr --format markdown {image}"
                       Emphasis (*italic*, _italic_) becomes emphasis marks in the edition; paragraphs come from blank lines.
                       Nothing about the tool is assumed: a vision-language OCR, a hosted OCR API wrapper, a script that asks
                       a model to transcribe the page ...
"""
from __future__ import annotations

import csv
import hashlib
import os
import re
import shlex
import statistics
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .. import marks
from ..config import parse_pages
from ..model import Line, PageData
from ..tools import ToolError, have, run, tesseract_env
from . import page_labels


def page_image(pdf: str, page: int, part: dict, tmp: Path) -> Path:
    mode = part.get("images", "render")
    base = tmp / f"p{page}"
    if mode == "render":
        run("pdftoppm", "-r", str(part.get("dpi", 300)), "-gray", "-png", "-f", str(page), "-l", str(page), pdf, str(base))
        return next(tmp.glob(f"p{page}-*.png"))
    listing = run("pdfimages", "-list", "-f", str(page), "-l", str(page), pdf).splitlines()[2:]
    kinds = [row.split()[2] for row in listing]
    run("pdfimages", "-png", "-f", str(page), "-l", str(page), pdf, str(base))
    files = sorted(tmp.glob(f"p{page}-*.png"))
    if mode == "smask":
        idx = [i for i, k in enumerate(kinds) if k == "smask"]
        if not idx:
            raise ToolError(f"page {page}: no soft mask image in {pdf}")
        img = files[idx[0]]
    else:
        idx = [i for i, k in enumerate(kinds) if k == "image"]
        if not files:
            raise ToolError(f"page {page}: no embedded image; use images = 'render'")
        img = files[idx[0]] if idx and idx[0] < len(files) else files[0]
    if part.get("scale") or part.get("invert"):
        if not have("magick"):
            raise ToolError("`scale`/`invert` need ImageMagick (magick)")
        out = tmp / f"p{page}_x.png"
        args = ["magick", str(img), "-colorspace", "Gray"]
        if part.get("invert"):
            args.append("-negate")
        if part.get("scale"):
            args += ["-filter", "Lanczos", "-resize", f"{int(part['scale'])}%"]
        run(*args, str(out))
        return out
    return img


def tsv_lines(tsv: str) -> list[Line]:
    rows = list(csv.reader(tsv.splitlines(), delimiter="\t", quoting=csv.QUOTE_NONE))[1:]
    lines: dict[tuple, dict] = {}
    for r in rows:
        if len(r) < 12 or r[0] != "5" or not r[11].strip():
            continue
        word = r[11].strip().strip("|¦")                     # gutter shadows are read as | characters
        if not word:
            continue
        d = lines.setdefault(tuple(r[2:5]), {"x0": int(r[6]), "y": int(r[7]), "x1": 0, "h": [], "w": [], "b": []})
        d["x0"] = min(d["x0"], int(r[6]))
        d["x1"] = max(d["x1"], int(r[6]) + int(r[8]))
        d["h"].append(int(r[9]))
        d["w"].append(word)
        d["b"].append((word, float(r[6]), float(int(r[6]) + int(r[8]))))
    out = [Line(" ".join(d["w"]), d["x0"], d["x1"], d["y"], statistics.median(d["h"]), d["b"]) for d in lines.values()]
    return sorted(out, key=lambda l: l.y)


def ocr_page(pdf: str, page: int, part: dict, cache: Path) -> list[str]:
    """-> one TSV per image (two for a spread)"""
    key = hashlib.sha1(f"{pdf}|{os.path.getmtime(pdf)}|{page}|{sorted(part.items(), key=str)}".encode()).hexdigest()[:16]
    n = int(part.get("split", 1))
    cached = [cache / f"{key}_{k}.tsv" for k in range(n)]
    if all(c.exists() for c in cached):
        return [c.read_text(encoding="utf-8") for c in cached]
    out = []
    with tempfile.TemporaryDirectory() as t:
        img = page_image(pdf, page, part, Path(t))
        imgs = [img]
        if n == 2:
            if not have("magick"):
                raise ToolError("`split = 2` needs ImageMagick (magick)")
            run("magick", str(img), "-crop", "50%x100%", "+repage", str(Path(t) / "half_%d.png"))
            imgs = [Path(t) / "half_0.png", Path(t) / "half_1.png"]
        for im in imgs:
            out.append(run("tesseract", str(im), "-", "-l", part.get("lang", "eng"), "--psm", str(part.get("psm", 4)), "tsv",
                           env=tesseract_env(part.get("tessdata_dir"))))
    cache.mkdir(parents=True, exist_ok=True)
    for c, tsv in zip(cached, out):
        c.write_text(tsv, encoding="utf-8")
    return out


EMPH = re.compile(r"(?<![*\w])\*(?!\*)([^*\n]+?)(?<!\*)\*(?![*\w])|(?<![_\w])_(?!_)([^_\n]+?)(?<!_)_(?![_\w])")


def markdown_to_paragraphs(md: str) -> list[str]:
    """Markdown page text -> paragraphs; *italic* / _italic_ -> emphasis sentinels, **bold** and headings are kept as plain text"""
    paras = []
    for block in re.split(r"\n\s*\n", md.strip()):
        text = re.sub(r"\s*\n\s*", " ", block).strip()
        text = re.sub(r"^#{1,6}\s+", "", text)
        text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
        text = EMPH.sub(lambda m: marks.EM_ON + (m.group(1) or m.group(2)) + marks.EM_OFF, text)
        if text:
            paras.append(text)
    return paras


def command_page(pdf: str, page: int, part: dict, cache: Path) -> str:
    key = hashlib.sha1(f"{pdf}|{page}|{part['command']}|{sorted(part.items(), key=str)}".encode()).hexdigest()[:16]
    cached = cache / f"{key}.md"
    if cached.exists():
        return cached.read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as t:
        img = page_image(pdf, page, part, Path(t))
        args = [a.replace("{image}", str(img)) for a in shlex.split(part["command"])]
        md = run(*args)
    cache.mkdir(parents=True, exist_ok=True)
    cached.write_text(md, encoding="utf-8")
    return md


def load(part: dict, ed: dict, cfg) -> list[PageData]:
    if part.get("engine", "tesseract") == "command":
        nums = parse_pages(part.get("pages"))
        labels = page_labels(nums, part.get("labels") or ed.get("pages"))
        cache = cfg.build_dir / "cache" / "ocr-cmd"
        with ThreadPoolExecutor(max_workers=int(part.get("jobs", 2))) as ex:
            mds = list(ex.map(lambda n: command_page(part["path"], n, part, cache), nums))
        return [PageData(label=lab, paragraphs=markdown_to_paragraphs(md), origin=(part["path"], n)) for lab, md, n in zip(labels, mds, nums)]
    nums = parse_pages(part.get("pages"))
    per = int(part.get("split", 1))
    labels = page_labels(nums if per == 1 else list(range(len(nums) * per)), part.get("labels") or ed.get("pages"))
    cache = cfg.build_dir / "cache" / "ocr"
    with ThreadPoolExecutor(max_workers=int(part.get("jobs", max(1, (os.cpu_count() or 2) - 1)))) as ex:
        tsvs = [t for group in ex.map(lambda n: ocr_page(part["path"], n, part, cache), nums) for t in group]
    origins = [(part["path"], n) for n in nums for _ in range(per)]
    return [PageData(label=lab, lines=tsv_lines(t), origin=o) for lab, t, o in zip(labels, tsvs, origins)]
