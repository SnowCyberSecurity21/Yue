"""Mezon: interfeysda bitta ham inglizcha so'z yo'q (oq ro'yxatdagi atamalardan tashqari)."""

import ast
import re
from pathlib import Path

import pytest
from PySide6.QtWidgets import QAbstractButton, QLabel, QMenu, QWidget

from yue import paths
from yue.i18n import STRINGS, t
from yue.lines import Lines

# Nomlar, mahsulotlar va texnik atamalar — tarjima qilinmaydi
WHITELIST = {
    "yue", "claude", "gemini", "google", "anthropic", "ai", "api", "windows", "dpapi", "aes",
    "gcm", "haiku", "sonnet", "ctrl", "alt", "shift", "enter", "esc", "json", "n", "sha",
    "openrouter",
}  # fmt: skip

# Aniq inglizcha so'zlar (o'zbekcha so'zlar bilan to'qnashmaydiganlari)
ENGLISH = set(
    """the and you your is are this that with for from settings setting cancel save open close
    file help about exit quit yes error warning key keys test check show hide delete add edit
    name language memory task tasks sleep wake hello welcome next back finish apply ok copy
    paste cut undo redo select all send message limit quota retry later please loading success
    failed failure enabled disabled off auto manual size walk budget daily today minutes hours
    reminder reminders battery privacy general folder export import clear data user password
    token request response chat talk outfit glasses headphones hood remove remember forget
    week day night morning evening options usage version run start stop update new old
    wait busy offline online network unknown invalid wrong exceeded rate""".split()
)

URL_RE = re.compile(r"https?://\S+|\b[\w.-]+\.(com|org|net|uz)\b|\{[a-z_]+\}|\$\{?\w*\}?")
WORD_RE = re.compile(r"[A-Za-zʻʼ'’]+")


# CLI parametrlari, fayl yo'llari va chat buyruqlari ("/offline")
TECH_RE = re.compile(r"(?<!\w)--?[a-z][\w-]*|[A-Za-z]:\\\S*|(?<![\w/])/[a-z]+\b")
# UI matni emas: shrift nomi va log uchun ichki sabablar
ALLOWED_LITERALS = {"Segoe UI", "kalit ochilmadi", "kalit mos emas"}


# Bo'lim nomi (foydalanuvchi tanlagan atama); alohida "offline" so'zi baribir ushlanadi
TERMS_RE = re.compile(r"(?<![a-z])offline model[a-z']*", re.I)
# Rejim nomlari (foydalanuvchi tanlagan): faqat bosh harf bilan — "Online", "Offline"
MODE_NAMES_RE = re.compile(r"(?<![A-Za-z])(?:Online|Offline)(?![A-Za-z])")
# ElevenLabs saytidagi menyu yo'li ("ElevenLabs → Developers → …") — sayt tilida, aynan shunday
SITE_PATH_RE = re.compile(r"ElevenLabs →[^.]*[.]")


def english_words(text: str) -> set[str]:
    text = MODE_NAMES_RE.sub(" ", TERMS_RE.sub(" ", SITE_PATH_RE.sub(" ", text)))
    text = TECH_RE.sub(" ", URL_RE.sub(" ", text))
    words = {w.lower().strip("'’ʻʼ") for w in WORD_RE.findall(text)}
    return {w for w in words if w in ENGLISH and w not in WHITELIST}


@pytest.mark.parametrize("key", sorted(STRINGS))
def test_ui_strings_have_no_english(key):
    assert not english_words(STRINGS[key]), (key, STRINGS[key])


def test_canned_lines_have_no_english():
    bad = {txt: english_words(txt) for txt in Lines.load().all_texts() if english_words(txt)}
    assert not bad


def test_persona_files_are_uzbek():
    for name in ("persona_uz.txt", "summarizer_uz.txt"):
        text = (paths.PERSONA_DIR / name).read_text(encoding="utf-8")
        assert "o'zbek" in text.lower()


# --- UI kodida qattiq yozilgan matn yo'q ------------------------------------------------------

UI_MODULES = [
    *sorted((paths.RES / "yue" / "ui").glob("*.py")),
    paths.RES / "yue" / "app.py",
    paths.RES / "yue" / "core.py",
    paths.RES / "yue" / "pet" / "window.py",
]
NATURAL = re.compile(r"^[A-Za-zʻ'’ ,.!?—-]+$")


