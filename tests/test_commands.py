"""Buyruqlar: <harakat> tegi, AI'siz tez tanish, buyruq qatlami, kiyim almashtirish va sayr."""

import json
import re
import time

import pytest

from tests.fakes import FakeProvider
from tests.test_behavior import DT, SCREEN, Sim
from tests.test_chat import ctl, send, use  # noqa: F401 — pytest fixture
from yue import paths
from yue.ai import prompt
from yue.ai.parse import parse_reply, stream_visible
from yue.ai.service import ChatResult
from yue.commands import Commands, CommandSpec, UniquePicker, normalize
from yue.config import Config
from yue.lines import Lines
from yue.pet.behavior import SAYR_STOP_EVERY, SAYR_STOP_S
from yue.pet.pack import load_pack
from yue.pet.physics import Seg

CMDS = Commands.load()


@pytest.fixture(scope="module")
def meta():
    return load_pack(paths.DEFAULT_PACK)


def run_cmd(sim, name, **kw):
    spec = CMDS.get(name)
    if kw:
        spec = CommandSpec(**{**spec.__dict__, **kw})
    return sim.bh.run_command(sim.t, spec)


# --- parse ------------------------------------------------------------------------------------


def test_harakat_tag_only_known_names_and_at_most_one():
    r = parse_reply("[sleepy] Mayli, ozgina. <harakat>uxla</harakat>")
    assert r.command == "uxla" and r.text == "Mayli, ozgina." and r.expression == "sleepy"
    r = parse_reply("[happy] Hop! <harakat> Sakra </harakat> <harakat>uxla</harakat>")
    assert r.command == "sakra" and "harakat" not in r.text and "uxla" not in r.text
    r = parse_reply("[smug] Uchish hali yo'q. <harakat>uch</harakat>")
    assert r.command is None and r.text == "Uchish hali yo'q."
    r = parse_reply("[happy] Ketdik! <harakat>sayr</harakat> <eslab>Sayrni yaxshi ko'radi</eslab>")
    assert r.command == "sayr" and [a.kind for a in r.actions] == ["remember"]
    assert parse_reply("[happy] Ha <harakat>sakra").text == "Ha sakra"  # buzilgan teg bajarilmaydi
    assert parse_reply("[happy] <harakat>sakra</harakat>").command == "sakra"  # matnsiz ham
    assert stream_visible("[happy] Ketdik! <hara") == "Ketdik!"
    assert stream_visible("[happy] Ketdik! <harakat>sa") == "Ketdik!"


# --- tez tanish -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text, name",
    [
        ("uxla", "uxla"),
        ("Uxlab ol!", "uxla"),
        ("ухла", "uxla"),
        ("yuring sayr qilamiz", "sayr"),
        ("Uyg‘on", "uygon"),
        ("tur uyg'on", "uygon"),  # uzunroq ibora "tur" dan ustun
        ("tur", "tur"),
        ("kuylab ber", "kuyla"),
        ("To'xta!", "toxta"),
        ("kecha yaxshi uxladim", None),
        ("sakrash qiyinmi?", None),
        ("sakra?", None),  # savol — buyruq emas
        ("uxla endi men ham yotaman", None),  # 4 so'zdan ko'p
        ("", None),
    ],
)
def test_fast_recognition(text, name):
    assert CMDS.recognize(text) == name


# --- fayllar ----------------------------------------------------------------------------------


def persona_names() -> list[str]:
    text = (paths.PERSONA_DIR / "persona_uz.txt").read_text(encoding="utf-8")
    after = text.split("- Nomlar:", 1)[1].strip().splitlines()[0]
    return re.findall(r"([\w']+) —", after)


