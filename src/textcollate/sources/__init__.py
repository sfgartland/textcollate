"""Sources turn files into PageData. One [[edition]] may have a single `source` or several `part`s (pages from different files)."""
from __future__ import annotations

from ..config import Config
from ..model import PageData


def page_labels(numbers: list[int], spec: dict | None) -> list[str]:
    """label of each source page.  spec: {offset=-2} | {first=11} | {list=[...]} | {roman=true, first=..} | {} -> source page number"""
    spec = spec or {}
    if "list" in spec:
        return [str(x) for x in spec["list"]]
    if "first" in spec:
        return [str(int(spec["first"]) + i) for i in range(len(numbers))]
    off = int(spec.get("offset", 0))
    return [str(n + off) for n in numbers]


def load_pages(ed: dict, cfg: Config) -> list[PageData]:
    from . import htmlpages, ocr, pdftext, plaintext
    loaders = {"pdf-text": pdftext.load, "pdf-ocr": ocr.load, "html-pages": htmlpages.load, "text": plaintext.load}
    parts = ed.get("part") or [ed["source"] if "source" in ed else {}]
    pages: list[PageData] = []
    for part in parts:
        kind = part.get("type")
        if kind not in loaders:
            raise ValueError(f"edition {ed['id']}: unknown source type {kind!r} (choose from {', '.join(loaders)})")
        got = loaders[kind](part, ed, cfg)
        for p in got:
            p.trust = float(part.get("trust", 1.0 if kind in ("html-pages", "text") else 0.5))
        pages += got
    # an edition assembled from several sources is put in page order (numeric labels only)
    if ed.get("sort_pages", True) and len(parts) > 1 and all(p.label.isdigit() for p in pages):
        pages.sort(key=lambda p: int(p.label))
    return pages
