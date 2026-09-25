"""Data model shared by all stages."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Line:
    text: str
    x0: float = 0.0
    x1: float = 0.0
    y: float = 0.0
    h: float = 0.0
    words: list[tuple[str, float, float]] | None = None    # (word, x0, x1) when the source has word boxes


@dataclass
class PageData:
    """One page as delivered by a source, before paragraph reconstruction."""
    label: str                                   # this edition's own page label ("517", "xii", ...)
    lines: list[Line] = field(default_factory=list)
    paragraphs: list[str] | None = None          # sources that already know their paragraphs (html, text)
    width: float = 0.0
    trust: float = 0.5                           # 1.0 born-digital text, ~0.5 OCR: decides who wins in a repair
    origin: tuple[str, int] | None = None        # (file, source page) for rendering the page image in a review
    margin: list[tuple[float, str]] = field(default_factory=list)   # (y, text): page numbers of another edition in the margin


@dataclass
class Edition:
    id: str
    label: str
    language: str
    paragraphs: list[str] = field(default_factory=list)      # marked strings, see marks.py
    notes: dict[str, str] = field(default_factory=dict)      # footnote key -> text
    title: str = ""
    trust: dict[int, float] = field(default_factory=dict)    # paragraph index -> trust
    meta: dict = field(default_factory=dict)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=1), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> Edition:
        d = json.loads(path.read_text(encoding="utf-8"))
        d["trust"] = {int(k): v for k, v in d.get("trust", {}).items()}
        return cls(**d)