def test_files_agree(meta):
    data = json.loads((paths.PERSONA_DIR / "harakatlar.json").read_text(encoding="utf-8"))
    lines = Lines.load()
    assert list(data["harakatlar"]) == list(CMDS.names)
    # AI'siz buyruqlar ("hazil ayt") AI tegi emas — personada yo'q
    assert persona_names() == [n for n in CMDS.names if not CMDS.specs[n].no_ai]
    assert set(data["rejimlar"]) == {"bir_marta", "soniya", "uygonguncha",
                                     "keyingi_buyruqgacha", "maxsus"}  # fmt: skip
    for name, spec in CMDS.specs.items():
        if spec.mode != "maxsus" and name != "raqs":  # raqs: "dance" sloti hali yo'q
            assert spec.slot in meta.slots, name
            assert meta.raw["slots"][spec.slot], name
        if spec.mode == "soniya":
            assert spec.seconds > 0, name
        assert lines.has(*spec.line_key), (name, spec.line)
        for w in spec.words:
            assert " ".join(normalize(w)) == w, (name, w)  # kichik harf, tinish belgisiz
            assert CMDS.recognize(w) == name, (name, w)  # boshqa buyruq bilan to'qnashmaydi
    for key in ("harakat_kiyim", "harakat_yoq", "qoshiq"):
        assert lines.options(key)
    for sub in ("boshlash", "gap", "kulish", "tugash"):
        assert lines.options("sayr", sub)


def test_harakatlar_json_is_in_dist():
    spec = (paths.RES / "build" / "yue.spec").read_text(encoding="utf-8")
    assert '(str(ROOT / "persona"), "persona")' in spec


# --- buyruq qatlami ---------------------------------------------------------------------------


def slots_after(sim, seconds):
    start = len(sim.visuals)
    sim.run(seconds)
    return [v.slot for v in sim.visuals[start:]]


def test_silver_stretch_switches_to_tee(meta):
    sim = Sim(meta, outfit="hoodie_silver").run(3)
    sim.bh.wardrobe.overrides.outfit = None  # buyruq uchun kiyim almashadi
    assert run_cmd(sim, "kerish") == "outfit"  # kerishish faqat futbolkada chizilgan
    assert sim.bh.wardrobe.base_outfit == "tee"
    shown = sim.run(0.5).visuals[-1]
    assert shown.slot == "stretch" and shown.look.base_outfit == "tee"
    assert any(v.fade_from is not None for v in sim.visuals[-10:])  # crossfade bilan
    assert sim.bh.command is not None
    sim.run(10)
    assert sim.bh.command is None and sim.visuals[-1].slot != "stretch"
    assert sim.bh.wardrobe.base_outfit == "tee"  # keyingi qayta tanlovgacha


@pytest.mark.parametrize("outfit", ["hoodie_black", "hoodie_silver"])
def test_jump_in_hoodie_keeps_outfit(meta, outfit):
    """15-okt: xudilarda ham sakrash rasmi bor — kiyim almashmaydi."""
    sim = Sim(meta, outfit=outfit).run(3)
    sim.bh.wardrobe.overrides.outfit = None
    assert run_cmd(sim, "sakra") == "ok"
    shown = sim.run(0.5).visuals[-1]
    assert (shown.slot, shown.look.outfit) == ("excited_jump", outfit)
    assert sim.bh.wardrobe.base_outfit == outfit


def test_tea_switches_to_black_hoodie(meta):
    sim = Sim(meta, outfit="tee").run(3)
    sim.bh.wardrobe.overrides.outfit = None
    assert run_cmd(sim, "choy") == "outfit"
    assert sim.bh.wardrobe.base_outfit == "hoodie_black"
    assert "tea" in slots_after(sim, 1.0)


def test_time_limit_ignored_for_commands(meta):
    sim = Sim(meta, period="night", outfit="tee").run(3)
    assert "butterfly" not in sim.bh.activity_choices("night")
    assert run_cmd(sim, "kapalak") == "ok"
    assert "butterfly" in slots_after(sim, 1.0)


def test_missing_slot(meta):
    sim = Sim(meta).run(3)
    assert sim.bh.run_command(sim.t, CommandSpec("uch", "bir_marta", slot="uchish")) == "missing"
    assert sim.bh.command is None


