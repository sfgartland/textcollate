"""Pages -> marked paragraphs.

Two families of sources:
  * geometry sources (pdf-text, pdf-ocr): lines with coordinates.  Paragraph starts come from indentation (`indent`),
    from short last lines (`shortline`) or both; furniture (running heads, folios) and footnotes are split off by
    position/size; hyphenated words are re-joined; the edition's own page breaks are recorded as marks.
  * given sources (html-pages, text): paragraphs already known; only the page joins have to be repaired.
"""
from __future__ import annotations

import re
import statistics
from collections import Counter

from . import marks
from .model import Line, PageData

TERMINAL = re.compile(r"[.?!:»«”“\"’)\]]\s*$")
HYPHEN_END = re.compile("[^\\W\\d_][-\u00ac\u00ad]$")


class Lexicon:
    def __init__(self, words: set[str] | None = None, keep: set[str] | None = None, mode: str = "join"):
        self.words, self.keep, self.mode = words or set(), {k.lower() for k in (keep or set())}, mode

    @classmethod
    def from_config(cls, cfg: dict) -> Lexicon:
        words: set[str] = set()
        for f in cfg.get("wordlist", []) if isinstance(cfg.get("wordlist"), list) else ([cfg["wordlist"]] if cfg.get("wordlist") else []):
            try:
                words |= {w.strip().lower() for w in open(f, encoding="utf-8", errors="ignore")}
            except OSError:
                pass
        return cls(words, set(cfg.get("keep", [])), cfg.get("mode", "join"))

    def join(self, head: str, tail: str) -> str:
        """head-\\ntail: return the joined word (keeping a hyphen only where it belongs to the word)"""
        h, t = re.sub(r"\W", "", marks.strip(head)), re.sub(r"\W", "", marks.strip(tail))
        if f"{h}-{t}".lower() in self.keep:
            return head + "-" + tail
        if self.mode == "lexicon" and self.words and (h + t).lower() not in self.words:
            return head + "-" + tail
        return head + tail


def _mode(values: list[float], step: float) -> float:
    return Counter(round(v / step) * step for v in values).most_common(1)[0][0]


def _drop_line_numbers(lines: list[Line], cfg: dict) -> list[Line]:
    """critical editions number every fifth line in the margin (the OCR reads them as the first word of the line):
    drop a leading multiple of `step` (<= `max`) that stands left of the text block"""
    step, mx = int(cfg.get("step", 5)), int(cfg.get("max", 60))
    starts = [l.words[0][1] for l in lines if l.words and re.match(r"[^\W\d_]", l.words[0][0])]
    if not starts:
        return lines
    left = _mode(starts, 4)
    out = []
    for l in lines:
        ws = l.words
        if ws and re.fullmatch(r"\d{1,2}", ws[0][0]) and int(ws[0][0]) % step == 0 and int(ws[0][0]) <= mx and ws[0][2] < left - float(cfg.get("slack", 4)):
            ws = ws[1:]
            if not ws:
                continue
            l = Line(" ".join(w[0] for w in ws), ws[0][1], ws[-1][2], l.y, l.h, ws)
        out.append(l)
    return out


def split_page(page: PageData, L: dict):
    """-> (body lines, footnote lines, title lines) for one page"""
    lines = [l for l in page.lines if l.text.strip()]
    if lines and L.get("line_numbers"):
        lines = _drop_line_numbers(lines, L["line_numbers"])
    if not lines:
        return [], [], []
    top, bottom = min(l.y for l in lines), max(l.y + l.h for l in lines)
    span = max(1.0, bottom - top)
    med_h = statistics.median(l.h for l in lines)
    furn = [re.compile(p) for p in L.get("furniture", [])]
    heads = [re.compile(p) for p in L.get("running_heads", [])]      # like furniture, but only in the top band (chapter titles keep theirs)
    titles = [re.compile(p) for p in L.get("title", [])]
    ncfg = L.get("notes") or {}
    body, notes, title = [], [], []
    note_from = None
    if ncfg.get("start_re"):
        # the first line in the lower part of the page that looks like the start of a note ("1) ...", "2. ...") opens the notes
        rx = re.compile(ncfg["start_re"])
        lower = [l for l in lines if l.y >= top + float(ncfg.get("min_frac", 0.6)) * span and rx.match(l.text.strip())]
        if lower:
            note_from = min(lower, key=lambda l: l.y).y - 1
    if ncfg.get("marker_lines"):
        # footnotes introduced by a small superscript marker line ("b") near the foot of the page: the last such marker
        # starts the note; only a few lines may follow it
        markers = [l for l in lines if re.fullmatch(r"[a-z*\d]", l.text.strip()) and l.h < 0.8 * med_h]
        if markers:
            m = max(markers, key=lambda l: l.y)
            tail = [l for l in lines if l.y >= m.y - 2]
            if len(tail) <= int(ncfg.get("max_lines", 6)):
                note_from = m.y - 2
    for l in lines:
        t = l.text.strip()
        edge = l.y < top + 0.10 * span or l.y > bottom - 0.10 * span
        if any(f.fullmatch(t) for f in furn) or (l.y < top + 0.035 * span and any(f.fullmatch(t) for f in heads)) or (L.get("drop_folios", True) and re.fullmatch(r"\d{1,4}\.?", t) and edge):
            continue
        if any(x.fullmatch(t) for x in titles):
            title.append(t)
            continue
        if note_from is not None and l.y >= note_from:
            notes.append(l)
            continue
        if ncfg and not ncfg.get("marker_lines") and not ncfg.get("start_re"):
            below = l.y >= ncfg["min_y"] if "min_y" in ncfg else l.y >= top + float(ncfg.get("frac", 0.75)) * span
            if below and l.h <= float(ncfg.get("height_ratio", 0.85)) * med_h:
                notes.append(l)
                continue
        body.append(l)
    return body, notes, title


