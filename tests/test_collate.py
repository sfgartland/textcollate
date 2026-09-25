from textcollate import collate, marks
from textcollate.model import Edition


def ed(id_, paras, trust=0.5, lang="de"):
    return Edition(id=id_, label=id_, language=lang, paragraphs=paras, trust={i: trust for i in range(len(paras))})


def test_repair_marks_and_paragraph_starts():
    ref = ed("ref", [marks.mark("ref", "1") + "Das Werk erklingen wir sollen denken. Der Boden der Heimat. Be" + marks.mark("ref", "2", "w") +
                     "denken wir dies weiter, dann zeigt sich vieles."], trust=1.0)
    ref.paragraphs = ["Das Werk erklingen wir sollen denken.", marks.mark("ref", "1") + "Der Boden der Heimat. Be " + marks.mark("ref", "2") +
                      " denken wir dies weiter, dann zeigt sich vieles."]
    ref = ed("ref", [ref.paragraphs[0], "Der Boden der Heimat " + marks.mark("ref", "2") + "denken wir dies weiter, dann zeigt sich vieles."], trust=1.0)
    target = ed("t", [marks.mark("t", "9") + "Das Werk erldingen wir sollen denken. Der Boden der Heimat. Bedenken wir dies weiter, dann zeigt sich vieles."])
    out, rep = collate.collate(target, [ref], paragraph_starts=["ref"], marks_from=["ref"])
    text = " ".join(out.paragraphs)
    assert "Erklingen" not in text and "erklingen" in marks.strip(text)                # OCR slip repaired
    assert len(out.paragraphs) == 2                                                      # paragraph start from the reference
    assert marks.strip(out.paragraphs[1]).startswith("Der Boden")
    marks_in = [(l, f) for _, e, l, f in marks.iter_marks(out.paragraphs[1], "ref")]
    assert marks_in == [("2", "")] or marks_in == [("2", "w")]
    assert any("erldingen -> erklingen" in x for x in rep.log)


def test_in_word_mark_transfer():
    ref = ed("ref", ["Wir sind Nach" + marks.mark("ref", "8", "w") + "denken, die totale Gedankenlosigkeit hier."], trust=1.0)
    target = ed("t", ["Wir sind Nachdenken, die totale Gedankenlosigkeit hier."])
    out, _ = collate.collate(target, [ref], marks_from=["ref"])
    assert marks.strip(out.paragraphs[0]) == "Wir sind Nachdenken, die totale Gedankenlosigkeit hier."
    assert list(marks.iter_marks(out.paragraphs[0], "ref"))[0][0] == len("Wir sind Nach")


def test_compare_classifies():
    a = ed("a", ["Der Mensch ist ein denkendes Wesen und wir alle wissen das."])
    b = ed("b", ["Der Mensch ist ein denkendes Wesen und wir alle wissen dass ganz genau nicht."])
    md, stats = collate.compare(a, b)
    assert stats["substantive"] >= 1 and "vs" in md
