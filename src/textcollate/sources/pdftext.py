"""PDF text layer with geometry (pdftotext -bbox-layout)."""
from __future__ import annotations

import html
import re

from ..config import parse_pages
from ..model import Line, PageData
from ..tools import run
from . import page_labels

LINE = re.compile(r'<line xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</line>', re.DOTALL)
WORD = re.compile(r">([^<]*)</word>")


def _mode(vals, step=4):
    from collections import Counter
    return Counter(round(v / step) * step for v in vals).most_common(1)[0][0]


def despace(words: list[tuple[str, float, float]], factor: float = 1.7) -> list[tuple[str, float, float]]:
    """letter-spaced text ("F r a g e n") arrives as single-letter words: join runs of >= 3 of them, splitting the run into words
    where the gap is clearly wider than the letter gap"""
    out, i = [], 0
    def single(w):
        return len(w[0].rstrip(".,;:!?)»«\"'")) == 1 and w[0][:1].isalpha()
    while i < len(words):
        j = i
        while j < len(words) and single(words[j]):
            j += 1
        if j - i >= 3:
            run = words[i:j]
            gaps = sorted(run[k + 1][1] - run[k][2] for k in range(len(run) - 1))
            med = gaps[len(gaps) // 2] if gaps else 0.0
            cur = [run[0]]
            for k in range(1, len(run)):
                if run[k][1] - run[k - 1][2] > max(factor * med, med + 1.5):
                    out.append(("".join(w[0] for w in cur), cur[0][1], cur[-1][2]))
                    cur = []
                cur.append(run[k])
            out.append(("".join(w[0] for w in cur), cur[0][1], cur[-1][2]))
            i = j
        else:
            out.append(words[i])
            i += 1
    return out


def _lines(chunk: str, join_letters: bool = False, drop_super: bool = False) -> list[Line]:
    out = []
    heights = sorted(float(y1) - float(y0) for y0, y1 in re.findall(r'<word xMin="[\d.]+" yMin="([\d.]+)" xMax="[\d.]+" yMax="([\d.]+)">', chunk)) if drop_super else []
    med = heights[len(heights) // 2] if heights else 0.0
    for m in LINE.finditer(chunk):
        boxes = re.findall(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">([^<]*)</word>', m.group(5))
        if drop_super:      # superscript numbers (editorial note references): smaller boxes than the running text
            boxes = [b for b in boxes if not (re.fullmatch(r"\d{1,3}[.,;:]?", b[4]) and float(b[3]) - float(b[1]) < 0.75 * med)]
        words = [(html.unescape(t), float(a), float(c)) for a, _, c, _, t in [(b[0], b[1], b[2], b[3], b[4]) for b in boxes]]
        if join_letters:
            words = despace(words)
        y0, y1 = float(m.group(2)), float(m.group(4))
        out.append(Line(" ".join(w[0] for w in words), float(m.group(1)), float(m.group(3)), y0, y1 - y0, words))
    return sorted(out, key=lambda l: (l.y, l.x0))


def _split_margin(lines: list[Line], cfg: dict) -> tuple[list[Line], list[tuple[float, str]]]:
    """numbers in the margin are the page numbers of another edition: whole lines consisting of one number outside the text
    block, and a number that starts or ends a text line but sits outside the block"""
    if not lines or not cfg:
        return lines, []
    pat = re.compile(cfg.get("regex", r"\d{1,3}"))
    text_lines = [l for l in lines if len(l.text.split()) > 3]
    if not text_lines:
        return lines, []
    left, right = _mode([l.x0 for l in text_lines]), _mode([l.x1 for l in text_lines])
    slack = float(cfg.get("slack", 6))
    margin, keep = [], []
    for l in lines:
        if len(l.text.split()) == 1 and pat.fullmatch(l.text) and (l.x1 < left - slack or l.x0 > right + slack):
            margin.append((l.y, l.text))
            continue
        if l.words and len(l.words) > 3:
            first = l.words[0]
            ws = list(l.words)
            if pat.fullmatch(first[0]) and first[2] < left - slack:
                margin.append((l.y, first[0]))
                ws = ws[1:]
            if ws and pat.fullmatch(ws[-1][0]) and ws[-1][1] > right + slack:
                margin.append((l.y, ws[-1][0]))
                ws = ws[:-1]
            if len(ws) != len(l.words):
                l = Line(" ".join(w[0] for w in ws), ws[0][1], ws[-1][2], l.y, l.h, ws)
        keep.append(l)
    return keep, margin


def load(part: dict, ed: dict, cfg) -> list[PageData]:
    nums = parse_pages(part.get("pages"))
    first, last = min(nums), max(nums)
    xml = run("pdftotext", "-bbox-layout", "-f", str(first), "-l", str(last), part["path"], "-")
    pages = re.split(r"<page ", xml)[1:]
    spreads = bool(part.get("spreads"))
    labels = page_labels(nums, part.get("labels") or ed.get("pages")) if not spreads else [str(x) for x in (part.get("labels") or ed.get("pages", {}).get("list", []))]
    mcfg = part.get("margin_marks") or {}
    out, k = [], 0
    for n, chunk in zip(range(first, last + 1), pages):
        if n not in nums:
            continue
        w = re.match(r'width="([\d.]+)"', chunk)
        width = float(w.group(1)) if w else 0.0
        lines = _lines(chunk, bool(part.get("despace")), bool(part.get("drop_superscripts")))
        halves = [lines]
        if spreads:                                            # a double-page spread: left and right page
            mid = width / 2
            halves = [[l for l in lines if (l.x0 + l.x1) / 2 < mid], [l for l in lines if (l.x0 + l.x1) / 2 >= mid]]
        for half in halves:
            label = labels[k] if k < len(labels) else str(n)
            k += 1
            if spreads and not label:                          # blank half of a spread
                continue
            body, margin = _split_margin(half, mcfg)
            out.append(PageData(label=label, lines=body, width=width, origin=(part["path"], n), margin=margin))
    return out
