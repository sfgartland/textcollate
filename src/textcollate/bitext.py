"""Alignment of a text with its translation (or any second-language edition), and transfer of page marks across languages.

  1. paragraph blocks: monotone DP; evidence = anchors (user-given regex pairs, plus automatic ones: numbers and proper names
     that occur in both texts) and a length prior.  Steps 1:1, 1:2, 2:1, 2:2, 1:3, 3:1, 1:0, 0:1.
  2. sentence groups inside each block: Gale-Church style DP on sentence lengths.
  3. marks: a page mark of the source-side edition is mapped through its sentence group to a position in the translation.
     'exact' when it stands at the start of a sentence group, otherwise proportional inside the aligned sentence(s) and flagged
     approximate ('a').
"""
from __future__ import annotations

import collections
import math
import re
from dataclasses import dataclass, field

from . import marks
from .model import Edition

ABBREV = {"ed.", "d.", "h.", "z.", "B.", "Dr.", "Mr.", "Mrs.", "St.", "vs.", "etc.", "i.", "e.", "g.", "Nr.", "Bd.", "S.", "pp.", "p.", "cf.", "Tr."}
SPLIT = re.compile(r"[.?!]+[”«\")\]]*\s+(?=[“»(\"\[]?[A-ZÄÖÜ])")


@dataclass
class Block:
    left: list[str]
    right: list[str]


@dataclass
class Parallel:
    left_id: str
    right_id: str
    blocks: list[Block]
    report: list[str] = field(default_factory=list)
    marks_info: list[dict] = field(default_factory=list)      # one per carried mark: edition, label, exact, left/right context, block
    shapes: list[tuple[int, int, int, int]] = field(default_factory=list)    # (left start, n left, right start, n right)


def plain(p: str) -> str:
    return marks.strip(p).strip()


def sentences(text: str, abbrev: set[str] = ABBREV) -> list[tuple[int, int]]:
    out, start = [], 0
    for m in SPLIT.finditer(text):
        word = re.search(r"(\S+)$", text[start:m.start() + 1])
        if word and (word.group(1) in abbrev or re.fullmatch(r"[A-Z]\.", word.group(1)) or text[max(0, m.start() - 1):m.start() + 1].endswith(" h.")):
            continue
        end = m.start() + len(re.match(r"[.?!]+[”«\")\]]*", text[m.start():]).group(0))
        out.append((start, end))
        start = m.end()
    out.append((start, len(text)))
    return [(s, e) for s, e in out if e > s]


def _anchor_weights(L: list[str], R: list[str], anchors: list[tuple[str, str]], auto: bool, pins: list[tuple[int, int]]):
    W = [[0.0] * len(R) for _ in L]
    for lrx, rrx in anchors:
        li = [i for i, p in enumerate(L) if re.search(lrx, p, re.DOTALL | re.IGNORECASE)]
        ri = [j for j, p in enumerate(R) if re.search(rrx, p, re.DOTALL | re.IGNORECASE)]
        for i in li:
            for j in ri:
                W[i][j] += 1.0 / (len(li) * len(ri))
    if auto:
        def toks(paras):
            occ = collections.defaultdict(set)
            for i, p in enumerate(paras):
                for w in re.findall(r"\b(?:\d{2,4}|[A-ZÄÖÜ][a-zäöüßéè]{3,})\b", p):
                    occ[w].add(i)
            return occ
        lo, ro = toks(L), toks(R)
        for w in set(lo) & set(ro):
            li, ri = lo[w], ro[w]
            if len(li) <= 3 and len(ri) <= 3:
                for i in li:
                    for j in ri:
                        W[i][j] += 0.7 / (len(li) * len(ri))
    for i, j in pins:
        W[i][j] += 5.0
    return W


def align_paragraphs(L: list[str], R: list[str], W) -> list[tuple[int, int, int, int]]:
    ratio = sum(map(len, R)) / max(1, sum(map(len, L)))
    steps = [(1, 1, 0.0), (1, 2, 0.5), (2, 1, 0.5), (2, 2, 0.8), (1, 3, 1.0), (3, 1, 1.0), (1, 0, 3.0), (0, 1, 3.0)]

    def score(i, a, j, b):
        s = sum(W[p][q] for p in range(i, i + a) for q in range(j, j + b)) * 3
        ld = sum(len(L[p]) for p in range(i, i + a)) * ratio
        le = sum(len(R[q]) for q in range(j, j + b))
        return s - 1.2 * abs(math.log((le + 30) / (ld + 30)))

    best: dict[tuple[int, int], tuple[float, tuple | None]] = {(0, 0): (0.0, None)}
    for i in range(len(L) + 1):
        for j in range(len(R) + 1):
            if (i, j) not in best:
                continue
            base = best[(i, j)][0]
            for a, b, pen in steps:
                if i + a > len(L) or j + b > len(R):
                    continue
                v = base + score(i, a, j, b) - pen
                if (i + a, j + b) not in best or v > best[(i + a, j + b)][0]:
                    best[(i + a, j + b)] = (v, (i, j, a, b))
    blocks, k = [], (len(L), len(R))
    while best[k][1]:
        i, j, a, b = best[k][1]
        blocks.append((i, a, j, b))
        k = (i, j)
    return blocks[::-1]