def _flush(cur: list[str], paras: list[str], quote: bool) -> None:
    words = [w for w in cur if w]
    if any(not marks.SENTINEL.fullmatch(w) for w in words):
        text = " ".join(words)
        text = re.sub(r"\s*(\x01BR\x01)\s*", r"\1", text)
        paras.append((marks.QUOTE if quote else "") + text)
    elif words and paras:                          # only marks left: attach to the previous paragraph
        paras[-1] += "".join(words)
    cur.clear()


REPAIRS: list[str] = []          # sequence repairs of embedded page numbers, reported by the build


def from_lines(pages: list[PageData], L: dict, edition: str, lex: Lexicon, margin_edition: str | None = None, margin_sequence: bool = False):
    paras: list[str] = []
    cur: list[str] = []
    notes: dict[str, str] = {}
    titles: list[str] = []
    mode = L.get("paragraphs", "indent")
    indent_frac = float(L.get("indent_frac", 0.035))
    short_frac = float(L.get("short_frac", 0.10))
    centred_frac = float(L.get("centred_frac", 0.10))
    qlo, qhi = L.get("quote_frac", [0.04, 0.10]) if L.get("quotes", True) else (9, 9)
    suspended = tuple(L.get("suspended", ["und", "oder", "and", "or"]))
    drop_tokens = [re.compile(x) for x in L.get("drop_tokens", [])]        # OCR debris such as a stray "O"
    carry: str | None = None          # head of a word hyphenated at the line end
    last_margin: int | None = None
    quote_open = prev_centred = pending_break = prev_head = False
    head_ratio = float(L.get("heading_ratio", 0))       # lines set larger than the body text are headings: a paragraph of their own
    head_re = re.compile(L["heading_re"]) if L.get("heading_re") else None      # or lines that start like one ("§ 11."); centred lines after it continue it
    for pg in pages:
        body, page_notes, title = split_page(pg, L)
        titles += title
        if page_notes:
            notes[pg.label] = " ".join(l.text.strip() for l in page_notes)
        if not body:
            continue
        left = _mode([l.x0 for l in body], 4)
        right = _mode([l.x1 for l in body], 4)
        tw = max(1.0, right - left)
        pending_margin = sorted(pg.margin) if margin_edition else []
        inds = [(l.x0 - left) / tw for l in body]
        in_range = [qlo < x <= qhi for x in inds]
        med_h = statistics.median(l.h for l in body)
        hstart = [bool(head_re and head_re.match(l.text.strip())) or (bool(head_ratio) and l.h > head_ratio * med_h and len(l.text.split()) > 1) for l in body]
        in_range = [r and not h for r, h in zip(in_range, hstart)]       # an indented heading is not a block quotation
        for i, l in enumerate(body):
            ind = inds[i]
            centred = ind > centred_frac and l.x1 < right - 0.05 * tw
            head_start = hstart[i]
            head = head_start or (prev_head and centred and bool(head_re))
            # a block quotation is indented over several lines; a paragraph indent affects exactly one
            quote = not head and not centred and in_range[i] and ((i > 0 and in_range[i - 1]) or (i + 1 < len(body) and in_range[i + 1]))
            words = [w for w in l.text.split() if not any(rx.fullmatch(w) for rx in drop_tokens)]
            starts = False
            if cur and carry is None:
                if mode in ("indent", "both") and ind > indent_frac and not quote and not centred:
                    starts = True
                if centred != prev_centred and (centred or prev_centred) and not (centred and prev_centred):
                    starts = True
                if quote != quote_open:
                    starts = True
                if head != prev_head or (head and re.match(r"(§|Chapter\b|Kapitel\b)", l.text.strip())):
                    starts = True
                if head and prev_head and not head_start:        # second line of a heading
                    starts = False
                if pending_break and not (centred and prev_centred) and words and words[0].lstrip("\u00bb(\u201c\"")[:1].isupper():
                    starts = True
            if starts:
                _flush(cur, paras, quote_open)
            pending_break = False
            first = i == 0
            margin_marks = []
            while pending_margin and pending_margin[0][0] <= l.y + 0.5 * max(l.h, 1):
                label = pending_margin.pop(0)[1]
                if margin_sequence and label.isdigit():
                    if last_margin is not None and int(label) not in (last_margin + 1, last_margin + 2):
                        REPAIRS.append(f"{margin_edition}: read {label!r} after {last_margin}, set to {last_margin + 1}")
                        label = str(last_margin + 1)
                    last_margin = int(label)
                margin_marks.append(marks.mark(margin_edition, label))
            if carry is not None and words:
                nxt = words.pop(0)
                cur.append(lex.join(carry, marks.mark(edition, pg.label, "w") + nxt if first else nxt))
                carry = None
            elif first:
                cur.append(marks.mark(edition, pg.label))
            if centred and prev_centred:
                cur.append(marks.BR)
            if margin_marks and carry is None:
                cur.extend(margin_marks)
            quote_open, prev_centred, prev_head = quote, centred, head
            cur.extend(words)
            nxt_line = body[i + 1].text.split() if i + 1 < len(body) else []
            if cur and words and HYPHEN_END.search(cur[-1]) and len(cur[-1]) > 2 and not (nxt_line and nxt_line[0].lower() in suspended):
                carry = cur.pop()[:-1]
            elif mode in ("shortline", "both") and l.x1 < right - short_frac * tw and TERMINAL.search(marks.strip(" ".join(cur))):
                pending_break = True
        # a page never ends a paragraph by itself
    if carry is not None:
        cur.append(carry)
    _flush(cur, paras, quote_open)
    return paras, notes, titles


