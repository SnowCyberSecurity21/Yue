"""Yue'ga xos qoidalar: munosabat yo'q, romantika yo'q, Nora bilan yonma-yon ishlaydi."""

import json
import random
import re

import pytest

from tests.test_i18n import controller  # noqa: F401 — fixture
from yue import APP_ID, paths
from yue.ai import prompt
from yue.ai.parse import EXPRESSIONS, parse_reply
from yue.commands import Commands
from yue.i18n import STRINGS, t
from yue.lines import Lines
from yue.pet.physics import Seg

ROOT = paths.RES
PERSONA_FILES = ("persona_uz.txt", "persona_qisqa_uz.txt", "summarizer_uz.txt")
ROMANTIC = re.compile(
    r"(?<![\w'])(jonim|azizim|sevgilim|yuragim|sevaman|sevgi\w*|o'pich\w*|o'pay\w*|quchoq\w*|noz)"
    r"(?![\w'])",
    re.I,
)
NORA = re.compile(r"\bnora", re.I)
# Nora'ning nomlari (C:\nora dan) — Yue'niki ulardan farq qilishi kerak
NORA_APP_ID = "{{6E0F7A51-2C4B-4C7B-9C0E-6B1D2F7A9A01}"
NORA_RUN_NAME = "Nora"
NORA_LOCK = "nora.lock"
NORA_SERVER_PREFIX = "nora-ctl-"
NORA_HOTKEY_IDS = {0x4E4F, 0x4E59, 0x4E4D}


class _ZeroRandom(random.Random):
    def random(self):
        return 0.0


def _said(c, monkeypatch):
    said = []
    monkeypatch.setattr(c, "say_text", lambda e, txt, **kw: said.append((e, txt)))
    monkeypatch.setattr(c, "say", lambda e, txt: said.append((e, txt)))
    return said


def _content_texts() -> dict[str, str]:
    """Foydalanuvchiga ko'rinadigan matnlar: iboralar, persona, i18n, harakatlar."""
    out = {
        "iboralar.json": "\n".join(Lines.load().all_texts()),
        "harakatlar.json": (paths.PERSONA_DIR / "harakatlar.json").read_text(encoding="utf-8"),
        "i18n": "\n".join(str(v) for v in STRINGS.values()),
    }
    for name in PERSONA_FILES:
        out[name] = (paths.PERSONA_DIR / name).read_text(encoding="utf-8")
    return out


# --- matnlar ------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["iboralar.json", "harakatlar.json", "i18n", *PERSONA_FILES])
def test_no_nora_and_no_romance_in_texts(name):
    text = _content_texts()[name]
    assert not NORA.search(text), NORA.findall(text)
    assert not ROMANTIC.findall(text), ROMANTIC.findall(text)


def test_romantic_regex_sanity():
    for bad in ("Salom, jonim", "Azizim!", "sevgi haqida", "quchoqlab", "noz qilma", "o'pay"):
        assert ROMANTIC.search(bad), bad
    for ok in ("Sevimli choyim", "nozik masala", "yaqin do'st", "o'pish"):
        assert not ROMANTIC.search(ok), ok


def _repo_files():
    skip = {".git", ".venv", "dist", "__pycache__", ".pytest_cache", ".ruff_cache", "docs"}
    for path in ROOT.rglob("*"):
        if set(path.relative_to(ROOT).parts) & skip or not path.is_file():
            continue
        if path.relative_to(ROOT).parts[0] == "build" and path.suffix not in (
            ".spec",
            ".iss",
            ".txt",
        ):
            continue
        if path.suffix in (".py", ".pyw", ".json", ".txt", ".toml", ".spec", ".iss", ".md", ".svg"):
            yield path


def test_no_personal_details_anywhere():
    nick = "Snow" + "me"  # bu fayl o'zini topib olmasin
    home = "C:\\" + "Users\\"
    for path in _repo_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        assert nick.lower() not in text.lower(), path
        assert home.lower() not in text.lower(), path
        assert not re.search(r"[\w.+-]+@(gmail|mail|yandex|outlook)\.", text), path
    talaffuz = json.loads((paths.PERSONA_DIR / "talaffuz.json").read_text(encoding="utf-8"))
    assert talaffuz.get("Yue") == "Yu-e"


