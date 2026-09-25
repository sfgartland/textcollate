import shutil

import pytest

from textcollate import cli, editions, marks
from textcollate.config import load


def test_config_and_extract(project):
    cfg = load(project)
    assert list(cfg.editions) == ["clean", "noisy", "en"]
    e = editions.build(cfg, "clean")
    assert [l for _, _, l, _ in marks.iter_marks(" ".join(e.paragraphs), "clean")] == ["1", "2", "3"]
    # the paragraph that runs across a page break was joined, with the mark inside it
    assert any("Be" in marks.strip(p) for p in e.paragraphs)


def test_build_without_pdf(project):
    assert cli.main(["build", "-c", str(project), "--no-pdf"]) == 0
    tex = (project / "build" / "out" / "de-clean.tex").read_text()
    assert "erklingen" in tex and "\\tcmB" in tex
    par = (project / "build" / "out" / "de-en.tex").read_text()
    assert "\\begin{paracol}{2}" in par and "\\switchcolumn" in par


@pytest.mark.skipif(shutil.which("lualatex") is None, reason="lualatex not installed")
def test_build_pdf(project):
    assert cli.main(["build", "-c", str(project), "de-en"]) == 0
    assert (project / "build" / "out" / "de-en.pdf").exists()


def test_compare_and_bib(project, capsys):
    assert cli.main(["compare", "-c", str(project), "clean", "noisy"]) == 0
    assert "->" in capsys.readouterr().out
    assert cli.main(["bib", "-c", str(project)]) == 0


def test_mark_at_and_italics(project):
    from textcollate import editions
    paras = editions.apply_mark_at(["Erster Satz. Zweiter Satz beginnt hier."], [{"edition": "ga", "label": 5, "before": "Zweiter"}])
    assert [(o, l) for o, _, l, _ in marks.iter_marks(paras[0], "ga")] == [(13, "5")]
    paras = editions.apply_italics(["Wir sind nicht allein."], [{"context": "sind nicht allein", "phrase": "nicht"}])
    assert marks.EM_ON in paras[0] and marks.strip(paras[0]) == "Wir sind nicht allein."


def test_markdown_ocr_adapter():
    from textcollate.sources.ocr import markdown_to_paragraphs
    paras = markdown_to_paragraphs("# Titel\n\nWir *denken* nicht **allein**, sondern _auch_ mehr.\nZweite Zeile.\n\n\nNeuer Absatz.")
    assert [marks.strip(p) for p in paras] == ["Titel", "Wir denken nicht allein, sondern auch mehr. Zweite Zeile.", "Neuer Absatz."]
    assert paras[1].count(marks.EM_ON) == 2 and paras[1].count(marks.EM_OFF) == 2
