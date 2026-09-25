from textcollate import editions, layout, marks, render
from textcollate.bitext import Block, Parallel
from textcollate.model import Edition, Line, PageData
from textcollate.sources import pdftext


def W(text, x0, x1):
    return (text, float(x0), float(x1))


def test_despace_joins_letterspaced_words():
    letters = [W(c, 10 + 6 * i, 14 + 6 * i) for i, c in enumerate("Fragen")]           # F r a g e n (gap 2)
    second = [W(c, 60 + 6 * i, 64 + 6 * i) for i, c in enumerate("und")]                # wider gap before: new word
    out = pdftext.despace([W("Die", 0, 8)] + letters + second)
    assert [w[0] for w in out] == ["Die", "Fragen", "und"]


def test_margin_numbers_become_marks_of_another_edition():
    body = [Line(f"Dies ist Zeile {i} des Textes hier", 50, 400, 100 + 20 * i, 10) for i in range(5)]
    margin = Line("12", 430, 445, 141, 8)
    keep, marg = pdftext._split_margin(body + [margin], {"regex": r"\d{1,3}"})
    assert len(keep) == 5 and marg == [(141, "12")]
    pg = PageData("7", keep, margin=marg)
    paras, _, _ = layout.from_lines([pg], {"paragraphs": "indent"}, "ga", layout.Lexicon(), margin_edition="va")
    assert [m[2] for m in marks.iter_marks(paras[0], "va")] == ["12"]


def test_margin_sequence_repairs_ocr_misreads():
    pages = [PageData(str(i), [Line("Zeile eins des Textes hier", 50, 400, 100, 10)], margin=[(99, lab)]) for i, lab in enumerate(["29", "50", "31"])]
    layout.REPAIRS.clear()
    paras, _, _ = layout.from_lines(pages, {"paragraphs": "indent"}, "ga", layout.Lexicon(), margin_edition="va", margin_sequence=True)
    assert [m[2] for m in marks.iter_marks(" ".join(paras), "va")] == ["29", "30", "31"] and layout.REPAIRS


def test_line_numbers_and_note_start():
    lines = [Line(f"{5 * (i + 1) if i % 2 else ''} Text der Zeile {i} hier steht".strip(), 260, 1480, 100 + 50 * i, 30,
                  ([W(str(5 * (i + 1)), 220, 245)] if i % 2 else []) + [W(t, 260 + 60 * k, 300 + 60 * k) for k, t in enumerate(f"Text der Zeile {i} hier steht".split())])
             for i in range(8)] + [Line("1) <Vgl. Beilage I.>", 292, 579, 560, 25, [W("1)", 292, 300), W("<Vgl.", 310, 350)])]
    body, notes, _ = layout.split_page(PageData("20", lines), {"line_numbers": {"step": 5, "max": 45}, "notes": {"start_re": r"^\d{1,2}\)\s", "min_frac": 0.6}})
    assert len(body) == 8 and all(not l.text[0].isdigit() for l in body)
    assert [l.text for l in notes] == ["1) <Vgl. Beilage I.>"]


def test_note_marker_lines():
    lines = [Line("Der Mensch " + "Wort " * 6, 50, 400, 50 + 15 * i, 11) for i in range(10)] + \
            [Line("b", 426, 430, 500, 7.5), Line("oder jetzt die maßgebende Weise", 431, 600, 501, 11.6)]
    body, notes, _ = layout.split_page(PageData("5", lines), {"notes": {"marker_lines": True}})
    assert len(body) == 10 and [l.text for l in notes] == ["b", "oder jetzt die maßgebende Weise"]


def test_page_scoped_notes_and_markers():
    ed = {"layout": {"note_scope": "page", "note_split": r"(?:^|(?<=\s))(\d{1,2}\.)\s+(?=[A-Z])"}}
    notes = editions._note_texts({"4": "2. A note on four.", "5": "1. A note on five. Continues here"}, ed)
    assert notes == {"4:2": "A note on four.", "5:1": "A note on five. Continues here"}
    paras = [marks.mark("e", "4") + "Text one,2 more." + marks.mark("e", "5") + " Text two.1"]
    out = editions._glued_note_markers(paras, r"(?<=[A-Za-z.,])(\d)(?=\s|$)", notes, None, "e")
    assert "N|4:2" in out[0] and "N|5:1" in out[0] and "one,2" not in marks.strip(out[0])


def test_concordance_of_the_left_edition_itself():
    left = Edition("de", "DE", "de", [])
    right = Edition("en", "EN", "en", [])
    par = Parallel("de", "en", [Block([marks.mark("de", "7") + "a " + marks.mark("de", "8") + "b"],
                                      [marks.mark("en", "50") + "x " + marks.mark("de", "8", "a") + "y"])])
    assert render.concordance(par, left, right, "de") == [("7", "7", ""), ("8", "8", "50≈")]
