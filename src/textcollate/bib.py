"""biblatex entries from the configuration."""
from __future__ import annotations

from .config import Config


def entry(key: str, table: dict, related: list[str] | None = None) -> str:
    t = dict(table)
    typ = t.pop("type", "book")
    key = t.pop("key", key)
    if related:
        t.setdefault("related", ",".join(related))
        t.setdefault("relatedtype", "compiledfrom")
    width = max((len(k) for k in t), default=8)
    body = ",\n".join(f"  {k:<{width}} = {{{v}}}" for k, v in t.items())
    return f"@{typ}{{{key},\n{body}\n}}\n"


def entries(cfg: Config) -> str:
    out, keys = [], {}
    for eid, ed in cfg.editions.items():
        if "bib" in ed:
            keys[eid] = ed["bib"].get("key", eid)
            out.append(entry(eid, ed["bib"]))
    for o in cfg.outputs:
        if "bib" in o:
            rel = [keys[e] for e in (o.get("edition"), o.get("left"), o.get("right")) if e in keys]
            out.append(entry(o["id"], o["bib"], rel))
    return "\n".join(out)
