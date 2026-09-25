"""External tools: discovery, invocation, tessdata download."""
from __future__ import annotations

import os
import shutil
import subprocess
import urllib.request
from pathlib import Path

TESSDATA_URL = "https://github.com/tesseract-ocr/tessdata_best/raw/main/{lang}.traineddata"


class ToolError(RuntimeError):
    pass


def have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def run(*args: str, env: dict | None = None, cwd: str | Path | None = None) -> str:
    try:
        r = subprocess.run(list(args), capture_output=True, text=True, env=env, cwd=cwd)
    except FileNotFoundError:
        raise ToolError(f"{args[0]} not found (run `textcollate doctor`)") from None
    if r.returncode != 0:
        raise ToolError(f"{' '.join(args[:3])}… failed: {r.stderr.strip()[:400]}")
    return r.stdout


def tessdata_dir(configured: str | None = None) -> str | None:
    for cand in (configured, os.environ.get("TESSDATA_PREFIX"), os.path.expanduser("~/.local/share/tessdata")):
        if cand and Path(cand, "eng.traineddata").exists() or (cand and any(Path(cand).glob("*.traineddata"))):
            return cand
    return None


def tesseract_env(configured: str | None = None) -> dict:
    env = dict(os.environ)
    d = tessdata_dir(configured)
    if d:
        env["TESSDATA_PREFIX"] = d
    return env


def tesseract_langs(configured: str | None = None) -> list[str]:
    try:
        out = run("tesseract", "--list-langs", env=tesseract_env(configured))
    except ToolError:
        return []
    return [l.strip() for l in out.splitlines()[1:] if l.strip()]


def fetch_tessdata(langs: list[str], dest: str | None = None) -> Path:
    """Download tessdata_best models into a user directory (no sudo) and copy tesseract's config files next to them."""
    dest_p = Path(dest or "~/.local/share/tessdata").expanduser()
    dest_p.mkdir(parents=True, exist_ok=True)
    for lang in langs:
        target = dest_p / f"{lang}.traineddata"
        if not target.exists():
            urllib.request.urlretrieve(TESSDATA_URL.format(lang=lang), target)
    # tesseract needs its configs/ and tessconfigs/ (hocr, tsv, ...) in the same directory
    for system in ("/usr/share/tesseract/tessdata", "/usr/share/tessdata", "/usr/share/tesseract-ocr/5/tessdata", "/usr/share/tesseract-ocr/4.00/tessdata"):
        for sub in ("configs", "tessconfigs", "eng.traineddata", "osd.traineddata"):
            src = Path(system, sub)
            if src.exists() and not (dest_p / sub).exists():
                (shutil.copytree if src.is_dir() else shutil.copy)(src, dest_p / sub)
    return dest_p


def doctor(cfg_langs: list[str] | None = None) -> list[tuple[str, bool, str]]:
    rows = []
    for cmd, why in (("pdftotext", "text layer + layout of PDFs (poppler)"), ("pdfimages", "page images of scans (poppler)"),
                     ("pdftoppm", "rendering pages (poppler)"), ("tesseract", "OCR"), ("qpdf", "extracting page ranges"),
                     ("lualatex", "typesetting (xelatex also works)"), ("magick", "optional: image upscaling for OCR")):
        rows.append((cmd, have(cmd), why))
    langs = tesseract_langs()
    for l in cfg_langs or ["eng"]:
        rows.append((f"tesseract lang {l}", l in langs, "textcollate fetch-tessdata " + l if l not in langs else "ok"))
    return rows
