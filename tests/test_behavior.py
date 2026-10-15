import random

import pytest

from yue import paths
from yue.pet.behavior import HOLD_END, Behavior
from yue.pet.pack import load_pack
from yue.pet.physics import Body, Rect, build_surfaces
from yue.pet.wardrobe import GLASSES, Overrides, Wardrobe

SCREEN = Rect(0, 0, 1920, 1040)
DT = 0.05


@pytest.fixture(scope="module")
def meta():
    return load_pack(paths.DEFAULT_PACK)


class Sim:
    def __init__(self, meta, period="day", seed=1, outfit=None):
        self.period = period
        self.t = 100.0
        wardrobe = Wardrobe.from_pack(
            meta.raw, rng=random.Random(seed), overrides=Overrides(outfit=outfit)
        )
        self.body = Body(x=900, y=200)
        self.bh = Behavior(
            meta, wardrobe, self.body, lambda: self.period, rng=random.Random(seed), half_width=30
        )
        self.bh.screens = [SCREEN]
        self.bh.surfaces = build_surfaces([SCREEN])
        self.bh.start(self.t)
        self.bh.gentle_drop = True  # oyna ochilganda ekran tepasidan tushib keladi
        self.body.drop()
        self.events = []
        self.visuals = []

    def run(self, seconds):
        end = self.t + seconds
        while self.t < end:
            self.t += DT
            vis = self.bh.tick(self.t)
            self.visuals.append(vis)
            self.events.extend(self.bh.pop_events())
        return self

    def slots(self):
        return [v.slot for v in self.visuals]


def test_spawn_lands_without_tantrum(meta):
    sim = Sim(meta).run(3)
    names = [e[0] for e in sim.events]
    assert "landed" in names and "thrown" not in names
    assert sim.body.grounded and sim.body.y == SCREEN.bottom
    assert "angry_stomp" not in sim.slots()


@pytest.mark.parametrize(
    ("period", "forbidden"),
    [
        ("night", {"look_around", "butterfly", "flower", "train"}),
        ("evening", {"look_around", "butterfly", "flower", "train"}),
        ("morning", {"ponder", "walk_pocket", "sleep"}),
        ("day", {"ponder", "walk_pocket", "sleep"}),
    ],
)
def test_activities_follow_period(meta, period, forbidden):
    sim = Sim(meta, period=period, seed=3).run(1800)
    used = set(sim.slots())
    assert not used & forbidden
    assert len(used) >= 5  # hayot bir xil emas


def test_seated_actions_have_transitions(meta):
    sim = Sim(meta, period="night", seed=5).run(2400)
    seq = []
    for s in sim.slots():
        if not seq or seq[-1] != s:
            seq.append(s)
    for i, s in enumerate(seq):
        if s in ("type", "sit") and i > 0:
            assert seq[i - 1] in ("sitdown", "sleep"), seq[max(0, i - 3) : i + 2]
        if s == "sitdown" and i + 1 < len(seq):
            assert seq[i + 1] in ("type", "sit", "sleep")


def test_walk_stays_on_floor_and_mirrors(meta):
    sim = Sim(meta, period="day", seed=7).run(1200)
    walks = [v for v in sim.visuals if v.slot in ("walk", "walk_music")]
    assert walks
    assert {v.mirror for v in walks} == {True, False}
    assert 0 <= sim.body.x <= 1920


def test_sleep_and_wake_cycle(meta):
    sim = Sim(meta, period="night", seed=2).run(3)
    sim.bh.wardrobe.base_outfit = "tee"
    sim.bh.go_sleep(sim.t, forced=True)
    sim.run(4)
    assert sim.bh.sleeping
    look = sim.bh.look
    assert look.outfit in ("hoodie_black", "hoodie_silver")
    assert GLASSES not in look.overlays
    fades = [v for v in sim.visuals if v.slot == "sleep" and v.fade_from is not None]
    assert fades and fades[0].fade_from.slot == "sitdown"
    sim.run(30)
    assert sim.bh.sleeping  # majburiy uyqu o'z-o'zidan tugamaydi

    sim.visuals.clear()
    sim.bh.wake(sim.t)
    sim.run(6)
    assert not sim.bh.sleeping
    order = []
    for s in sim.slots():
        if not order or order[-1] != s:
            order.append(s)
    assert order[:2] == ["sit", "standup"]
    assert any(v.slot == "sit" and v.fade_from is not None for v in sim.visuals)


