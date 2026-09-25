import textwrap
from pathlib import Path

import pytest


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """a tiny project: a clean transcription (pages 1-2), a noisy edition with other pagination, and a translation"""
    (tmp_path / "clean.txt").write_text(
        "Das erste Wort ist ein Wort des Dankes. Wir danken der Heimat.\n\n"
        "Aus dem Werk erklingen Lied und Chor, Oper und Kammermusik. Die Gegenwart des Meisters ist die einzig echte. Wir sollen denken und\f"
        "sagen? Zeichnet sich die Musik nicht aus? Man sagt es.\n\n"
        "Doch bleibt die Frage bestehen. Der Boden der Heimat hat große Dichter hervorgebracht. Be\f"
        "denken wir dies weiter, dann zeigt sich vieles. Wir sind Pflanzen.\n", encoding="utf-8")
    (tmp_path / "noisy.txt").write_text(
        "Das erste Wort ist ein Wort des Dankes.\n\n"
        "Wir danken der Heimat. Aus dem Werk erldingen Lied und Chor, Oper und Kammermusik. Die Gegenwart des Meisters\f"
        "ist die einzig echte. Wir sollen denken und sagen? Zeichnet sich die Musik nicht aus? Man sagt es.\n\n"
        "Doch bleibt die Frage bestehen.\n\n"
        "Der Boden der Heimat hat große Dichter hervorgebracht. Bedenken wir dies weiter, dann zeigt sich vieles. Wir sind Pflanzen.\n",
        encoding="utf-8")
    (tmp_path / "en.txt").write_text(
        "The first word is a word of thanks. We thank our homeland.\n\n"
        "From the work ring forth song and chorus, opera and chamber music. The presence of the master is the only true one. "
        "We are to think and to say? Is it not the distinction of music? So they say.\n\n"
        "Yet the question remains. The soil of the homeland has brought forth great poets.\n\n"
        "Thinking about this further, much becomes clear. We are plants.\n", encoding="utf-8")
    (tmp_path / "textcollate.toml").write_text(textwrap.dedent('''
        [project]
        name = "toy"
        [[edition]]
        id = "clean"
        label = "Clean"
        language = "de"
        [edition.source]
        type = "text"
        path = "clean.txt"
        [edition.pages]
        first = 1
        [edition.mark_style]
        label = "C"
        color = "8B1E1E"
        bold = true
        [[edition]]
        id = "noisy"
        label = "Noisy"
        language = "de"
        [edition.source]
        type = "text"
        path = "noisy.txt"
        trust = 0.5
        [edition.pages]
        first = 10
        [[edition]]
        id = "en"
        label = "English"
        language = "en"
        [edition.source]
        type = "text"
        path = "en.txt"
        [edition.pages]
        first = 100
        [[output]]
        id = "de-clean"
        kind = "single"
        edition = "noisy"
        marks = ["noisy", "clean"]
        [output.collate]
        refs = ["clean"]
        paragraph_starts = ["clean"]
        marks_from = ["clean"]
        [[output]]
        id = "de-en"
        kind = "parallel"
        left = "noisy"
        right = "en"
        marks = ["noisy", "en", "clean"]
        transfer = ["clean"]
        [output.left_collate]
        refs = ["clean"]
        paragraph_starts = ["clean"]
        marks_from = ["clean"]
    '''), encoding="utf-8")
    return tmp_path
