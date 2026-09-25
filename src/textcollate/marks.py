"""Inline markers inside paragraph strings.

A paragraph is a plain string in which zero-width *sentinels* carry structure, so text and page references
travel together through every stage (extraction, repair, alignment, rendering):

    \\x01M|<edition>|<label>|<flags>\\x01   a page break of <edition> starting here.
                                            flags: ``w`` = inside a word (Be|denken), ``a`` = approximate position
    \\x01N|<key>\\x01                        footnote marker
    \\x01BR\\x01                             forced line break     \\x01Q\\x01  block quotation paragraph
    \\x01I+\\x01 ... \\x01I-\\x01              emphasis
"""
from __future__ import annotations

import re

SENTINEL = re.compile(r"\x01([A-Z]+[+-]?)(?:\|([^\x01]*))?\x01")


def mark(edition: str, label: str, flags: str = "") -> str:
    return f"\x01M|{edition}|{label}|{flags}\x01"


def note(key: str) -> str:
    return f"\x01N|{key}\x01"


BR = "\x01BR\x01"
QUOTE = "\x01Q\x01"
EM_ON, EM_OFF = "\x01I+\x01", "\x01I-\x01"


def parse(text: str) -> tuple[str, dict[int, list[str]]]:
    """-> (clean text, {offset in clean text: [sentinel, ...]})"""
    clean, marks, pos, last = [], {}, 0, 0
    for m in SENTINEL.finditer(text):
        clean.append(text[last:m.start()])
        pos += m.start() - last
        marks.setdefault(pos, []).append(m.group(0))
        last = m.end()
    clean.append(text[last:])
    return "".join(clean), marks


def rebuild(clean: str, marks: dict[int, list[str]]) -> str:
    out, prev = [], 0
    for off in sorted(marks):
        off_c = min(off, len(clean))
        out.append(clean[prev:off_c] + "".join(marks[off]))
        prev = off_c
    out.append(clean[prev:])
    return "".join(out)


def strip(text: str, keep_br: bool = False) -> str:
    return SENTINEL.sub(lambda m: " " if (keep_br and m.group(1) == "BR") else "", text)


def decode(sentinel: str) -> tuple[str, list[str]]:
    """'\\x01M|ga16|517|w\\x01' -> ('M', ['ga16', '517', 'w'])"""
    m = SENTINEL.fullmatch(sentinel)
    if not m:
        raise ValueError(sentinel)
    return m.group(1), (m.group(2) or "").split("|") if m.group(2) is not None else []


def iter_marks(text: str, edition: str | None = None):
    """yield (clean offset, edition, label, flags) for page marks, in order"""
    for off, lst in sorted(parse(text)[1].items()):
        for s in lst:
            kind, args = decode(s)
            if kind == "M" and (edition is None or args[0] == edition):
                yield off, args[0], args[1], args[2] if len(args) > 2 else ""


def add_mark_at(text: str, offset: int, sentinel: str) -> str:
    clean, marks = parse(text)
    marks.setdefault(min(max(offset, 0), len(clean)), []).append(sentinel)
    return rebuild(clean, marks)


def drop_marks(text: str, edition: str) -> str:
    return re.sub(rf"\x01M\|{re.escape(edition)}\|[^\x01]*\x01", "", text)