def test_drag_and_throw_lands(meta):
    sim = Sim(meta, seed=4, outfit="tee").run(3)
    sim.bh.start_drag(sim.t)
    sim.bh.drag_to(500, 100)
    sim.run(0.5)
    assert sim.visuals[-1].slot == "dangle"
    sim.bh.end_drag(1200, 300)
    sim.run(3)
    names = [e[0] for e in sim.events]
    assert "thrown" in names  # ibora uchun
    assert "land" in sim.slots() and "angry_stomp" not in sim.slots()


def test_low_drop_has_no_land(meta):
    sim = Sim(meta, seed=4, outfit="tee").run(3)
    sim.bh.start_drag(sim.t)
    sim.bh.drag_to(500, SCREEN.bottom - 20)  # yerdan 20 px — bir-ikki kadrda tushadi
    sim.bh.end_drag(0, 0)
    sim.events.clear()
    sim.visuals.clear()
    sim.run(2)
    assert "thrown" not in [e[0] for e in sim.events]
    assert "landed" in [e[0] for e in sim.events]
    assert "land" not in sim.slots()


def test_spawn_drop_has_no_land(meta):
    sim = Sim(meta, seed=4, outfit="tee").run(3)
    assert "land" not in sim.slots()


def test_talk_then_expression(meta):
    sim = Sim(meta, seed=6, outfit="tee").run(3)
    sim.bh.set_talking(sim.t, True)
    sim.run(1)
    assert sim.visuals[-1].slot == "talk"
    sim.bh.set_talking(sim.t, False, expression="smug")
    sim.run(0.5)
    vis = sim.visuals[-1]
    names = meta.variant("expressions", "tee").names
    assert vis.slot == "expressions" and vis.frame == names.index("smug")
    sim.run(6)
    assert sim.visuals[-1].slot != "expressions"


def test_perform_seated_from_menu(meta):
    sim = Sim(meta, seed=8).run(3)
    sim.bh.perform(sim.t, "wave")
    sim.run(1.5)
    assert not sim.bh.seated
    sim.bh.perform(sim.t, "type")
    sim.run(0.2)
    assert sim.visuals[-1].slot == "sitdown"
    sim.run(2)
    assert sim.visuals[-1].slot == "type"
    sim.bh.perform(sim.t, "wave")
    sim.run(0.1)
    assert sim.visuals[-1].slot == "standup"


def test_period_change_rerolls_outfit(meta):
    sim = Sim(meta, period="day", seed=9).run(3)
    rolls = []
    for p in ("night", "day", "night", "day", "night"):
        sim.period = p
        sim.bh.restart(sim.t)
        rolls.append(sim.bh.wardrobe.period)
    assert rolls == ["night", "day", "night", "day", "night"]


def test_frame_index_wraps_and_reverse(meta):
    walk = meta.slots["walk"]
    assert walk.frame_at(0, 26, 18.0) == 0 and walk.frame_at(1.0, 26, 18.0) == 18
    assert walk.frame_at(26 / 18 + 0.01, 26, 18.0) == 0  # floor(t × fps) mod kadrlar
    standup = meta.slots["standup"]
    assert standup.sheet == "sitdown"
    assert standup.frame_at(0) == standup.frames - 1
    assert standup.frame_at(10) == 0


# --- v4: kiyimga mos variantlar va fallback ----------------------------------------------------

SILVER_MISSING = {"walk_music", "music", "ponder", "walk_pocket", "tea"}


def test_silver_never_picks_activities_without_art(meta):
    sim = Sim(meta, period="evening", seed=11, outfit="hoodie_silver")
    for period in ("morning", "day", "evening", "night"):
        assert not set(sim.bh.activity_choices(period)) & SILVER_MISSING
    sim.run(1800)
    assert not set(sim.slots()) & SILVER_MISSING
    actions = {e[1] for e in sim.events if e[0] == "action"}
    assert not actions & SILVER_MISSING


