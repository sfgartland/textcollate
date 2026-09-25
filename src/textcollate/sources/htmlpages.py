"""One HTML file per page (e.g. a website that publishes a book page by page)."""
from __future__ import annotations

import html
import re

from .. import marks
from ..config import parse_pages
from ..model import PageData
from ..tools import ToolError
from . import page_labels


def to_text(fragment: str) -> str:
    fragment = re.sub(r"<br\s*/?>", marks.BR, fragment, flags=re.IGNORECASE)
    fragment = re.sub(r"<(?:i|em)\b[^>]*>", marks.EM_ON, fragment, flags=re.IGNORECASE)
    fragment = re.sub(r"</(?:i|em)>", marks.EM_OFF, fragment, flags=re.IGNORECASE)
    fragment = re.sub(r"<[^>]+>", " ", fragment)
    text = html.unescape(fragment).replace("\xa0", " ")
    text = re.sub(r"[ \t\r\n]+", " ", text)
    text = re.sub(rf"\s*({re.escape(marks.BR)})\s*", r"\1", text)
    return text.strip()


def load(part: dict, ed: dict, cfg) -> list[PageData]:
    nums = parse_pages(part.get("pages"))
    labels = page_labels(nums, part.get("labels") or ed.get("pages"))
    body_rx = re.compile(part.get("body", r"<body[^>]*>(.*?)</body>"), re.DOTALL | re.IGNORECASE)
    par_rx = re.compile(part.get("paragraph", r"<p[^>]*>(.*?)</p>"), re.DOTALL | re.IGNORECASE)
    drop = [re.compile(d) for d in part.get("drop", [r"^\d{1,4}$"])]
    out = []
    for n, label in zip(nums, labels):
        path = part["pattern"].format(page=n)
        try:
            raw = open(path, encoding="utf-8", errors="replace").read()
        except FileNotFoundError:
            if part.get("skip_missing", False):
                continue
            raise ToolError(f"missing page file {path}") from None
        m = body_rx.search(raw)
        body = m.group(1) if m else raw
        paras = [to_text(x) for x in par_rx.findall(body)]
        paras = [p for p in paras if p and not any(d.search(marks.strip(p)) for d in drop)]
        out.append(PageData(label=label, paragraphs=paras))
    return out
