from textcollate import marks


def test_roundtrip_and_strip():
    t = "Das " + marks.mark("ga", "517") + "Wort" + marks.mark("ga", "518", "w") + "e " + marks.note("1") + "Ende"
    clean, mk = marks.parse(t)
    assert clean == "Das Worte Ende"
    assert marks.rebuild(clean, mk) == t
    assert marks.strip(t) == clean
    assert [(o, e, l, f) for o, e, l, f in marks.iter_marks(t)] == [(4, "ga", "517", ""), (8, "ga", "518", "w")]


def test_add_and_drop():
    t = marks.add_mark_at("abc def", 4, marks.mark("x", "1"))
    assert marks.parse(t)[0] == "abc def" and "x|1" in t
    assert marks.drop_marks(t, "x") == "abc def"


def test_decode():
    assert marks.decode(marks.mark("e", "4", "a")) == ("M", ["e", "4", "a"])
    assert marks.decode(marks.BR) == ("BR", [])