def test_each_outfit_uses_only_its_looks(meta):
    for outfit in ("tee", "hoodie_black", "hoodie_silver"):
        sim = Sim(meta, period="day", seed=12, outfit=outfit).run(900)
        bases = {v.look.base_outfit for v in sim.visuals}
        assert bases == {outfit}, outfit
        for v in sim.visuals:
            assert meta.variant(v.slot, v.look.outfit) is not None, (v.slot, v.look.outfit)


@pytest.mark.parametrize("outfit", ["tee", "hoodie_black", "hoodie_silver"])
def test_dangle_has_own_art_in_every_outfit(meta, outfit):
    """15-okt: kumushda ham idle kadri emas, o'z rasmi (qimirlaydi)."""
    sim = Sim(meta, seed=4, outfit=outfit).run(3)
    sim.bh.start_drag(sim.t)
    sim.bh.drag_to(500, 100)
    sim.run(1.0)
    vis = sim.visuals[-1]
    assert (vis.slot, vis.look.outfit) == ("dangle", outfit)
    assert sim.bh.wardrobe.base_outfit == outfit  # reaksiya kiyimni almashtirmaydi
    assert len({v.frame for v in sim.visuals[-15:]}) > 1


def test_fallback_chain_for_missing_art(meta):
    """Fallback faqat rasmi yo'q look'lar uchun: qora xudida angry_stomp → angry ifodasi,
    kumushda (ifodasi bor) — o'sha ifoda; kumushda music yo'q → fallback "idle" (animatsiya)."""
    sim = Sim(meta, seed=4, outfit="hoodie_black").run(3)
    slot, look, frame = sim.bh.resolve("angry_stomp", sim.bh.look)
    assert (slot, look.outfit) == ("expressions", "hoodie_black")
    assert meta.variant(slot, look.outfit).names[frame] == "angry"
    sim = Sim(meta, seed=4, outfit="hoodie_silver").run(3)
    slot, look, frame = sim.bh.resolve("angry_stomp", sim.bh.look)
    assert (slot, look.outfit) == ("expressions", "hoodie_silver")
    assert meta.variant(slot, look.outfit).names[frame] == "angry"
    assert sim.bh.resolve("music", sim.bh.look) == ("idle", sim.bh.look, None)


def drop_from(sim, y=100):
    sim.bh.start_drag(sim.t)
    sim.bh.drag_to(500, y)
    sim.bh.end_drag(0, 0)
    sim.visuals.clear()
    sim.events.clear()


@pytest.mark.parametrize("outfit", ["tee", "hoodie_black", "hoodie_silver"])
def test_fall_and_land_have_own_art(meta, outfit):
    """15-okt: qora xudida land "angry" ifodasi emas, kumushda idle kadri emas — o'z rasmi."""
    sim = Sim(meta, seed=4, outfit=outfit).run(3)
    drop_from(sim)
    sim.run(0.5)
    assert (sim.visuals[-1].slot, sim.visuals[-1].look.outfit) == ("fall", outfit)
    sim.run(0.7)  # ~0.9 s havoda, keyin yerda
    assert sim.bh.activity == "land"
    ground = sim.visuals[-4:]  # yerga tushgandan keyingi kadrlar
    assert ground and (ground[0].slot, ground[0].look.outfit) == ("land", outfit)
    assert sim.bh.wardrobe.base_outfit == outfit  # kiyim almashmaydi


def test_land_plays_once_holds_and_returns(meta):
    sim = Sim(meta, seed=4, outfit="tee").run(3)
    drop_from(sim)
    sim.run(4.5)
    n = meta.variant("land", "tee").frames
    lands = [v.frame for v in sim.visuals if v.slot == "land"]
    assert lands[0] == 0 and sorted(set(lands)) == list(range(n))  # to'liq, bir marta
    assert lands == sorted(lands)  # takrorlanmaydi
    held = (len(lands) - lands.index(n - 1)) * DT
    assert held >= HOLD_END - 2 * DT  # oxirgi kadrda ~1 s
    assert sim.visuals[-1].slot != "land"


def test_grab_during_land_starts_dangle(meta):
    sim = Sim(meta, seed=4, outfit="tee").run(3)
    drop_from(sim)
    sim.run(1.3)
    assert sim.visuals[-1].slot == "land"
    sim.bh.start_drag(sim.t)
    sim.bh.drag_to(600, 300)
    sim.run(0.2)
    assert sim.visuals[-1].slot == "dangle" and sim.bh.step is None


