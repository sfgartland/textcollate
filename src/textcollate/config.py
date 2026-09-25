"""Project configuration (TOML).

    [project]            name, title, author, build_dir
    [latex]              paper, fontsize, font, engine
    [[edition]]          id, label, language, [edition.source] / [[edition.part]], [edition.layout], [edition.clean], [edition.bib]
    [[output]]           kind = "single" | "parallel" | "compare" ...

See docs/config.md and examples/gelassenheit/textcollate.toml.
"""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


class ConfigError(ValueError):
    pass


PATH_KEYS = {"path", "pattern", "file", "tessdata_dir", "wordlist", "build_dir", "tex", "pdf"}


def resolve_path(value: str, base: Path) -> str:
    """expand ~ and ${VAR}; relative paths are relative to the config file (braces/globs are left alone)"""
    value = os.path.expandvars(os.path.expanduser(value))
    return value if os.path.isabs(value) else str(base / value)


def walk(value, base: Path, key: str | None = None):
    if isinstance(value, dict):
        return {k: walk(v, base, k) for k, v in value.items()}
    if isinstance(value, list):
        return [walk(v, base, key) for v in value]
    if isinstance(value, str) and key in PATH_KEYS:
        return resolve_path(value, base)
    return value


@dataclass
class Config:
    path: Path
    data: dict

    @property
    def root(self) -> Path:
        return self.path.parent

    @property
    def project(self) -> dict:
        return self.data.get("project", {})

    @property
    def build_dir(self) -> Path:
        return Path(self.project.get("build_dir", self.root / "build"))

    @property
    def latex(self) -> dict:
        return {"engine": "lualatex", "paper": "a4paper", "fontsize": "10pt", "font": "TeX Gyre Pagella", **self.data.get("latex", {})}

    @property
    def editions(self) -> dict[str, dict]:
        return {e["id"]: e for e in self.data.get("edition", [])}

    @property
    def outputs(self) -> list[dict]:
        return self.data.get("output", [])

    def edition(self, ed_id: str) -> dict:
        try:
            return self.editions[ed_id]
        except KeyError:
            raise ConfigError(f"unknown edition {ed_id!r}; known: {', '.join(self.editions)}") from None

    def output(self, out_id: str) -> dict:
        for o in self.outputs:
            if o.get("id") == out_id:
                return o
        raise ConfigError(f"unknown output {out_id!r}; known: {', '.join(o.get('id', '?') for o in self.outputs)}")


def load(path: str | Path) -> Config:
    path = Path(path).resolve()
    if path.is_dir():
        path = path / "textcollate.toml"
    if not path.exists():
        raise ConfigError(f"no config at {path}")
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    data = walk(raw, path.parent)
    seen = set()
    for e in data.get("edition", []):
        for key in ("id", "language"):
            if key not in e:
                raise ConfigError(f"edition without {key!r}: {e}")
        if e["id"] in seen:
            raise ConfigError(f"duplicate edition id {e['id']!r}")
        seen.add(e["id"])
        e.setdefault("label", e["id"])
    cfg = Config(path, data)
    if "build_dir" not in cfg.project:
        cfg.data.setdefault("project", {})["build_dir"] = str(path.parent / "build")
    return cfg


def parse_pages(spec, default=None) -> list[int]:
    """'13-30', '1,3,5-7' or a list -> [ints]"""
    if spec is None:
        return list(default or [])
    if isinstance(spec, list):
        return [int(x) for x in spec]
    out = []
    for part in str(spec).split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-")
            out += list(range(int(a), int(b) + 1))
        elif part:
            out.append(int(part))
    return out
