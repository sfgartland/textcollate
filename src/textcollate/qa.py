"""Checks: does the translation cover the same material, in the same order?"""
from __future__ import annotations

import re

from . import marks
from .model import Edition


def anchor_order(left: Edition, right: Edition, pairs: list[dict]) -> dict:
    """pairs = [{left = regex, right = regex}]: every anchor must be found in both texts, in the same order in each"""
    lt = re.sub(r"\s+", " ", " ".join(marks.strip(p, keep_br=True) for p in left.paragraphs))
    rt = re.sub(r"\s+", " ", " ".join(marks.strip(p, keep_br=True) for p in right.paragraphs))

    def run(text, key):
        last, absent, ooo = 0, [], []
        for a in pairs:
            m = re.search(a[key], text[last:], re.DOTALL | re.IGNORECASE)
            if m:
                last += m.end()
            elif re.search(a[key], text, re.DOTALL | re.IGNORECASE):
                ooo.append(a[key])
            else:
                absent.append(a[key])
        return absent, ooo

    la, lo = run(lt, "left")
    ra, ro = run(rt, "right")
    n = len(pairs)
    return {"anchors": n, "left_in_order": n - len(la) - len(lo), "right_in_order": n - len(ra) - len(ro),
            "absent_left": la, "absent_right": ra, "out_of_order_left": lo, "out_of_order_right": ro}


def mark_census(ed: Edition) -> dict[str, list[str]]:
    """{edition id: [labels in order]} of the page marks inside an edition"""
    out: dict[str, list[str]] = {}
    for p in ed.paragraphs:
        for _, eid, label, _ in marks.iter_marks(p):
            out.setdefault(eid, []).append(label)
    return out
