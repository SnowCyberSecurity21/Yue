"""Iboralardagi {ism}: ism bilan to'ldirish, ismsiz olib tashlash; "taklif" bo'limi."""

import random
import re

from tests.test_i18n import controller  # noqa: F401 — fixture
from yue.lines import NAME, Lines, fill_name


def test_fill_name_with_name():
    assert fill_name("Xayrli tong, {ism}! Bugun", "Akmal") == "Xayrli tong, Akmal! Bugun"
    assert fill_name("Ana, {ism} keldi!", "Akmal") == "Ana, Akmal keldi!"
    assert fill_name("Ismsiz gap.", "") == "Ismsiz gap."


def test_fill_name_without_name_removes_parts():
    assert fill_name("{ism}, suv ichdingizmi? Rostini ayting.", "") == (
        "Suv ichdingizmi? Rostini ayting."
    )
    assert fill_name("{ism}! Keldingizmi? Kutayotgan edim.", "") == "Keldingizmi? Kutayotgan edim."
    assert (
        fill_name("Xayrli tong, {ism}! Bugun ajoyib kun.", "") == "Xayrli tong! Bugun ajoyib kun."
    )
    assert fill_name("Rahmat, {ism}.", "") == "Rahmat."
    assert fill_name("Ana, {ism} keldi!", "") is None  # ismsiz aytib bo'lmaydi


def _lines(name):
    lines = Lines.load()
    lines.rng = random.Random(7)
    lines.name_fn = lambda: name
    return lines


def test_pick_fills_name():
    lines = _lines("Akmal")
    got = {lines.pick("welcome_back")[1] for _ in range(400)}
    assert "Ana, Akmal keldi! Qalay, hammasi joyidami?" in got
    assert not any(NAME in x for x in got)


def test_pick_without_name_never_leaves_placeholder():
    lines = _lines("")
    for key, sub in (("welcome_back", None), ("mehr", None), ("taklif", None), ("greet", "day")):
        for _ in range(1000):
            text = lines.pick(key, sub)[1]
            assert NAME not in text and not text.startswith(("Ana, ", ", ", "! ")), text
            assert text[:1] == text[:1].upper(), text


def test_every_name_line_is_sayable():
    """Har {ism} li gap ism bilan ham, ismsiz ham (yoki tanlanmaydi) to'g'ri chiqadi."""
    lines = Lines.load()
    with_name = [x for x in lines.all_texts() if NAME in x]
    assert len(with_name) >= 8
    for x in with_name:
        assert re.sub(r"\{ism\}", "", x).count("{") == 0, x  # boshqa o'zgaruvchi yo'q
        assert NAME not in fill_name(x, "Akmal")
        out = fill_name(x, "")
        assert out is None or (NAME not in out and out[:1].isupper()), x


def test_taklif_said_unprompted(controller):  # noqa: F811
    c = controller
    rng = random.Random(3)
    taklif = {x for _, x in c.lines.options("taklif")}
    got = {c.chatter_line(rng)[1] for _ in range(600)}
    assert got & {fill_name(x, "") for x in taklif}


def test_fill_name_mid_text_sentence_start():
    assert fill_name("Salom! {ism}, qalay?", "") == "Salom! Qalay?"