def align_sentences(ds, es, ratio):
    steps = [(1, 1, 0.0), (1, 2, 0.4), (2, 1, 0.4), (2, 2, 0.9), (1, 0, 2.0), (0, 1, 2.0), (3, 1, 1.2), (1, 3, 1.2)]
    ln = lambda ss, i, a: sum(ss[k][1] - ss[k][0] for k in range(i, i + a))
    best: dict[tuple[int, int], tuple[float, tuple | None]] = {(0, 0): (0.0, None)}
    for i in range(len(ds) + 1):
        for j in range(len(es) + 1):
            if (i, j) not in best:
                continue
            for a, b, pen in steps:
                if i + a > len(ds) or j + b > len(es):
                    continue
                v = best[(i, j)][0] - abs(math.log((ln(es, j, b) + 15) / (ln(ds, i, a) * ratio + 15))) * 1.5 - pen
                if (i + a, j + b) not in best or v > best[(i + a, j + b)][0]:
                    best[(i + a, j + b)] = (v, (i, j, a, b))
    groups, k = [], (len(ds), len(es))
    while best[k][1]:
        i, j, a, b = best[k][1]
        groups.append((i, a, j, b))
        k = (i, j)
    return groups[::-1]


def align(left: Edition, right: Edition, *, anchors: list[tuple[str, str]] | None = None, auto_anchors: bool = True,
          pins: list[tuple[int, int]] | None = None, marks_from: list[str] | None = None) -> Parallel:
    Lc = [marks.parse(p)[0] for p in left.paragraphs]
    Rc = [marks.parse(p)[0] for p in right.paragraphs]
    W = _anchor_weights(Lc, Rc, anchors or [], auto_anchors, pins or [])
    blocks = align_paragraphs(Lc, Rc, W)
    right_marks: list[dict[int, list[str]]] = [{} for _ in right.paragraphs]     # transferred marks only
    report: list[str] = []
    info: list[dict] = []
    wanted = set(marks_from or [])
    for bi, (i, a, j, b) in enumerate(blocks):
        if b == 0 or a == 0:
            continue
        # block texts and the wanted marks of the left side, as offsets into the joined left text
        de_off, off = [], 0
        for p in range(i, i + a):
            de_off.append(off)
            off += len(Lc[p]) + 1
        de_full = " ".join(Lc[i:i + a])
        en_off, off = [], 0
        for q in range(j, j + b):
            en_off.append(off)
            off += len(Rc[q]) + 1
        en_full = " ".join(Rc[j:j + b])
        todo = []
        for p in range(i, i + a):
            for o, lst in sorted(marks.parse(left.paragraphs[p])[1].items()):
                for s in lst:
                    kind, args = marks.decode(s)
                    if kind == "M" and args[0] in wanted:
                        todo.append((de_off[p - i] + min(o, len(Lc[p])), args, s))
        if not todo:
            continue
        ds, es = sentences(de_full), sentences(en_full)
        groups = align_sentences(ds, es, len(en_full) / max(1, len(de_full)))
        for o, args, _s in todo:
            k = next((n for n, (s0, e0) in enumerate(ds) if s0 <= o <= e0 or o < s0), len(ds) - 1)
            gi, ga, gj, gb = next(g for g in groups if g[0] <= k < g[0] + g[1])
            if gb == 0:
                target, exact = (es[gj][0] if gj < len(es) else len(en_full)), False
            else:
                d0, d1 = ds[gi][0], ds[gi + ga - 1][1]
                e0, e1 = es[gj][0], es[gj + gb - 1][1]
                frac = (o - d0) / max(1, d1 - d0)
                exact = o <= d0 and "w" not in (args[2] if len(args) > 2 else "")
                target = e0 + round(frac * (e1 - e0))
                if not exact:
                    m = re.compile(r"\s").search(en_full, target)
                    target = min(m.end() if m else e1, e1)
            q = max(((q, en_off[q - j]) for q in range(j, j + b) if en_off[q - j] <= min(target, len(en_full))), key=lambda t: t[1])
            qo = min(target - q[1], len(Rc[q[0]]))
            flags = "" if exact else "a"
            right_marks[q[0]].setdefault(qo, []).append(marks.mark(args[0], args[1], flags))
            info.append({"edition": args[0], "label": args[1], "exact": exact, "block": bi,
                         "left": f"{de_full[max(0, o - 60):o]}⟦|⟧{de_full[o:o + 40]}",
                         "right": f"{Rc[q[0]][max(0, qo - 70):qo]}⟦|⟧{Rc[q[0]][qo:qo + 50]}"})
            report.append(f"{args[0]} {args[1]} ({'exact' if exact else 'approx'}), block {bi}: "
                          f"{de_full[max(0, o - 30):o]!r}|{de_full[o:o + 25]!r}  ->  ...{Rc[q[0]][max(0, qo - 35):qo]}|{Rc[q[0]][qo:qo + 35]}")
    out = []
    for i, a, j, b in blocks:
        out.append(Block(left.paragraphs[i:i + a], [_rebuild_with(right.paragraphs[q], right_marks[q]) for q in range(j, j + b)]))
    par = Parallel(left.id, right.id, out, report)
    par.marks_info = info
    par.shapes = list(blocks)
    return par


def _rebuild_with(para: str, new_marks: dict[int, list[str]]) -> str:
    """add the transferred marks (offsets in the paragraph's clean text) to the paragraph's own sentinels"""
    clean, own = marks.parse(para)
    merged: dict[int, list[str]] = collections.defaultdict(list)
    for off, lst in own.items():
        merged[off] += lst
    for off, lst in new_marks.items():
        merged[off] += lst
    return marks.rebuild(clean, merged)