def test_fall_frames_repeat_in_air(meta):
    sim = Sim(meta, seed=4, outfit="tee").run(3)
    sim.bh.start_drag(sim.t)
    sim.bh.drag_to(900, 50)
    sim.bh.end_drag(0, -300)
    sim.visuals.clear()
    sim.run(0.6)
    falls = [v.frame for v in sim.visuals if v.slot == "fall"]
    assert set(falls) == set(range(meta.variant("fall", "tee").frames))


def test_type_sits_down_with_glasses_on_tee(meta):
    sim = Sim(meta, seed=8, outfit="tee").run(3)
    sim.bh.perform(sim.t, "type")
    sim.run(3)
    order = []
    for v in sim.visuals:
        if not order or order[-1][0] != v.slot:
            order.append((v.slot, v.look.outfit))
    i = order.index(("type", "tee_glasses"))
    assert order[i - 1] == ("sitdown", "tee")
    sim.bh.perform(sim.t, "idle")
    sim.run(0.1)
    assert sim.visuals[-1].slot == "standup"


def test_sleep_from_tee_switches_to_hoodie(meta):
    for period, want in (("night", "hoodie_black"), ("day", "hoodie_silver")):
        sim = Sim(meta, period=period, seed=2, outfit="tee").run(1.0)  # qo'ndi, hali idle
        assert sim.bh.wardrobe.base_outfit == "tee"
        sim.visuals.clear()
        sim.bh.go_sleep(sim.t, forced=True)
        sim.run(3)
        assert sim.bh.sleeping and sim.bh.wardrobe.base_outfit == want
        assert sim.visuals[0].slot == "sitdown" and sim.visuals[0].look.outfit == want
        assert sim.visuals[0].fade_from is not None  # futbolkadan xudiga — crossfade
        assert any(v.slot == "sleep" and v.fade_from is not None for v in sim.visuals)


def test_non_loop_slot_holds_last_frame(meta):
    sim = Sim(meta, period="day", seed=3, outfit="tee").run(3)
    sim.bh.perform(sim.t, "flower")
    info = meta.slots["flower"]
    n = meta.variant("flower", "tee").frames
    sim.visuals.clear()
    sim.run(n / info.fps + HOLD_END - 0.2)
    assert all(v.slot == "flower" for v in sim.visuals)
    assert sim.visuals[-1].frame == n - 1
    sim.run(0.5)
    assert sim.visuals[-1].slot != "flower"


def test_silver_talk_ends_with_expression(meta):
    """15-okt: kumushda ham gapdan keyin javob ifodasi (boshqa kiyimlardagidek)."""
    sim = Sim(meta, seed=6, outfit="hoodie_silver").run(3)
    sim.bh.set_talking(sim.t, True)
    sim.run(1)
    assert (sim.visuals[-1].slot, sim.visuals[-1].look.outfit) == ("talk", "hoodie_silver")
    assert sim.bh.expression_available("happy")
    sim.bh.set_talking(sim.t, False, expression="happy")
    sim.run(1)
    vis = sim.visuals[-1]
    assert (vis.slot, vis.look.outfit) == ("expressions", "hoodie_silver")
    assert meta.variant("expressions", "hoodie_silver").names[vis.frame] == "happy"


def test_every_tag_has_expression_in_every_outfit(meta):
    for outfit in ("tee", "hoodie_black", "hoodie_silver"):
        sim = Sim(meta, seed=1, outfit=outfit).run(2)
        for tag in meta.raw["expression_map"]:
            assert sim.bh.expression_available(tag), (outfit, tag)


# --- ko'z yumib-ochish -------------------------------------------------------------------------


def idle_run(meta, outfit="tee", seconds=40.0, seed=5):
    sim = Sim(meta, seed=seed, outfit=outfit).run(3)
    sim.bh.set_focus(sim.t, True)  # suhbat ochiq — Yue to'xtab tinglaydi (idle)
    sim.run(1.5)  # o'tirgan bo'lsa — avval turadi
    assert sim.bh.step.slot == "idle"
    sim.visuals.clear()
    start = sim.t
    sim.run(seconds)
    times = [start + (i + 1) * DT for i in range(len(sim.visuals))]
    return sim, list(zip(times, sim.visuals, strict=True))