def from_paragraphs(pages: list[PageData], L: dict, edition: str):
    """sources that know their paragraphs: add page marks and repair paragraphs that run across a page break"""
    paras: list[str] = []
    notes: dict[str, str] = {}
    for pg in pages:
        for i, p in enumerate(pg.paragraphs or []):
            if i == 0:
                prev = paras[-1] if paras else ""
                plain_prev = marks.strip(prev)
                if prev and L.get("merge_pages", True) and (not TERMINAL.search(plain_prev) or marks.strip(p)[:1].islower()):
                    # the paragraph runs on across the page break; a fragment lost at the page foot (Be-|denken) is repaired
                    # later by collation against another edition, so a lowercase start after a full stop just gets a mark
                    if plain_prev.endswith("-"):
                        paras[-1] = prev + marks.mark(edition, pg.label, "w") + p
                    else:
                        paras[-1] = prev + " " + marks.mark(edition, pg.label) + " " + p
                    continue
                p = marks.mark(edition, pg.label) + p
            paras.append(p)
    return paras, notes, []


def continues(prev: str, nxt: str) -> bool:
    """does the paragraph `prev` run on into `nxt` (next page / next source)?"""
    return bool(prev) and (not TERMINAL.search(marks.strip(prev)) or marks.strip(nxt)[:1].islower())


def reconstruct(pages: list[PageData], L: dict, edition: str, lex: Lexicon, margin_edition: str | None = None, margin_sequence: bool = False):
    """pages of one edition; runs of line-based and paragraph-based pages (from different sources) are joined at their seams"""
    from itertools import groupby
    paras: list[str] = []
    notes: dict[str, str] = {}
    titles: list[str] = []
    for given, run in groupby(pages, key=lambda p: p.paragraphs is not None):
        run = list(run)
        got, n, t = from_paragraphs(run, L, edition) if given else from_lines(run, L, edition, lex, margin_edition, margin_sequence)
        notes.update(n)
        titles += t
        if paras and got and L.get("merge_pages", True) and continues(paras[-1], got[0]):
            paras[-1] = paras[-1] + " " + got[0]
            got = got[1:]
        paras += got
    return paras, notes, titles
