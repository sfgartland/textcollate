from textcollate import layout, marks
from textcollate.model import Line, PageData


def page(label, rows, x1=400):
    """rows: (indent, text) with 20pt line pitch"""
    return PageData(label, [Line(t, 50 + ind, x1 if not t.endswith("|") else 250, 100 + 20 * i, 10) for i, (ind, t) in enumerate(rows)])


def test_indent_paragraphs_hyphens_and_page_marks():
    p1 = page("7", [(0, "Erste Zeile des Absatzes mit ver-"), (0, "bundenen Worten und mehr."),
                    (20, "Zweiter Absatz beginnt hier und geht"), (0, "weiter mit dem Wort Be-")])
    p2 = page("8", [(0, "denken wir das weiter."), (20, "Dritter Absatz.")])
    paras, notes, titles = layout.from_lines([p1, p2], {"paragraphs": "indent"}, "ed", layout.Lexicon())
    assert len(paras) == 3
    assert "verbundenen" in marks.strip(paras[0])
    assert "Bedenken" in marks.strip(paras[1])
    # the mark of page 8 sits inside the word Be|denken
    assert list(marks.iter_marks(paras[1], "ed"))[-1][3] == "w"
    assert [m[2] for m in marks.iter_marks(paras[0], "ed")] == ["7"]


def test_lexicon_keeps_real_hyphen():
    lex = layout.Lexicon({"warm", "hearted"}, keep={"warm-hearted"})
    assert lex.join("warm", "hearted") == "warm-hearted"
    assert layout.Lexicon().join("hun", "dredth") == "hundredth"
    en = layout.Lexicon({"hundredth"}, mode="lexicon")
    assert en.join("hun", "dredth") == "hundredth" and en.join("life", "giving") == "life-giving"


def test_footnotes_and_furniture_are_split_off():
    lines = [Line("MEMORIAL ADDRESS 45", 50, 300, 10, 8)] + [Line(f"Body text line {i}.", 50, 400, 100 + 20 * i, 12) for i in range(1, 7)] + \
            [Line("1. A footnote (Tr.)", 50, 300, 500, 8), Line("45", 200, 210, 560, 8)]
    body, notes, _ = layout.split_page(PageData("45", lines), {"furniture": [r"MEMORIAL ADDRESS \d+"], "notes": {"frac": 0.7, "height_ratio": 0.85}})
    assert [l.text for l in body] == [f"Body text line {i}." for i in range(1, 7)]
    assert [l.text for l in notes] == ["1. A footnote (Tr.)"]
