"""Build an Edition from its configuration: load pages -> reconstruct paragraphs -> clean -> notes."""
from __future__ import annotations

import re

from . import layout, marks, textnorm
from .config import Config
from .model import Edition
from .sources import load_pages


def _note_texts(raw: dict[str, str], ed: dict) -> dict[str, str]:
    """footnote texts per page -> {key: text}; explicit [[edition.note]] entries win over automatic splitting.
    layout.note_scope = "page": numbering restarts on every page, keys become "<page>:<n>" """
    out: dict[str, str] = {}
    L = ed.get("layout", {})
    split = re.compile(L.get("note_split", r"(?:^|(?<=\s))(\*|\d{1,2}[.)])\s+(?=[A-Z\"\u201c\u2018'(\[])"))
    page_scope = L.get("note_scope") == "page"
    last = None
    for label, text in raw.items():
        parts = split.split(text)
        if parts[0].strip() and last:                      # the rest of a note that began on the previous page
            out[last] = (out[last] + " " + parts[0].strip()).strip()
        for k, v in zip(parts[1::2], parts[2::2]):
            key = re.sub(r"[.)]$", "", k)
            last = f"{label}:{key}" if page_scope else key
            out[last] = v.strip()
    for n in ed.get("note", []):
        out[str(n["key"])] = n["text"]
    return out


def _insert_note_markers(paras: list[str], titles: list[str], ed: dict) -> tuple[list[str], list[str]]:
    for nm in ed.get("note_marker", []):
        key, after = str(nm["key"]), nm["after"]
        for pool in (titles, paras):
            done = False
            for i, text in enumerate(pool):
                clean, mk = marks.parse(text)
                j = clean.find(after)
                if j >= 0:
                    mk.setdefault(j + len(after), []).append(marks.note(key))
                    pool[i] = marks.rebuild(clean, mk)
                    done = True
                    break
            if done:
                break
        else:
            raise ValueError(f"note_marker {key!r}: anchor {after!r} not found in the text")
    return paras, titles


def _glued_note_markers(paras: list[str], rx: str, notes: dict[str, str], keymap: dict[str, str] | None = None,
                        page_edition: str | None = None) -> list[str]:
    """footnote numbers printed as glued digits (essence1): turn them into note markers when a note with that key exists"""
    pat = re.compile(rx)
    out = []
    page = None
    for p in paras:
        clean, mk = marks.parse(p)
        def page_at(off: int, start=page, mk=mk):
            cur = start
            if page_edition:
                for o in sorted(mk):
                    if o > off:
                        break
                    for sent in mk[o]:
                        kind, a = marks.decode(sent)
                        if kind == "M" and a[0] == page_edition:
                            cur = a[1]
            return cur

        def key_of(m):
            k = (keymap or {}).get(m.group(1), m.group(1))
            return f"{page_at(m.start())}:{k}" if page_edition else k
        hits = [(m.start(), m.end(), key_of(m)) for m in pat.finditer(clean) if key_of(m) in notes]
        for o in sorted(mk):                                # remember the page this paragraph ends on
            for sent in mk[o]:
                kind, a = marks.decode(sent)
                if kind == "M" and page_edition and a[0] == page_edition:
                    page = a[1]
        for a, b, key in reversed(hits):
            clean = clean[:a] + clean[b:]
            shifted = {}
            for off, lst in mk.items():
                shifted.setdefault(off - (b - a) if off >= b else (a if off > a else off), []).extend(lst)
            mk = shifted
            mk.setdefault(a, []).append(marks.note(key))
        out.append(marks.rebuild(clean, mk))
    return out


def apply_italics(paras: list[str], phrases: list[dict]) -> list[str]:
    """emphasis is lost by OCR: restore it for phrases given as {context = "...", phrase = "..."} (phrase must occur inside context)"""
    for spec in phrases:
        ctx, ph = spec["context"], spec["phrase"]
        for i, text in enumerate(paras):
            clean, mk = marks.parse(text)
            j = clean.find(ctx)
            if j < 0:
                continue
            k = clean.find(ph, j)
            if k < 0:
                break
            mk.setdefault(k, []).append(marks.EM_ON)
            mk.setdefault(k + len(ph), []).insert(0, marks.EM_OFF)
            paras[i] = marks.rebuild(clean, mk)
            break
    return paras