@pytest.mark.parametrize("outfit", ["tee", "hoodie_black", "hoodie_silver"])
def test_blink_interval_and_frames(meta, outfit):
    blink = meta.slots["idle"].blink
    assert blink.frames == (4, 5, 6) and blink.rest == (0, 1, 2, 3, 7)
    _sim, seq = idle_run(meta, outfit)
    assert all(v.slot == "idle" for _, v in seq)
    frames = [v.frame for _, v in seq]
    starts = [i for i in range(1, len(frames)) if frames[i] == 4 and frames[i - 1] != 4]
    assert len(starts) >= 5
    for s in starts:  # ketma-ket 4 → 5 → 6, keyin yana rest
        run = [f for f in frames[s : s + 12] if f in blink.frames]
        assert run[:3] == sorted(run[:3])
    ends = [i for i in range(len(frames) - 1) if frames[i] == 6 and frames[i + 1] != 6]
    gaps = [seq[s][0] - seq[e][0] for e, s in zip(ends, starts[1:], strict=False)]
    assert gaps and all(3.0 - 2 * DT <= g <= 6.0 + 2 * DT for g in gaps), gaps
    # blink'dan tashqarida faqat rest kadrlari
    in_blink = set()
    for s in starts:
        j = s
        while j < len(frames) and frames[j] in blink.frames:
            in_blink.add(j)
            j += 1
    assert {frames[i] for i in range(len(frames)) if i not in in_blink} <= set(blink.rest)


def test_no_blink_while_talking_or_sleeping(meta):
    sim = Sim(meta, seed=6, outfit="tee").run(3)
    sim.bh.set_talking(sim.t, True)
    for _ in range(200):
        sim.run(DT)
        assert sim.bh._blink_t0 is None and sim.visuals[-1].slot == "talk"
    sim.bh.set_talking(sim.t, False)
    sim.bh.go_sleep(sim.t, forced=True)
    sim.run(3)
    for _ in range(200):
        sim.run(DT)
        assert sim.bh._blink_t0 is None and sim.visuals[-1].slot == "sleep"


def test_blink_now(meta):
    sim = Sim(meta, seed=7, outfit="tee").run(3)
    sim.bh.blink_now(sim.t)
    sim.visuals.clear()
    sim.run(0.6)
    assert [v.frame for v in sim.visuals if v.frame in (4, 5, 6)][:1] == [4]


# --- look almashganda crossfade ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("outfit", "typing_look"),
    [("tee", "tee_glasses"), ("hoodie_black", "hood_black"), ("hoodie_silver", "hood_silver")],
)
def test_look_change_crossfades(meta, outfit, typing_look):
    sim = Sim(meta, seed=8, outfit=outfit).run(3)
    sim.bh.perform(sim.t, "type")
    sim.run(3)
    first_type = next(v for v in sim.visuals if v.slot == "type")
    assert first_type.look.outfit == typing_look
    assert first_type.fade_from is not None
    assert first_type.fade_from.slot == "sitdown" and first_type.fade_from.look.outfit == outfit
    n = meta.variant("sitdown", outfit).frames
    assert first_type.fade_from.frame == n - 1  # oldingi slotning oxirgi kadri
    assert first_type.frame == 0  # yangisining birinchi kadri
    sim.visuals.clear()
    sim.bh.perform(sim.t, "idle")  # type → standup
    sim.run(0.3)
    stand = next(v for v in sim.visuals if v.slot == "standup")
    assert stand.fade_from is not None and stand.fade_from.look.outfit == typing_look
    fades = [e[1] for e in sim.events if e[0] == "crossfade"]
    assert (outfit, "type") in fades and (typing_look, "standup") in fades


def test_same_look_has_no_extra_crossfade(meta):
    sim = Sim(meta, seed=8, outfit="tee").run(3)
    sim.bh.perform(sim.t, "wave")
    sim.events.clear()
    sim.run(1.0)
    assert not [e for e in sim.events if e[0] == "crossfade"]