def test_talking_does_not_stop_command_and_drag_cancels(meta):
    sim = Sim(meta, outfit="tee").run(3)
    run_cmd(sim, "mashq")
    sim.run(0.5)
    sim.bh.set_talking(sim.t, True)
    assert slots_after(sim, 1.0)[-1] == "train"
    sim.bh.set_talking(sim.t, False, "happy")
    assert sim.visuals[-1].slot == "train"
    sim.bh.start_drag(sim.t)
    assert sim.bh.command is None
    assert ("command_end", "mashq") in sim.bh.pop_events()


def test_sleep_command_until_woken(meta):
    sim = Sim(meta).run(3)
    assert run_cmd(sim, "uxla") == "ok"
    sim.run(3)
    assert sim.bh.sleeping and sim.bh.command.name == "uxla"
    sim.bh.set_talking(sim.t, True)  # o'z javobi uni uyg'otmaydi
    sim.run(1)
    assert sim.bh.sleeping
    sim.bh.wake(sim.t)
    assert sim.bh.command is None
    assert "standup" in slots_after(sim, 3)


def test_sit_until_next_command(meta):
    sim = Sim(meta, outfit="tee").run(3)
    run_cmd(sim, "otir")
    sim.run(60)
    assert sim.visuals[-1].slot == "sit" and sim.bh.command.name == "otir"
    assert run_cmd(sim, "sakra") == "ok"
    assert "standup" in slots_after(sim, 1.0)
    assert sim.visuals[-1].slot == "excited_jump"


def test_sit_returns_to_life_after_ten_minutes(meta):
    sim = Sim(meta, outfit="tee").run(3)
    run_cmd(sim, "otir")
    sim.run(605)
    assert sim.bh.command is None


def test_code_sits_down_types_and_stands_up(meta):
    sim = Sim(meta, outfit="tee").run(3)
    run_cmd(sim, "kod", seconds=3.0)
    seq = slots_after(sim, 6)
    assert seq.index("sitdown") < seq.index("type") < seq.index("standup")


def test_special_commands(meta):
    sim = Sim(meta).run(3)
    assert run_cmd(sim, "uygon") == "idle"  # uyg'oq — faqat ibora
    assert run_cmd(sim, "tur") == "idle"
    run_cmd(sim, "otir")
    sim.run(2)
    assert run_cmd(sim, "tur") == "ok"
    assert "standup" in slots_after(sim, 1.0)
    run_cmd(sim, "uxla")
    sim.run(3)
    assert run_cmd(sim, "uygon") == "ok" and not sim.bh.sleeping
    sim.run(3)
    run_cmd(sim, "salom", seconds=60)
    assert run_cmd(sim, "toxta") == "ok"
    assert sim.bh.command is None
    assert sim.visuals[-1].slot != "wave" or slots_after(sim, 0.3)[-1] == "idle"


# --- sayr -------------------------------------------------------------------------------------


def test_sayr_walks_stops_and_ends(meta):
    sim = Sim(meta, outfit="tee").run(3)
    y = sim.body.y
    run_cmd(sim, "sayr")
    stops, walk_mirror, end_t = [], set(), None
    start_t = sim.t
    while sim.t < start_t + 160:
        sim.t += DT
        vis = sim.bh.tick(sim.t)
        sim.visuals.append(vis)
        if vis.slot == "walk":
            walk_mirror.add(vis.mirror)
        assert sim.body.y == y and SCREEN.left <= sim.body.x <= SCREEN.right  # faqat shu yuzada
        for name, data in sim.bh.pop_events():
            if name == "sayr" and data in ("gap", "kulish"):
                stops.append(sim.t)
            if name == "sayr" and data == "end":
                end_t = sim.t
    assert end_t is not None and 149 <= end_t - start_t <= 151
    assert sim.bh.command is None and sim.bh.sayr is None
    assert walk_mirror == {True, False}  # chetga yetib burilgan
    assert len(stops) >= 4
    walking = [b - a - SAYR_STOP_S for a, b in zip(stops, stops[1:], strict=False)]
    lo, hi = SAYR_STOP_EVERY
    assert all(lo - 2 * DT <= w <= hi + 2 * DT for w in walking), walking
    assert stops[0] - start_t <= hi + 1