def apply_mark_at(paras: list[str], specs: list[dict]) -> list[str]:
    """declare a page break by a text anchor: [[edition.mark_at]] edition = "ga16", label = "526", before = "Denken wach,"
    (or after = "...", flags = "a").  Used for breaks that no source edition provides."""
    for spec in specs:
        anchor, where = (spec["before"], 0) if "before" in spec else (spec["after"], len(spec["after"]))
        for i, text in enumerate(paras):
            clean, mk = marks.parse(text)
            j = clean.find(anchor)
            if j >= 0:
                mk.setdefault(j + where, []).append(marks.mark(spec["edition"], str(spec["label"]), spec.get("flags", "")))
                paras[i] = marks.rebuild(clean, mk)
                break
        else:
            raise ValueError(f"mark_at anchor not found: {anchor!r}")
    return paras


def build(cfg: Config, ed_id: str, force: bool = False) -> Edition:
    ed = cfg.edition(ed_id)
    target = cfg.build_dir / "editions" / f"{ed_id}.json"
    pages = load_pages(ed, cfg)
    L = ed.get("layout", {})
    lex = layout.Lexicon.from_config(L.get("hyphens", {}))
    part0 = (ed.get("part") or [ed.get("source", {})])[0]
    margin_edition = (part0.get("margin_marks") or {}).get("edition")
    layout.REPAIRS.clear()
    paras, notes_raw, titles = layout.reconstruct(pages, L, ed_id, lex, margin_edition, bool((part0.get("margin_marks") or {}).get("sequence")))
    trust: dict[int, float] = {}
    if L.get("drop_paragraphs"):
        rx = [re.compile(x) for x in L["drop_paragraphs"]]
        kept, carry = [], ""
        for p in paras:
            if any(r.search(marks.strip(p).strip()) for r in rx):
                carry += "".join(m.group(0) for m in marks.SENTINEL.finditer(p) if marks.decode(m.group(0))[0] == "M")   # page marks survive
            else:
                kept.append(carry + p)
                carry = ""
        paras = kept
    # per-paragraph trust: the trust of the page the paragraph starts on (used when editions repair each other)
    label_trust = {p.label: p.trust for p in pages}
    last = pages[0].trust if pages else 0.5
    for i, para in enumerate(paras):
        m = next(iter(marks.iter_marks(para, ed_id)), None)
        if m:
            last = label_trust.get(m[2], last)
        trust[i] = last
    # text clean-up (explicit rules first, then language normalisation), applied between the sentinels
    C = ed.get("clean", {})
    def fix(t: str) -> str:
        t = textnorm.apply_rules(t, C)
        if C.get("normalise", True):
            t = textnorm.normalise(t, ed["language"], quotes=C.get("quotes"), dashes=C.get("dashes", True),
                                   abbrev=C.get("abbrev"), debris=C.get("debris", True), space_punct=C.get("space_punct", True))
        return t
    paras = [textnorm.clean_marked(p, fix) for p in paras]
    titles = [textnorm.clean_marked(t, fix) for t in titles]
    paras, titles = _insert_note_markers(paras, titles, ed)
    if ed.get("layout", {}).get("note_marker_re"):
        paras = _glued_note_markers(paras, ed["layout"]["note_marker_re"], _note_texts(notes_raw, ed), ed["layout"].get("note_marker_map"),
                                    ed_id if ed["layout"].get("note_scope") == "page" else None)
    paras = apply_italics(paras, ed.get("italic", []))
    paras = apply_mark_at(paras, ed.get("mark_at", []))
    edition = Edition(id=ed_id, label=ed.get("label", ed_id), language=ed["language"], paragraphs=paras,
                      notes=_note_texts(notes_raw, ed), title=ed.get("title") or " ".join(titles), trust=trust,
                      meta={"pages": [p.label for p in pages], "repairs": list(layout.REPAIRS), "origins": {p.label: list(p.origin) for p in pages if p.origin}})
    edition.save(target)
    return edition


def get(cfg: Config, ed_id: str, refresh: bool = False) -> Edition:
    path = cfg.build_dir / "editions" / f"{ed_id}.json"
    if path.exists() and not refresh:
        return Edition.load(path)
    return build(cfg, ed_id)