def test_removed_relation_files():
    for rel in ("yue/lock.py", "yue/ui/relation.py", "persona/hissiyot.json"):
        assert not (ROOT / rel).exists(), rel
    lines = Lines.load()
    for key in ("yaqin", "munosabat", "yaqinlik_daraja", "yaqinlik_sana"):
        assert key not in lines.data, key
    assert not lines.has("kayfiyat", "sogingan") and not lines.has("kayfiyat", "arazlagan")
    assert not lines.has("harakat", "raqs_rad")
    for key in STRINGS:
        assert not key.startswith(("maxfiy.", "memory.bond.")), key
    assert "settings.tab.maxfiy" not in STRINGS and "expr.love" not in STRINGS


# --- iboralar.json ------------------------------------------------------------------------------

MIN_LINES = {
    "listen": 8, "thinking": 6, "drag": 8, "thrown": 6, "wake": 6, "pat": 10, "welcome_back": 8,
    "goodbye": 6, "break": 8, "task_remind": 5, "task_added": 5, "task_done": 6, "tasks_empty": 4,
    "hazil": 45, "mehr": 25, "taklif": 6, "offline_taklif": 2, "ollama_ishlamayapti": 2,
}  # fmt: skip
MIN_SUB = {("kayfiyat", s): 5 for s in ("xavotirda", "gururli", "charchagan")} | {
    ("manba", "online"): 2, ("manba", "offline"): 2, ("ovoz", "chegara"): 2,
    ("harakat", "raqs"): 3, ("harakat", "uyal"): 1,
}  # fmt: skip


def _entries(node):
    if isinstance(node, dict):
        for k, v in node.items():
            if not str(k).startswith("_"):
                yield from _entries(v)
    elif isinstance(node, list):
        yield from node


def test_iboralar_schema_and_minimums():
    lines = Lines.load()
    for entry in _entries({k: v for k, v in lines.data.items() if k != "about"}):
        assert isinstance(entry, list) and len(entry) == 2, entry
        assert entry[0] in EXPRESSIONS, entry  # "love" yo'q
        assert isinstance(entry[1], str) and entry[1].strip(), entry
    texts = lines.all_texts()
    assert len(texts) == len(set(texts)), [x for x in texts if texts.count(x) > 1]
    for period in ("morning", "day", "evening", "night"):
        assert len(lines.options("greet", period)) >= 6, period
        assert len(lines.options("idle", period)) >= 15, period
    for key, n in MIN_LINES.items():
        assert len(lines.options(key)) >= n, key
    for (key, sub), n in MIN_SUB.items():
        assert len(lines.options(key, sub)) >= n, (key, sub)


def test_iboralar_quality():
    lines = Lines.load()
    texts = [x for x in lines.all_texts() if x != lines.data["about"]]
    assert all(len(x) <= 140 for x in texts), [x for x in texts if len(x) > 140]
    fillers = [x for x in texts if re.search(r"(hihi|pff|hmf)", x, re.I)]
    assert len(fillers) <= len(texts) // 10
    assert len(lines.options("pat")) == 10 and len(lines.options("welcome_back")) == 8
    assert any("mushuk emasman" in x for _, x in lines.options("pat"))
    clingy = re.compile(
        r"kutayotgan edim|sizni kutdim|sog'indim|tashlab ketdingiz|kechirim so'ra", re.I
    )
    assert not [x for x in texts if clingy.search(x)]


def test_last_five_not_repeated():
    lines = Lines.load()
    lines.rng = random.Random(3)
    picked = [lines.pick("pat")[1] for _ in range(200)]
    for i in range(5, len(picked)):
        assert picked[i] not in picked[i - 5 : i]


def test_placeholders_kept():
    lines = Lines.load()
    for _, x in lines.options("task_remind"):
        assert "{count}" in x and "{list}" in x
    for key in ("task_added", "task_done"):
        assert all("{task}" in x for _, x in lines.options(key))


# --- harakatlar va AI teglari -------------------------------------------------------------------