def _literals(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    skip: set[int] = set()
    for node in ast.walk(tree):
        # docstring'lar
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                skip.add(id(body[0].value))
        # log.info("...") — log xabarlari UI emas
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            owner = node.func.value
            if isinstance(owner, ast.Name) and owner.id in ("log", "logging", "logger"):
                for a in node.args:
                    skip.add(id(a))
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip:
            s = node.value.strip()
            if len(s.split()) >= 2 and NATURAL.match(s) and s not in ALLOWED_LITERALS:
                out.append((node.lineno, s))
    return out


@pytest.mark.parametrize("path", UI_MODULES, ids=lambda p: p.name)
def test_no_hardcoded_ui_text(path):
    assert _literals(path) == []


# --- tayyor vidjetlarda inglizcha yo'q ---------------------------------------------------------


def _visible_texts(w: QWidget) -> list[str]:
    texts = []
    for child in [w, *w.findChildren(QWidget)]:
        if isinstance(child, (QLabel, QAbstractButton)):
            texts.append(child.text())
        texts.append(child.toolTip())
        if hasattr(child, "placeholderText"):
            texts.append(child.placeholderText())
    return [x for x in texts if x]


def _menu_texts(m: QMenu) -> list[str]:
    out = []
    for act in m.actions():
        out.append(act.text())
        if act.menu():
            out += _menu_texts(act.menu())
    return out


@pytest.fixture
def controller(qtbot, tmp_path, monkeypatch):
    monkeypatch.setenv("YUE_DATA", str(tmp_path))
    from PySide6.QtWidgets import QApplication

    from yue.app import Controller
    from yue.config import Config
    from yue.pet.pack import load_pack
    from yue.platform import NullPlatform

    class FakeDpapi(NullPlatform):
        def protect(self, data):
            return data[::-1]

        def unprotect(self, blob):
            return blob[::-1]

    cfg = Config(path=tmp_path / "config.json")
    cfg.set("welcome_done", True)
    c = Controller(QApplication.instance(), cfg, load_pack(paths.DEFAULT_PACK), FakeDpapi())
    c.brain.book.add("Dori ichish", "2030-01-01 09:00")
    yield c
    c.shutdown()
    c.pet.close()
    c.bubble.close()


def test_dialogs_and_menu_are_uzbek(qtbot, controller):
    from yue.ui.memory_view import MemoryDialog
    from yue.ui.menu import TaskDialog, fill_menu
    from yue.ui.settings import SettingsDialog
    from yue.ui.welcome import WelcomeDialog

    texts: list[str] = []
    for dlg in (
        SettingsDialog(controller),
        WelcomeDialog(controller),
        MemoryDialog(controller),
        TaskDialog(),
    ):
        qtbot.addWidget(dlg)
        texts += _visible_texts(dlg)
        texts.append(dlg.windowTitle())
        if hasattr(dlg, "tabs"):
            texts += [dlg.tabs.tabText(i) for i in range(dlg.tabs.count())]
    menu = QMenu()
    fill_menu(controller, menu)
    texts += _menu_texts(menu)
    texts += _visible_texts(controller.bubble)
    assert len(texts) > 60
    bad = {x: english_words(x) for x in texts if english_words(x)}
    assert not bad
    for forbidden in ("OK", "Cancel", "Apply", "Close", "Yes", "No", "&OK", "&Cancel"):
        assert forbidden not in texts


def test_t_formats_and_falls_back():
    assert t("ai.today", requests=3, cost="0.010") == "Bugun: 3 ta so'rov, taxminan $0.010"
    assert t("yoq.kalit") == "yoq.kalit"


def test_wardrobe_settings_v4_outfit_and_hood(qtbot, controller):
    from yue.ui.settings import SettingsDialog

    dlg = SettingsDialog(controller, "wardrobe")
    qtbot.addWidget(dlg)
    texts = _visible_texts(dlg)
    assert t("wardrobe.outfit") in texts and t("wardrobe.manual") in texts
    assert t("wardrobe.hood") in texts  # xudidagi yurishda kapyushon: har doim / hech qachon
    for hidden in ("wardrobe.glasses", "wardrobe.phones"):
        assert t(hidden) not in texts
    outfits = [dlg.w_outfit.itemText(i) for i in range(dlg.w_outfit.count())]
    assert outfits == [t("choice.auto"), "Oq futbolka", "Qora xudi", "Kumushrang xudi"]


def test_debug_menu_v4(qtbot, controller, monkeypatch):
    from yue.ui.menu import fill_menu

    monkeypatch.setenv("YUE_DEBUG", "1")
    c = controller
    c.debug_outfit("hoodie_silver")
    assert c.wardrobe.base_outfit == "hoodie_silver"
    menu = QMenu()
    fill_menu(c, menu)
    texts = _menu_texts(menu)
    bad = {x: english_words(x) for x in texts if english_words(x)}
    assert not bad
    assert "Kumushrang xudi" in texts and "Qora xudi" in texts
    assert t("menu.debug.no_art", name=t("slot.walk_music")) in texts  # kumushda rasm yo'q
    # 15-okt: kumushda ham ifodalar bor
    assert t("expr.happy") in texts and t("menu.debug.no_art", name=t("expr.happy")) not in texts
    assert "120%" in texts  # yurish tempi
    c.set_walk_tempo(1.2)
    assert c.behavior.walk_tempo == 1.2 and c.cfg.get("pet.walk_tempo") == 1.2
    c.set_walk_tempo(5.0)
    assert c.behavior.walk_tempo == 1.3  # oralig'i 0.7–1.3
