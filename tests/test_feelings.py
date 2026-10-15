"""Kayfiyat qoidalari (soxta soat), [Holat] bloki va omborning sxemasi."""

import datetime as dt

import pytest

from tests.fakes import FakeClock
from yue.ai import prompt
from yue.feelings import MOODS, Mood, is_praise, is_success, mood_expression
from yue.memory.crypto import Cipher
from yue.memory.store import Store

DAY = dt.datetime(2026, 10, 13, 14, 0)  # kunduzi


def make_mood():
    clock = FakeClock()
    return Mood(clock=clock), clock


def test_default_mood_is_happy():
    m, _ = make_mood()
    assert m.current(DAY, active=True) == "xursand"
    assert mood_expression("xursand") is None


def test_no_attachment_moods():
    """Bog'lanib qolishga undaydigan kayfiyatlar yo'q."""
    assert "sog'ingan" not in MOODS and "arazlagan" not in MOODS
    assert set(MOODS) == {"xursand", "xavotirda", "uyalgan", "g'ururli", "charchagan"}
    m, _ = make_mood()
    assert not hasattr(m, "on_return") and not hasattr(m, "on_unprompted_line")


@pytest.mark.parametrize(
    ("hour", "active", "mood"),
    [(3, True, "xavotirda"), (0, True, "xavotirda"), (3, False, "charchagan"),
     (23, True, "charchagan"), (5, True, "charchagan"), (14, True, "xursand")],
)  # fmt: skip
def test_night_moods(hour, active, mood):
    m, _ = make_mood()
    assert m.current(DAY.replace(hour=hour), active=active) == mood


def test_praise_makes_shy_for_ten_minutes():
    m, clock = make_mood()
    m.on_user_message("Rahmat, zo'rsiz!")
    assert m.current(DAY, active=True) == "uyalgan"
    assert mood_expression("uyalgan") == "shy"
    clock.advance(10 * 60 + 1)
    assert m.current(DAY, active=True) == "xursand"
    for text in ("молодец", "Barakalla", "aqlli qizsan"):
        assert is_praise(text), text
    for text in ("zo'rg'a ulgurdim", "rejalarim bor", "bugun yomg'ir"):
        assert not is_praise(text), text


def test_success_makes_proud_for_thirty_minutes():
    m, clock = make_mood()
    m.on_user_message("Imtihondan o'tdim!")
    assert is_success("Kodni tuzatdim, ishladi") and not is_success("ishlamadi")
    assert m.current(DAY, active=True) == "g'ururli" and mood_expression("g'ururli") == "smug"
    clock.advance(30 * 60 + 1)
    assert m.current(DAY, active=True) == "xursand"


def test_shy_beats_proud():
    m, _ = make_mood()
    m.on_user_message("Uddaladim!")
    m.on_user_message("rahmat")
    assert m.current(DAY, active=True) == "uyalgan"


# --- [Holat] bloki ------------------------------------------------------------------------------


def test_state_block_has_mood_but_no_relation():
    ctx = prompt.PromptContext(now=DAY, mood="charchagan")
    blocks = prompt.build(ctx, "salom", private=True)[0]
    state = blocks[-1].text
    assert "Kayfiyat: charchagan." in state
    text = "\n".join(b.text for b in blocks)
    for word in ("Munosabat:", "Yaqinlik:", "[Yaqin muloqot]", "Laqabi:", "tanishganimizga"):
        assert word not in text, word


def test_prompt_context_has_no_relation_fields():
    fields = set(prompt.PromptContext.__dataclass_fields__)
    assert not fields & {"intimate", "closeness", "nickname", "days_known"}


# --- ombor ------------------------------------------------------------------------------------


def test_store_schema_has_no_bond(tmp_path):
    s = Store(tmp_path / "yue.db", Cipher(b"k" * 32))
    tables = {r[0] for r in s._q("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "bond" not in tables
    cols = {r[1] for r in s._q("PRAGMA table_info(messages)")}
    assert "intimate" not in cols
    s.add_message("user", "salom")
    s.add_message("assistant", "Salom!")
    assert s.recent_messages() == [("user", "salom"), ("assistant", "Salom!")]
    assert s.verify_key()
    s.close()


def test_summarizer_prompt_excludes_romance():
    assert "Romantik gaplarni" in prompt.summarizer_text()