def test_actions_match_persona_list():
    cmds = Commands.load()
    names = {n for n in cmds.names if not cmds.specs[n].no_ai}  # "hazil" — AI tegi emas
    assert not set(cmds.names) & {"o_pish", "bagirga_bosil", "erka"}
    assert {"uyal", "raqs"} <= names
    persona = (paths.PERSONA_DIR / "persona_uz.txt").read_text(encoding="utf-8")
    listed = persona.split("- Nomlar:\n", 1)[1].split("\n", 1)[0]
    in_persona = {m.split(" — ")[0].strip() for m in listed.split(";")}
    assert in_persona == names
    short = (paths.PERSONA_DIR / "persona_qisqa_uz.txt").read_text(encoding="utf-8")
    assert set(re.findall(r"<harakat>(\w+)</harakat>", short)) == names


@pytest.mark.parametrize("tag", ["o_pish", "bagirga_bosil", "erka"])
def test_ai_romantic_actions_ignored(tag):
    reply = parse_reply(f"[happy] Yo'q. <harakat>{tag}</harakat>")
    assert reply.command is None and reply.text == "Yo'q."


def test_ai_love_expression_becomes_happy():
    assert "love" not in EXPRESSIONS
    reply = parse_reply("[love] Salom! [love] Qalay?")
    assert reply.expression == "happy" and reply.tagged
    assert reply.text == "Salom! Qalay?"


def test_ai_romantic_action_does_nothing_in_app(controller, monkeypatch):  # noqa: F811
    c = controller
    for name in ("o_pish", "bagirga_bosil", "erka"):
        assert c.run_command(name, source="ai") == "missing"


def test_pack_has_no_love_expression():
    raw = json.loads((paths.DEFAULT_PACK / "pack.json").read_text(encoding="utf-8"))
    assert raw["name"] == "Yue" and "love" not in raw["expression_map"]
    for tags in raw["expression_map"].values():
        assert "love" not in tags
    assert (paths.DEFAULT_PACK / "yue.ico").is_file()
    assert not (paths.DEFAULT_PACK / "nora.ico").exists()


def test_love_tag_never_shows_love_frame(controller):  # noqa: F811
    bh = controller.behavior
    assert not bh.expression_available("love")
    assert bh.expression_available("happy")


# --- silash, raqs, hazil -------------------------------------------------------------------------


def test_pat_is_teasing_not_affection(controller, monkeypatch):  # noqa: F811
    c = controller
    said = _said(c, monkeypatch)
    for _ in range(20):
        c.pat()
    assert len(said) == 20
    pat = {x for _, x in c.lines.options("pat")}
    for expr, text in said:
        assert expr in ("neutral", "smug"), (expr, text)  # neutral — grumpy kadri
        assert text in pat
    assert ("neutral", "Men mushuk emasman!") in c.lines.options("pat")


def test_dance_works_for_everyone(controller, monkeypatch, qtbot):  # noqa: F811
    import yue.app

    c = controller
    c.behavior.body.land(Seg(0, 1920, 1040), None)  # yerda turibdi
    monkeypatch.setattr(yue.app, "DANCE_STEPS", tuple((s, 0.01) for s, _ in yue.app.DANCE_STEPS))
    played = []
    monkeypatch.setattr(c.behavior, "play", lambda now, slot, secs=None: played.append(slot))
    said = _said(c, monkeypatch)
    assert c.run_command("raqs", source="menu") == "ok"
    expected = [s for s, _ in yue.app.DANCE_STEPS if c.wardrobe.has(s)]
    qtbot.waitUntil(lambda: played == expected)
    assert said and said[0][1] in [x for _, x in c.lines.options("harakat", "raqs")]


def test_joke_command_is_answered_without_ai(controller, monkeypatch):  # noqa: F811
    c = controller
    calls = []
    monkeypatch.setattr(c.brain, "ask", lambda text, enqueue=True: calls.append(text) or True)
    said = _said(c, monkeypatch)
    for text in ("hazil ayt", "Latifa ayt!", "kuldir"):
        c.on_submit(text)
    assert calls == [] and len(said) == 3
    assert all(x in [y for _, y in c.lines.options("hazil")] for _, x in said)


