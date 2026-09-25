"""Plain text with page separators (form feed by default) and blank-line paragraphs."""
from __future__ import annotations

import re

from ..model import PageData
from . import page_labels


def load(part: dict, ed: dict, cfg) -> list[PageData]:
    raw = open(part["path"], encoding=part.get("encoding", "utf-8")).read()
    chunks = re.split(part.get("page_break", r"\f"), raw)
    labels = page_labels(list(range(1, len(chunks) + 1)), part.get("labels") or ed.get("pages"))
    out = []
    for chunk, label in zip(chunks, labels):
        paras = [re.sub(r"\s*\n\s*", " ", p).strip() for p in re.split(part.get("paragraph_break", r"\n\s*\n"), chunk)]
        out.append(PageData(label=label, paragraphs=[p for p in paras if p]))
    return out
