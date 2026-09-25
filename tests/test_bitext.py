from textcollate import bitext, marks
from textcollate.model import Edition


def test_sentences_skip_abbreviations():
    s = bitext.sentences("Er sagte es, d. h. er wusste es. Dann ging er. Wir sahen ed. Altwegg III, 314. Ende.")
    assert len(s) == 4


def test_align_blocks_and_transfer():
    de = Edition("de", "de", "de", [
        "Das erste Wort ist ein Wort des Dankes. Wir danken der Heimat.",
        "Der Boden der Heimat " + marks.mark("ga", "518") + "hat große Dichter hervorgebracht. Kreutzer war einer davon.",
        "Ende von 1955."])
    en = Edition("en", "en", "en", [
        "The first word is a word of thanks. We thank our homeland.",
        "The soil of the homeland has brought forth great poets. Kreutzer was one of them.",
        "End of 1955."])
    par = bitext.align(de, en, marks_from=["ga"])
    assert [(len(b.left), len(b.right)) for b in par.blocks] == [(1, 1), (1, 1), (1, 1)]
    right = par.blocks[1].right[0]
    assert marks.strip(right).startswith("The soil")
    (off, ed_, label, flags), = list(marks.iter_marks(right, "ga"))
    assert label == "518" and "a" in flags                       # mid-sentence -> approximate
    assert 5 < off < 40


def test_paragraph_merge_shapes():
    de = Edition("de", "de", "de", ["Kurz eins.", "Kurz zwei folgt.", "Ein längerer dritter Absatz mit vielen Worten hier."])
    en = Edition("en", "en", "en", ["Short one. Short two follows.", "A longer third paragraph with many words here."])
    par = bitext.align(de, en)
    assert [(len(b.left), len(b.right)) for b in par.blocks] == [(2, 1), (1, 1)]