@pytest.mark.parametrize("text", ["/yaqin", "/maxfiy", "/oddiy", "yaqin rejim"])
def test_relation_keywords_go_to_ai(controller, monkeypatch, text):  # noqa: F811
    """Munosabat kalit so'zlari yo'q: oddiy xabar sifatida AI'ga ketadi."""
    c = controller
    calls = []
    monkeypatch.setattr(c.brain, "has_ai", lambda: True)
    monkeypatch.setattr(c.brain, "ask", lambda tx, enqueue=True: calls.append(tx) or True)
    c.on_submit(text)
    assert calls == [text]


# --- eslatmalar ---------------------------------------------------------------------------------


def test_reminders_work(controller, monkeypatch):  # noqa: F811
    import datetime as dt

    from yue.platform.base import Battery

    c = controller
    said = []
    c.brain.say.connect(lambda e, txt: said.append(txt))
    # vazifa eslatmasi (fixture'da bitta vazifa bor) va muddati o'tgan vazifa
    c.brain.remind_open_tasks(force=True)
    assert said and "Dori ichish" in said[-1]
    c.brain.book.add("Suv ichish", "2020-01-01 09:00")
    n = len(said)
    c.brain.check_tasks()
    assert len(said) > n
    # tanaffus
    monkeypatch.setattr(c.brain.break_tracker, "update", lambda now, idle: 2.0)
    monkeypatch.setattr(c.platform, "battery", lambda: None)
    n = len(said)
    c.brain.check_minute()
    assert len(said) == n + 1
    # batareya
    monkeypatch.setattr(c.brain.break_tracker, "update", lambda now, idle: None)
    monkeypatch.setattr(c.platform, "battery", lambda: Battery(percent=8, plugged=False))
    monkeypatch.setattr(c.brain.battery, "update", lambda b: "critical")
    n = len(said)
    c.brain.check_minute()
    assert len(said) == n + 1 and "8%" in said[-1]
    # uyqu: tun yarmida faol bo'lsa — xavotirda kayfiyati va "yoting" iborasi
    late = dt.datetime(2026, 10, 15, 2, 0)
    assert c.brain.mood.current(late, active=True) == "xavotirda"
    monkeypatch.setattr(c.brain, "current_mood", lambda: "xavotirda")
    line = c.chatter_line(_ZeroRandom())  # kayfiyat iborasi ulushiga tushadi
    assert line in c.lines.options("kayfiyat", "xavotirda")


# --- prompt -------------------------------------------------------------------------------------


def test_prompt_has_no_relation(controller):  # noqa: F811
    ctx = controller.brain.prompt_context()
    blocks, _ = prompt.build(ctx, "salom", private=True)
    text = "\n".join(b.text for b in blocks)
    for word in ("Munosabat:", "Yaqinlik:", "[Yaqin muloqot]", "Laqabi:", "Bugun: tanish"):
        assert word not in text, word
    assert "Sen — Yue" in blocks[0].text


# --- ma'lumotlar papkasi va Nora bilan yonma-yon -------------------------------------------------