def test_sayr_pauses_for_reply_and_toxta_or_drag_end_it(meta):
    sim = Sim(meta, outfit="tee").run(3)
    run_cmd(sim, "sayr")
    sim.run(2)
    assert sim.visuals[-1].slot == "walk"
    sim.bh.set_talking(sim.t, True)
    assert slots_after(sim, 1)[-1] == "talk"
    sim.bh.set_talking(sim.t, False, "happy")
    assert slots_after(sim, 0.5)[-1] == "walk"
    assert run_cmd(sim, "toxta") == "ok" and sim.bh.sayr is None
    run_cmd(sim, "sayr")
    sim.run(1)
    sim.bh.start_drag(sim.t)
    assert sim.bh.sayr is None and sim.bh.command is None


def test_sayr_focus_does_not_pause(meta):
    sim = Sim(meta, outfit="tee").run(3)
    sim.bh.set_focus(sim.t, True)  # foydalanuvchi pufakda "sayr" deb yozdi
    run_cmd(sim, "sayr")
    assert slots_after(sim, 2)[-1] == "walk"


def test_unique_picker_never_repeats_within_sayr():
    opts = Lines.load().options("sayr", "gap")
    picker = UniquePicker()
    got = [picker.pick(opts)[1] for _ in opts]
    assert len(set(got)) == len(opts)
    assert picker.pick(opts) is not None  # hammasi aytilgach — yana boshidan


# --- hazil darajasi va model ------------------------------------------------------------------


def test_humor_level_in_state_block():
    import datetime as dt

    now = dt.datetime(2026, 10, 13, 15, 0)
    blocks, _ = prompt.build(prompt.PromptContext(now=now), "salom", True)
    assert "Hazil darajasi: o'rtacha." in blocks[-1].text
    blocks, _ = prompt.build(prompt.PromptContext(now=now, humor="high"), "salom", True)
    assert blocks[-1].text.startswith("[Holat]") and "Hazil darajasi: ko'p." in blocks[-1].text
    assert blocks[0].cache and "HARAKATLAR" in blocks[0].text  # katta persona keshlanadi


def test_defaults_humor_and_fast_mode():
    assert Config().get("pet.humor") == "medium"
    assert Config().get("ai.mode") == "fast"
    assert Config({"ai": {"mode": "fast"}}).get("ai.mode") == "fast"  # tanlov saqlanadi


# --- Controller: tez tanish, ibora, takror -----------------------------------------------------


def ground(c):
    """Controller testlarida Yue polda turadi (start() chaqirilmagan)."""
    c.behavior.body.x = 900
    c.behavior.body.land(Seg(0, 1920, 1040), None)


def wait_answer(qtbot, c):
    qtbot.waitUntil(lambda: not c.brain.busy, timeout=5000)


def spy_commands(c):
    calls = []
    orig = c.behavior.run_command

    def spy(now, spec):
        calls.append(spec.name)
        return orig(now, spec)

    c.behavior.run_command = spy
    return calls


def test_fast_command_runs_once_before_answer(qtbot, ctl):  # noqa: F811
    use(
        ctl,
        FakeProvider(
            "claude", "claude-sonnet-5-5", default="[sleepy] Mayli. <harakat>uxla</harakat>"
        ),
    )
    calls = spy_commands(ctl)
    ground(ctl)
    ctl.open_chat()
    send(qtbot, ctl, "Uxlab ol!")
    assert calls == ["uxla"]  # javobni kutmasdan
    wait_answer(qtbot, ctl)
    assert calls == ["uxla"]  # javobdagi xuddi shu teg ikkinchi marta bajarilmadi
    assert ctl.bubble.text.text() == "" or "harakat" not in ctl.bubble._full


