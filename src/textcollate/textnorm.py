"""Typographic normalisation of running text (per language)."""
from __future__ import annotations

import re

from . import marks

THIN = " "
QUOTES = "«»\"“”„"


def positional_quotes(t: str, open_q: str, close_q: str) -> str:
    """decide opening vs closing quote by position (after space/bracket + before a letter = opening), not by the glyph OCR chose"""
    def q(m):
        i = m.start()
        opening = (i == 0 or t[i - 1] in " ([–—") and i + 1 < len(t) and (t[i + 1].isalnum() or t[i + 1] in "([")
        return open_q if opening else close_q
    return re.sub(f"[{QUOTES}]", q, t)


def abbrev_pattern(abbrev: str) -> tuple[re.Pattern, str]:
    """'d. h.' -> matches d.h. / d. h / d.h, and rewrites to 'd.<thin>h.'"""
    parts = [p for p in re.split(r"[.\s]+", abbrev) if p]
    rx = r"\b" + r"\.\s?".join(re.escape(p) for p in parts) + r"[.,]"
    return re.compile(rx), ("." + THIN).join(parts) + "."


def normalise(t: str, language: str = "de", *, quotes: str | None = None, dashes: bool = True, abbrev: list[str] | None = None,
              debris: bool = True, space_punct: bool = True) -> str:
    quotes = quotes or ("de" if language.startswith("de") else "en")
    if quotes == "de":
        t = positional_quotes(t, "»", "«")
    elif quotes == "en":
        t = t.replace("\u2018\u2018", "\u201c").replace("\u2019\u2019", "\u201d").replace("''", "\u201d").replace("``", "\u201c")
        t = re.sub("\u2019(?=\u201d)", "", t)                                   # Feldweg’” -> Feldweg”
        t = positional_quotes(t, "\u201c", "\u201d")
        t = t.replace("\u201d\u2019", "\u201d").replace("\u201c\u2018", "\u201c")
    if dashes:
        t = re.sub(r"(?<=\s)[-—–](?=\s)", "–" if language.startswith("de") else "—", t)
        t = re.sub(r"[—-]*—[—-]*", "—", t) if not language.startswith("de") else t
        t = re.sub(r"(?<=[a-zäöüß])-(und|oder)\b", r"- \1", t)      # aus-und -> aus- und
    for a in abbrev or []:
        rx, rep = abbrev_pattern(a)
        t = rx.sub(rep, t)
    if debris:
        t = re.sub(r"(?<=[^\W\d_])\d+(?=[^\W\d_])", "", t)                       # W7enn
        t = t.replace("¬", "")
    if space_punct:
        t = re.sub(r"\s+([?!:;,])", r"\1", t)
    return re.sub(r"[ \t]{2,}", " ", t)


def apply_rules(t: str, cfg: dict) -> str:
    """explicit per-edition clean-up: replace = [[a,b],...], regex = [[pattern, repl],...], drop = ["®"]"""
    for a, b in cfg.get("replace", []):
        t = t.replace(a, b)
    for pat, rep in cfg.get("regex", []):
        t = re.sub(pat, rep, t)
    for d in cfg.get("drop", []):
        t = t.replace(d, "")
    return t


def clean_marked(text: str, fn) -> str:
    """apply a text function to the plain segments of a marked paragraph, leaving sentinels alone"""
    out, last = [], 0
    for m in marks.SENTINEL.finditer(text):
        out.append(fn(text[last:m.start()]))
        out.append(m.group(0))
        last = m.end()
    out.append(fn(text[last:]))
    return "".join(out)
