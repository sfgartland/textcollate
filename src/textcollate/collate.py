"""Same-language collation of editions.

Two editions of one text (say a clean web transcription and a noisy scan) are aligned word by word.  Alignment is used to

  * repair OCR slips in the weaker edition (trust-aware, every change logged),
  * take paragraph starts from an edition whose paragraphs are reliable,
  * carry page marks (original pagination) from one edition into the other, even when a page break falls inside a word,
  * report differences (`compare`), separating OCR-like noise from substantive variants.
"""
from __future__ import annotations

import collections
import difflib
import re
from dataclasses import dataclass, field

from . import marks
from .model import Edition

LETTERS = "A-Za-zÄÖÜäöüßÀ-ÿ"


def core(tok: str) -> str:
    return re.sub(rf"[^{LETTERS}]", "", marks.SENTINEL.sub("", tok))


def lev(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


@dataclass
class Flat:
    """an edition as one token stream"""
    toks: list[str]
    par_of: list[int]                 # token index -> paragraph index
    par_starts: set[int]              # token indices that start a paragraph
    trust: list[float]                # per token
    lead: dict[int, str] = field(default_factory=dict)   # paragraph-leading sentinel (quote) per paragraph start token

    @classmethod
    def of(cls, ed: Edition) -> Flat:
        toks, par_of, starts, trust = [], [], set(), []
        for pi, para in enumerate(ed.paragraphs):
            starts.add(len(toks))
            para = re.sub(rf"\s*({re.escape(marks.BR)})\s*", r" \1 ", para)
            # page marks between words become standalone tokens; marks inside a word (flag w) stay glued
            para = re.sub(r"\x01M\|[^\x01|]*\|[^\x01|]*\|(?![^\x01]*w)[^\x01]*\x01", lambda m: f" {m.group(0)} ", para)
            for t in para.split():
                toks.append(t)
                par_of.append(pi)
                trust.append(ed.trust.get(pi, 0.5))
        return cls(toks, par_of, starts, trust)

    def cores(self) -> list[tuple[int, str]]:
        return [(i, core(t)) for i, t in enumerate(self.toks) if core(t) and not marks.SENTINEL.fullmatch(t)]

    def paragraphs(self) -> list[str]:
        out, cur = [], []
        for i, t in enumerate(self.toks):
            if i in self.par_starts and cur:
                out.append(cur)
                cur = []
            if t:
                cur.append(t)
        if cur:
            out.append(cur)
        return [re.sub(rf"\s*({re.escape(marks.BR)})\s*", r"\1", " ".join(p)) for p in out]


@dataclass
class Report:
    log: list[str] = field(default_factory=list)
    unresolved: list[tuple[str, str]] = field(default_factory=list)
    unresolved_at: list[dict] = field(default_factory=list)      # {ref, target, ref_edition, token} for the review step
    starts_added: list[str] = field(default_factory=list)
    marks_moved: list[str] = field(default_factory=list)

    def text(self) -> str:
        out = [f"corrections: {len(self.log)}", *("  " + x for x in self.log),
               f"paragraph starts taken from references: {len(self.starts_added)}", *("  " + x for x in self.starts_added),
               f"marks carried over: {len(self.marks_moved)}", *("  " + x for x in self.marks_moved),
               f"unresolved differences: {len(self.unresolved)}", *(f"  ref {a!r} | target {b!r}" for a, b in self.unresolved)]
        return "\n".join(out) + "\n"


def _aligner(a: list[str], b: list[str]) -> difflib.SequenceMatcher:
    return difflib.SequenceMatcher(None, a, b, autojunk=len(a) > 30000)


def collate(target: Edition, refs: list[Edition], *, repair: bool = True, paragraph_starts: list[str] | None = None,
            marks_from: list[str] | None = None) -> tuple[Edition, Report]:
    """-> (new target edition, report).  `refs` in priority order; only tokens still differing are offered to later refs."""
    T = Flat.of(target)
    rep = Report()
    corpus = collections.Counter(w for e in [target, *refs] for w in re.findall(rf"[{LETTERS}]{{3,}}", marks.strip(" ".join(e.paragraphs))))
    # vocabulary attested in the references: a word of the target that no reference contains is a suspect
    LEX = {w for e in refs for w in re.findall(rf"[{LETTERS}]{{3,}}", marks.strip(" ".join(e.paragraphs)))}
    # ... and the vocabulary of the trustworthy paragraphs only (OCR garbage in a weak reference must not license a merge)
    STRONG = {w for e in refs for i, p in enumerate(e.paragraphs) if e.trust.get(i, 0.5) >= 0.9
              for w in re.findall(rf"[{LETTERS}]{{3,}}", marks.strip(p))}
    tcount = collections.Counter(core(t) for t in T.toks)
    starts_from = set(paragraph_starts or [])
    mark_eds = set(marks_from or [])
    new_starts: set[int] = set()
    new_marks: dict[int, list[str]] = collections.defaultdict(list)      # target token -> sentinels to insert before it
    inword: list[tuple[int, str, str]] = []                             # (target token, sentinel, ref core)

    for ref in refs:
        R = Flat.of(ref)
        rc, tc = R.cores(), T.cores()
        sm = _aligner([c for _, c in rc], [c for _, c in tc])
        i2j: dict[int, int] = {}

        def fix_token(j: int, n: str, r: str, trust: float) -> bool:
            nl, rl = n.lower(), r.lower()
            if nl != rl and (nl.endswith(rl) or nl.startswith(rl) or rl.endswith(nl) or rl.startswith(nl)):
                return False                                       # a word fragment (Be|denken), not an OCR slip
            d = lev(rl, nl)
            rare = tcount[n] <= 1 and corpus.get(r, 0) >= 3
            ok = len(r) >= 3 and ((d == 0 and r != n and n not in LEX and r in LEX) or
                                  (0 < d <= 2 and trust >= 0.9 and (n not in LEX or d == 1)) or
                                  (0 < d <= 2 and trust < 0.9 and ((n not in LEX and r in LEX) or (d == 1 and rare))))
            if ok and repair and n in T.toks[j]:
                rep.log.append(f"{n} -> {r}")
                T.toks[j] = T.toks[j].replace(n, r, 1)
                return True
            return False

        for tag, a1, a2, b1, b2 in sm.get_opcodes():
            Rr, Tt = rc[a1:a2], tc[b1:b2]
            if tag == "equal":
                for d in range(len(Rr)):
                    i2j[Rr[d][0]] = Tt[d][0]
            elif tag == "replace" and len(Rr) == len(Tt):
                for d in range(len(Rr)):
                    i2j[Rr[d][0]] = Tt[d][0]
                    if Rr[d][1] != Tt[d][1] and not fix_token(Tt[d][0], Tt[d][1], Rr[d][1], R.trust[Rr[d][0]]):
                        rep.unresolved.append((Rr[d][1], Tt[d][1]))
                        rep.unresolved_at.append({"ref": Rr[d][1], "target": Tt[d][1], "ref_edition": ref.id, "token": Tt[d][0]})
            elif tag == "replace" and repair and len(Rr) == 1 and len(Tt) == 2 and Rr[0][1] == Tt[0][1] + Tt[1][1] \
                    and (Rr[0][1] in STRONG or R.trust[Rr[0][0]] >= 0.9) and Tt[1][1].lower() not in ("und", "oder", "and", "or"):
                rep.log.append(f"{T.toks[Tt[0][0]]} {T.toks[Tt[1][0]]} -> joined")
                T.toks[Tt[0][0]] += T.toks[Tt[1][0]]
                T.toks[Tt[1][0]] = ""
                i2j[Rr[0][0]] = Tt[0][0]
            elif tag == "replace" and repair and len(Rr) == 2 and len(Tt) == 1 and Tt[0][1] == Rr[0][1] + Rr[1][1] and Tt[0][1] not in STRONG:
                rep.log.append(f"{T.toks[Tt[0][0]]} -> {R.toks[Rr[0][0]]} {R.toks[Rr[1][0]]}")
                T.toks[Tt[0][0]] = R.toks[Rr[0][0]] + " " + R.toks[Rr[1][0]]
                i2j[Rr[0][0]] = Tt[0][0]
            elif tag == "replace" and len(Rr) == 2 and len(Tt) == 1 and Tt[0][1] == Rr[0][1] + Rr[1][1]:
                i2j[Rr[0][0]] = i2j[Rr[1][0]] = Tt[0][0]                # word cut in the reference (Nach|denken)
            elif tag == "delete" and repair and 1 <= len(Rr) <= 2 and all(R.trust[r[0]] >= 0.9 for r in Rr) and b1 < len(tc):
                j = tc[b1][0]
                words = " ".join(R.toks[r[0]] for r in Rr)
                rep.log.append(f"(missing) + {words}")
                T.toks[j] = words + " " + T.toks[j]
                if j > 0 and re.fullmatch(r"[\d|]{1,2}", T.toks[j - 1]):
                    rep.log.append(f"(debris) {T.toks[j - 1]} removed")
                    T.toks[j - 1] = ""
            else:
                rep.unresolved.append((" ".join(c for _, c in Rr), " ".join(c for _, c in Tt)))
                pos = Tt[0][0] if Tt else (tc[b1][0] if b1 < len(tc) else len(T.toks) - 1)
                if len(Rr) <= 12 and len(Tt) <= 12:                    # long stretches are missing coverage, not variants
                    rep.unresolved_at.append({"ref": " ".join(c for _, c in Rr), "target": " ".join(c for _, c in Tt), "ref_edition": ref.id, "token": pos})

        def target_index(r: int, i2j: dict[int, int] = i2j) -> int | None:
            for k in range(r, r + 4):
                if k in i2j:
                    return i2j[k]
            return None

        def is_mark(t: str) -> bool:
            return bool(marks.SENTINEL.fullmatch(t)) and marks.decode(t)[0] == "M"

        def para_start_at(j: int) -> int | None:
            """a new paragraph opens at token j together with the page marks just before it; None if that would leave
            the previous paragraph holding nothing but marks (it already starts here)"""
            while j > 0 and is_mark(T.toks[j - 1]) and (j - 1) not in T.par_starts:
                j -= 1
            prev = max((k for k in T.par_starts if k < j), default=0)
            if all(is_mark(T.toks[k]) or not T.toks[k] for k in range(prev, j)):
                return None
            return j

        if ref.id in starts_from:
            for pi_start in sorted(R.par_starts):
                j = target_index(pi_start if core(R.toks[pi_start]) else next((k for k in range(pi_start, len(R.toks)) if core(R.toks[k])), pi_start))
                j = para_start_at(j) if j is not None else None
                if j is not None and j not in T.par_starts and j not in new_starts and j != 0:
                    new_starts.add(j)
                    rep.starts_added.append(" ".join(marks.strip(T.toks[j + k]) for k in range(4) if j + k < len(T.toks)))
        # marks of the wanted editions: standalone sentinel tokens precede the next word; in-word ones sit inside a token
        pending: list[str] = []
        for r, tok in enumerate(R.toks):
            sent = marks.SENTINEL.findall(tok) and [m.group(0) for m in marks.SENTINEL.finditer(tok)]
            mine = [s for s in sent if marks.decode(s)[0] == "M" and marks.decode(s)[1][0] in mark_eds]
            if marks.SENTINEL.fullmatch(tok):
                pending += mine
                continue
            inside = mine if core(tok) else []
            if inside:                                        # e.g. "denken" after "Be|" or "Nach|denken" in the reference
                c = core(marks.SENTINEL.sub("", tok))
                pos_in_ref = re.sub(rf"[^{LETTERS}]", "", tok[:tok.index(inside[0])])
                j = target_index(r)
                if j is not None:
                    inword.append((j, inside[0], pos_in_ref and c[len(pos_in_ref):] or ""))
                    rep.marks_moved.append(f"{marks.decode(inside[0])[1][1]} inside word at target token {j}")
                continue
            if pending:
                j = target_index(r)
                if j is not None:
                    rc_ = core(tok)
                    tc_ = core(T.toks[j])
                    if len(pending) == 1 and rc_ and tc_ != rc_ and tc_.lower().endswith(rc_.lower()):
                        # the reference page starts with the tail of a word the target has whole (Be|denken)
                        m_, args = marks.decode(pending[0])
                        inword.append((j, marks.mark(args[0], args[1], (args[2] if len(args) > 2 else "") + "w"), rc_))
                        rep.marks_moved.append(f"{args[1]} inside {tc_!r}")
                    else:
                        new_marks[j] += pending
                        rep.marks_moved += [f"{marks.decode(s)[1][0]}:{marks.decode(s)[1][1]} before {marks.strip(T.toks[j])!r}" for s in pending]
                pending = []
    # apply
    for j, sents in new_marks.items():
        T.toks[j] = " ".join(sents) + " " + T.toks[j]
    for j, sent, tail in inword:
        t = T.toks[j]
        plain_core = core(t)
        pos = t.lower().rfind(tail.lower()) if tail else 0
        if tail and pos > 0 and plain_core != tail:
            T.toks[j] = t[:pos] + sent + t[pos:]
        else:
            T.toks[j] = sent + " " + t
    T.par_starts |= new_starts
    out = Edition(id=target.id, label=target.label, language=target.language, paragraphs=T.paragraphs(), notes=dict(target.notes),
                  title=target.title, trust={}, meta=dict(target.meta))
    for u in rep.unresolved_at:                                          # context and page of each unresolved difference
        u["context"], u["page"] = context_at(T, u["token"], target.id)
    return out, rep


def context_at(T: "Flat", j: int, ed_id: str, width: int = 7) -> tuple[str, str | None]:
    """the words around token j (page marks removed) and the target's own page label at that point"""
    page = None
    for k in range(min(j, len(T.toks) - 1), -1, -1):
        for m in marks.SENTINEL.finditer(T.toks[k]):
            kind, a = marks.decode(m.group(0))
            if kind == "M" and a[0] == ed_id:
                page = a[1]
                break
        if page:
            break
    words = [marks.strip(t) for t in T.toks[max(0, j - width):j + width + 1] if marks.strip(t)]
    return " ".join(words), page


# ---------------------------------------------------------------------------------- compare
def compare(a: Edition, b: Edition) -> tuple[str, dict]:
    """word-level differences of b against a, classified: ocr-like (1:1, small edit distance), spacing/hyphenation, substantive"""
    A, B = Flat.of(a).cores(), Flat.of(b).cores()
    sm = _aligner([c for _, c in A], [c for _, c in B])
    stats = collections.Counter()
    rows = []
    for tag, a1, a2, b1, b2 in sm.get_opcodes():
        if tag == "equal":
            continue
        x, y = " ".join(c for _, c in A[a1:a2]), " ".join(c for _, c in B[b1:b2])
        if x.replace(" ", "") == y.replace(" ", ""):
            kind = "spacing/hyphenation"
        elif tag == "replace" and (a2 - a1) == (b2 - b1) == 1 and lev(x.lower(), y.lower()) <= 2:
            kind = "ocr-like"
        else:
            kind = "substantive"
        stats[kind] += 1
        rows.append((kind, x, y))
    total = len(A)
    lines = [f"# {a.label} vs {b.label}", "", f"words: {a.label} {len(A)}, {b.label} {len(B)}",
             *(f"- {k}: {v}" for k, v in stats.items()), "", "| kind | " + a.label + " | " + b.label + " |", "|---|---|---|"]
    lines += [f"| {k} | {x[:60]} | {y[:60]} |" for k, x, y in rows if k != "spacing/hyphenation"]
    return "\n".join(lines) + "\n", {"words_a": len(A), "words_b": len(B), **stats, "total": total}