def test_ai_tag_runs_command(qtbot, ctl):  # noqa: F811
    use(
        ctl,
        FakeProvider(
            "claude", "claude-sonnet-5-5", default="[happy] Hop! <harakat>sakra</harakat>"
        ),
    )
    calls = spy_commands(ctl)
    ground(ctl)
    ctl.open_chat()
    send(qtbot, ctl, "Bir sakrab bersangiz bo'ladimi endi")
    wait_answer(qtbot, ctl)
    assert calls == ["sakra"]
    assert ctl.bubble._full == "Hop!"


def test_repeat_after_window_runs_again(qtbot, ctl):  # noqa: F811
    calls = spy_commands(ctl)
    ground(ctl)
    from yue.ai.parse import Reply

    res = ChatResult("answer", reply=Reply("happy", "Hop!", command="sakra"))
    ctl._fast_cmd = ("sakra", time.monotonic() - 5)
    ctl._on_answered(res)
    assert calls == []
    ctl._fast_cmd = ("sakra", time.monotonic() - 20)  # 15 s dan o'tgan
    ctl._on_answered(res)
    assert calls == ["sakra"]


def test_offline_command_answers_with_its_line(qtbot, ctl):  # noqa: F811
    from yue.ai.providers.base import ProviderError

    use(ctl, FakeProvider("claude", "claude-sonnet-5-5", script=[ProviderError("network")] * 4))
    ctl.open_chat()
    send(qtbot, ctl, "uxla")
    wait_answer(qtbot, ctl)
    assert ctl.bubble._full in {t for _, t in Lines.load().options("harakat", "uxla")}
    assert len(ctl.brain.service.queue) == 0  # buyruq navbatga qo'yilmadi


def test_no_keys_command_line_and_missing(qtbot, ctl):  # noqa: F811
    ctl.brain.router.set_targets([])
    ctl.open_chat()
    send(qtbot, ctl, "kuylab ber")
    wait_answer(qtbot, ctl)
    assert ctl.bubble._full in {t for _, t in Lines.load().options("qoshiq")}
    ctl.commands = Commands({"uch": CommandSpec("uch", "bir_marta", slot="uchish", line="x")})
    ctl.bubble.close_bubble()
    ground(ctl)
    assert ctl.run_command("uch") == "missing"
    assert ctl.bubble._full in {t for _, t in Lines.load().options("harakat_yoq")}


def test_sayr_lines_do_not_repeat(qtbot, ctl):  # noqa: F811
    said = []
    ctl.say = lambda e, t: said.append(t)
    ctl._on_sayr("start")
    n = len(Lines.load().options("sayr", "gap"))
    for _ in range(n):
        ctl._on_sayr("gap")
    assert len(said) == n and len(set(said)) == n
    ctl._on_sayr("end")
    assert said[-1] in {t for _, t in Lines.load().options("sayr", "tugash")}


def test_humor_from_settings_reaches_prompt(qtbot, ctl):  # noqa: F811
    ctl.cfg.set("pet.humor", "low")
    assert ctl.brain.prompt_context().humor == "low"


def test_all_speech_goes_through_say_text():
    """Ovoz keyin ulanishi uchun: pufakka Yue gapi faqat `Controller.say_text` orqali chiqadi."""
    sources = {p: p.read_text(encoding="utf-8") for p in (paths.RES / "yue").rglob("*.py")}
    calls = {p.name: src.count("show_text(") for p, src in sources.items() if "show_text(" in src}
    assert calls == {"app.py": 1, "bubble.py": calls.get("bubble.py", 0)}
    bubble = sources[paths.RES / "yue" / "ui" / "bubble.py"]
    assert "self.show_text(" not in bubble  # pufak o'zi gapirmaydi (open_input ham)