def test_data_dir_is_appdata_yue(monkeypatch, tmp_path):
    monkeypatch.delenv("YUE_DATA", raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    assert paths.data_dir() == tmp_path / "Roaming" / "Yue"
    assert paths.db_path().name == "yue.db"
    monkeypatch.setenv("YUE_DATA", str(tmp_path / "boshqa"))
    assert paths.data_dir() == tmp_path / "boshqa"
    monkeypatch.setenv("NORA_DATA", str(tmp_path / "nora"))  # Nora o'zgaruvchisi ta'sir qilmaydi
    assert paths.data_dir() == tmp_path / "boshqa"


def test_names_differ_from_nora(monkeypatch, tmp_path):
    import yue.app
    from yue import ctl
    from yue.platform import windows

    monkeypatch.setenv("YUE_DATA", str(tmp_path))
    assert ctl.lock_path().name != NORA_LOCK and ctl.lock_path().name == "yue.lock"
    assert not ctl.server_name().startswith(NORA_SERVER_PREFIX)
    assert ctl.server_name().startswith("yue-ctl-")
    assert windows.RUN_NAME == "Yue" != NORA_RUN_NAME
    iss = (ROOT / "build" / "yue.iss").read_text(encoding="utf-8")
    app_id = re.search(r"^AppId=(\S+)", iss, re.M).group(1)
    assert app_id != NORA_APP_ID and re.fullmatch(r"\{\{[0-9A-F-]{36}\}", app_id)
    assert 'ValueName: "Yue"' in iss and "DefaultDirName={localappdata}\\Programs\\Yue" in iss
    assert f'#define AppUserModelID "{APP_ID}"' in iss and "nora" not in APP_ID.lower()
    assert {yue.app.HOTKEY_ID, yue.app.HOTKEY_VOICE_ID}.isdisjoint(NORA_HOTKEY_IDS)
    assert yue.app.HOTKEY_ID != yue.app.HOTKEY_VOICE_ID


# --- tezkor tugmalar ----------------------------------------------------------------------------


class _ComboPlatform:
    """Ro'yxatdan o'tgan birikmalarni eslab qoladigan soxta platforma (band — `busy` da)."""

    def __init__(self, busy=()):
        self.busy = set(busy)
        self.active: dict[int, str] = {}

    def register_combo(self, handle, hotkey_id, combo):
        text = combo.portable()
        if text in self.busy or text in self.active.values():
            return False
        self.active[hotkey_id] = text
        return True

    def unregister_hotkey(self, handle, hotkey_id):
        self.active.pop(hotkey_id, None)


def test_default_hotkeys_and_rebinding(controller, monkeypatch):  # noqa: F811
    import yue.app
    from yue import hotkey

    c = controller
    assert hotkey.DEFAULT_TOGGLE == "Ctrl+Alt+Y" and hotkey.DEFAULT_VOICE == "Ctrl+Alt+Shift+U"
    assert c.cfg.get("pet.hotkey") == "Ctrl+Alt+Y"
    assert c.cfg.get("voice.hotkey") == "Ctrl+Alt+Shift+U"
    fake = _ComboPlatform(busy={"Ctrl+Alt+N"})
    monkeypatch.setattr(c.platform, "register_combo", fake.register_combo)
    monkeypatch.setattr(c.platform, "unregister_hotkey", fake.unregister_hotkey)
    c.toggle_hotkey, c.hotkey_ok = c._register_saved(yue.app.HOTKEY_ID, "pet.hotkey", "")
    assert (c.toggle_hotkey, c.hotkey_ok) == ("Ctrl+Alt+Y", True)
    assert c.set_toggle_hotkey("Ctrl+Alt+N") == "busy"  # band: eskisi qoladi
    assert c.toggle_hotkey == "Ctrl+Alt+Y" and c.hotkey_ok
    assert fake.active[yue.app.HOTKEY_ID] == "Ctrl+Alt+Y"
    assert c.set_toggle_hotkey("Y") == "invalid"
    assert c.set_toggle_hotkey("Ctrl+Alt+K") == "ok"
    assert (
        c.cfg.get("pet.hotkey") == "Ctrl+Alt+K" and fake.active[yue.app.HOTKEY_ID] == "Ctrl+Alt+K"
    )


def test_busy_hotkey_shown_in_settings(controller):  # noqa: F811
    from yue.ui.settings import SettingsDialog

    c = controller  # NullPlatform: hech narsa ro'yxatdan o'tmaydi — "band"
    dlg = SettingsDialog(c, "general")
    assert dlg.g_hotkey_status.text() == t("general.hotkey.busy")
    assert dlg.g_hotkey.keySequence().toString() == "Ctrl+Alt+Y"


def test_settings_tabs_scroll_and_fit_screen(controller):  # noqa: F811
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QScrollArea

    from yue.ui.settings import SettingsDialog

    dlg = SettingsDialog(controller)
    labels = [dlg.tabs.tabText(i) for i in range(dlg.tabs.count())]
    assert labels.count(t("settings.tab.privacy")) == 1 and t("settings.tab.privacy") == "Xotira"
    assert "Maxfiy" not in labels
    for i in range(dlg.tabs.count()):
        w = dlg.tabs.widget(i)
        assert isinstance(w, QScrollArea) and w.widgetResizable()
        assert w.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    screen = dlg.screen().availableGeometry()
    assert dlg.height() <= int(screen.height() * 0.85) + 1
