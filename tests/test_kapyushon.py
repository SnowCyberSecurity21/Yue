"""14-oktabr videolari: yangi yurish lentalari, hood_up klipi va xudida kapyushon mantiqi."""

import json
import random
import statistics

import pytest
from PySide6.QtGui import QImage

from tests.test_behavior import Sim, meta  # noqa: F401 — fixture
from yue import paths
from yue.pet.behavior import CROSSFADE
from yue.pet.wardrobe import Overrides, Wardrobe

# --- tayyor to'plam ----------------------------------------------------------------------------

NEW_WALKS = [  # (slot, look, kadrlar, speed) — foydalanuvchi o'lchovi bilan bir xil
    ("walk_music", "tee_phones", 38, 122.9),
    ("walk_music", "hood_black", 27, 155.0),
    ("walk_pocket", "hoodie_black", 28, 153.5),
    ("walk", "hood_silver", 25, 162.0),
]


@pytest.mark.parametrize(("slot", "look", "frames", "speed"), NEW_WALKS)
def test_new_video_walks_in_pack(meta, slot, look, frames, speed):  # noqa: F811
    v = meta.variant(slot, look)
    assert v.frames == frames and v.speed == speed and v.fps == 18.0
    assert meta.raw["slots"][slot]["variants"][look]["source"] == "video"


def test_hood_black_walk_points_to_walk_music_strip(meta):  # noqa: F811
    raw = meta.raw["slots"]
    assert raw["walk"]["variants"]["hood_black"] == raw["walk_music"]["variants"]["hood_black"]
    assert meta.variant("walk", "hood_black").strips[0].file == "hood_black/walk_music.png"


def _rows(img: QImage, i: int, fw: int, foot_y: int, half: int = 120, up: int = 370) -> list[int]:
    """Kadr i ning maskasi: har qator — bitlar (x = langar ± half), oyoq chizig'iga tekislangan."""
    img = img.convertToFormat(QImage.Format.Format_ARGB32)
    bpl = img.bytesPerLine()
    data = bytes(img.constBits())[: bpl * img.height()]
    c = i * fw + fw // 2
    out = []
    for y in range(foot_y - up, foot_y):
        bits = 0
        if 0 <= y < img.height():
            for x in range(max(c - half, i * fw), min(c + half, (i + 1) * fw)):
                if data[y * bpl + x * 4 + 3] > 128:
                    bits |= 1 << (x - c + half)
        out.append(bits)
    return out


def _best_shift(a: list[int], b: list[int], limit: int = 12) -> tuple[float, int]:
    """(IoU, dx): `a` ni dx px o'ngga surganda `b` ga eng mos."""
    best = (0.0, 0)
    for dx in range(-limit, limit + 1):
        inter = union = 0
        for ra, rb in zip(a, b, strict=True):
            sa = ra << dx if dx >= 0 else ra >> -dx
            inter += (sa & rb).bit_count()
            union += (sa | rb).bit_count()
        iou = inter / max(1, union)
        if iou > best[0]:
            best = (iou, dx)
    return best


def _anchor_shift(meta, clip_img, s, frame, look, walk_frames):  # noqa: F811
    """Klip kadri va look yurish lentasining eng o'xshash kadri orasidagi langar farqi (px)."""
    w = meta.variant("walk", look).strips[0]
    wimg = QImage(str(meta.path(w)))
    a = _rows(clip_img, frame, s.frame_width, s.foot_y)
    best = max(_best_shift(a, _rows(wimg, i, w.frame_width, w.foot_y)) for i in walk_frames)
    return best[1]


def _heights(img: QImage, frames: int, fw: int) -> list[tuple[int, int]]:
    """Har kadrda (eng yuqori, eng past) ko'rinadigan qator (alfa > 128)."""
    img = img.convertToFormat(QImage.Format.Format_ARGB32)
    bpl, h = img.bytesPerLine(), img.height()
    data = bytes(img.constBits())[: bpl * h]
    solid = bytes(1 if a > 128 else 0 for a in range(256))
    out = []
    for i in range(frames):
        rows = [
            y
            for y in range(h)
            if 1 in data[y * bpl + i * fw * 4 + 3 : y * bpl + (i + 1) * fw * 4 : 4].translate(solid)
        ]
        out.append((rows[0], rows[-1]))
    return out


@pytest.fixture(scope="module")
def hood_clip(meta):  # noqa: F811
    v = meta.variant("hood_up", "hood_black")
    s = v.strips[0]
    img = QImage(str(meta.path(s)))
    return v, s, _heights(img, s.frames, s.frame_width)


def test_hood_up_clip_size(meta, hood_clip):  # noqa: F811
    v, s, rows = hood_clip
    info = meta.slots["hood_up"]
    assert s.frames <= 64 and v.fps in (12.0, 10.0) and not info.loop
    assert info.kind == "transition" and info.faces_right
    up_s = info.duration(s.frames, info.fps_of(v))
    assert up_s <= 5.0 + 1 / v.fps  # o'rtadagi deyarli harakatsiz qism kesilgan
    down = meta.slots["hood_down"]
    assert down.reverse and down.faces_right and down.variants["hood_black"] == v
    down_s = down.duration(s.frames, down.fps_of(v))
    assert down_s == pytest.approx(up_s / 1.5)  # yechish 1.5× tezroq
    assert 7.0 <= up_s + down_s <= 9.0  # kapyushonli yurishga ~8 s qo'shiladi
    # birinchi kadr bo'yi = hoodie_black yurish lentasidagi bo'y (±2%)
    w = meta.variant("walk", "hoodie_black").strips[0]
    walk_h = statistics.median(
        b - t for t, b in _heights(QImage(str(meta.path(w))), w.frames, w.frame_width)
    )
    first = rows[0][1] - rows[0][0]
    assert abs(first - walk_h) <= 0.02 * walk_h
    # oxirgi kadr bo'yi = kapyushonli yurish lentasi (±2%)
    hw = meta.variant("walk", "hood_black").strips[0]
    hrows = _heights(QImage(str(meta.path(hw))), hw.frames, hw.frame_width)
    last = rows[-1][1] - rows[-1][0]
    assert abs(last - statistics.median(b - t for t, b in hrows)) <= 0.02 * last
    # foot_y: har kadrda eng past nuqta yerda
    assert all(abs(b + 1 - s.foot_y) <= 1 for _, b in rows)
    assert 0 <= v.walk_frame < meta.variant("walk", "hood_black").frames


def test_hood_up_ends_on_walk_anchors(meta):  # noqa: F811
    """Klip boshi hoodie_black yurishining, oxiri hood_black yurishining langarida (≤ 1 px)."""
    v = meta.variant("hood_up", "hood_black")
    s = v.strips[0]
    img = QImage(str(meta.path(s)))
    n_plain = meta.variant("walk", "hoodie_black").frames
    assert abs(_anchor_shift(meta, img, s, 0, "hoodie_black", range(n_plain))) <= 1
    assert abs(_anchor_shift(meta, img, s, s.frames - 1, "hood_black", [v.walk_frame])) <= 1


# --- kapyushon qarori ----------------------------------------------------------------------------


class FixedRandom(random.Random):
    """Soxta tasodif: random() doim bir xil qiymat."""

    def __init__(self, value: float) -> None:
        super().__init__(0)
        self.value = value

    def random(self) -> float:
        return self.value


@pytest.fixture(scope="module")
def pack():
    return json.loads((paths.DEFAULT_PACK / "pack.json").read_text(encoding="utf-8"))


def wardrobe(pack, outfit, period="day", r=0.5, hood=None):
    w = Wardrobe.from_pack(pack, rng=FixedRandom(r), overrides=Overrides(outfit=outfit, hood=hood))
    w.update_period(period)
    return w


def test_hood_probability_values_in_pack(pack):
    hw = pack["wardrobe"]["hood_walk"]
    assert hw["slots"] == ["walk", "walk_music"]
    p = hw["probability"]
    assert p["morning"] == p["day"] == 0.2 and p["evening"] == p["night"] == 0.6


@pytest.mark.parametrize(
    ("period", "r", "up"),
    [
        ("morning", 0.19, True),
        ("day", 0.19, True),
        ("day", 0.21, False),
        ("evening", 0.59, True),
        ("night", 0.59, True),
        ("night", 0.61, False),
    ],
)
@pytest.mark.parametrize("outfit", ["hoodie_black", "hoodie_silver"])
def test_hood_decision_by_period(pack, outfit, period, r, up):
    w = wardrobe(pack, outfit, period, r)
    assert w.decide_hood("walk", period) is up
    look = w.dress("walk", period, hood=up)
    assert look.hood is up and look.base_outfit == outfit


def test_hood_rates_with_real_random(pack):
    for period, rate in (("day", 0.2), ("night", 0.6)):
        w = Wardrobe.from_pack(
            pack, rng=random.Random(5), overrides=Overrides(outfit="hoodie_black")
        )
        w.update_period(period)
        n = sum(w.decide_hood("walk", period) for _ in range(4000))
        assert abs(n / 4000 - rate) < 0.03


@pytest.mark.parametrize("r", [0.0, 0.5, 0.99])
def test_never_hood_in_pocket_walk_or_tee(pack, r):
    assert not wardrobe(pack, "hoodie_black", "night", r).decide_hood("walk_pocket", "night")
    tee = wardrobe(pack, "tee", "night", r)
    for slot in ("walk", "walk_music", "walk_pocket"):
        assert not tee.decide_hood(slot, "night")
    assert not wardrobe(pack, "tee", "night", r, hood=True).decide_hood("walk", "night")


@pytest.mark.parametrize("period", ["morning", "day", "evening", "night"])
def test_walk_music_black_always_hooded(pack, period):
    w = wardrobe(pack, "hoodie_black", period, r=0.99)
    assert w.has("walk_music") and w.decide_hood("walk_music", period)
    assert w.dress("walk_music", period, hood=True).outfit == "hood_black"


def test_settings_hood_always_and_never(pack):
    for r in (0.0, 0.99):
        on = wardrobe(pack, "hoodie_black", "day", r, hood=True)
        off = wardrobe(pack, "hoodie_black", "night", r, hood=False)
        assert on.decide_hood("walk", "day") and not off.decide_hood("walk", "night")
    off = wardrobe(pack, "hoodie_black", "night", 0.0, hood=False)
    assert not off.has("walk_music")  # "hech qachon": qora xudida walk_music tanlanmaydi
    assert off.has("walk") and off.has("walk_pocket")


def test_look_for_walk_never_picks_hood_by_itself(pack):
    for outfit in ("hoodie_black", "hoodie_silver"):
        w = Wardrobe.from_pack(pack, rng=random.Random(1), overrides=Overrides(outfit=outfit))
        w.update_period("night")
        looks = {w.look_for("walk").outfit for _ in range(200)}
        assert looks == {outfit}
        assert {w.dress("walk").outfit for _ in range(50)} == {outfit}
    # type va music avvalgidek (kapyushonli look'lar o'z rasmi)
    w = wardrobe(pack, "hoodie_black")
    assert w.look_for("type").outfit == "hood_black"


# --- ketma-ketlik ---------------------------------------------------------------------------------


def hooded_sim(meta, outfit, seed=4):  # noqa: F811
    """Kechasi, xudida, "kapyushon: har doim"; Yue joyida turibdi (suhbat oynasi ochiq —
    ketma-ketlikdan keyin boshqa faoliyat tanlanmaydi)."""
    sim = Sim(meta, period="night", seed=seed, outfit=outfit).run(3)
    sim.bh.wardrobe.overrides.hood = True
    sim.bh.set_focus(sim.t, True)
    sim.run(3)
    assert sim.bh.step.slot == "idle"
    sim.visuals.clear()
    sim.events.clear()
    return sim


def runs(visuals):
    out = []
    for v in visuals:
        key = (v.slot, v.look.outfit)
        if not out or out[-1] != key:
            out.append(key)
    return out


def test_black_hood_sequence(meta):  # noqa: F811
    sim = hooded_sim(meta, "hoodie_black")
    sim.bh.perform(sim.t, "walk")
    plan = [(s.slot, s.look.outfit if s.look else None) for s in [sim.bh.step, *sim.bh.plan]]
    assert plan == [("hood_up", "hood_black"), ("walk", "hood_black"), ("hood_down", "hood_black")]
    walk_step = sim.bh.plan[0]
    clip = meta.variant("hood_up", "hood_black")
    assert walk_step.frame0 == clip.walk_frame
    x0 = sim.body.x
    sim.run(clip.frames / clip.fps - 0.1)
    assert sim.body.x == x0  # hood_up joyida — oyna qimirlamaydi
    sim.run(40)
    seq = runs(sim.visuals)
    i = seq.index(("hood_up", "hood_black"))
    assert seq[i : i + 4] == [
        ("hood_up", "hood_black"),
        ("walk", "hood_black"),
        ("hood_down", "hood_black"),
        (seq[i + 3][0], "hoodie_black"),
    ]
    first_walk = next(v for v in sim.visuals if v.slot == "walk")
    assert first_walk.frame == clip.walk_frame and first_walk.fade_from is None  # sakrashsiz
    up = [v for v in sim.visuals if v.slot == "hood_up"]
    down = [v for v in sim.visuals if v.slot == "hood_down"]
    assert up[0].frame == 0 and up[0].fade_from is not None  # turgan Yue → yurish pozasi
    assert up[0].fade_from.look.outfit == "hoodie_black" and up[0].fade_from.slot != "hood_up"
    assert down[0].frame == clip.frames - 1 and down[-1].frame == 0  # teskari
    # yurish butun sikl: yana klip oxiriga mos kadrda tugaydi — hood_down sakrashsiz boshlanadi
    n = meta.variant("walk", "hood_black").frames
    last_walk = [v for v in sim.visuals if v.slot == "walk"][-1]
    assert (clip.walk_frame - last_walk.frame) % n in (0, 1)
    last_down = max(i for i, v in enumerate(sim.visuals) if v.slot == "hood_down")
    after = sim.visuals[last_down + 1]
    assert after.look.outfit == "hoodie_black" and after.fade_from is not None
    assert after.fade_from.slot == "hood_down" and after.fade_from.frame == 0
    assert {v.mirror for v in up} == {v.mirror for v in sim.visuals if v.slot == "walk"}


def test_hood_clip_mirrors_when_walking_left(meta):  # noqa: F811
    sim = hooded_sim(meta, "hoodie_black")
    sim.body.x = 1885  # o'ng chetda — chapga yuradi
    sim.bh.perform(sim.t, "walk")
    assert not sim.bh.face_right
    sim.run(0.5)
    assert sim.visuals[-1].slot == "hood_up" and sim.visuals[-1].mirror


def test_silver_hood_crossfades(meta):  # noqa: F811
    assert meta.variant("hood_up", "hood_silver") is None  # klip hali yo'q
    sim = hooded_sim(meta, "hoodie_silver")
    sim.bh.perform(sim.t, "walk")
    step = sim.bh.step
    assert step.slot == "walk" and step.look.outfit == "hood_silver" and step.fade_in == CROSSFADE
    after = sim.bh.plan[0]
    assert after.look.outfit == "hoodie_silver" and after.fade_in == CROSSFADE
    sim.run(0.1)
    vis = sim.visuals[-1]
    assert vis.fade_from is not None and vis.fade_from.look.outfit == "hoodie_silver"
    sim.run(30)
    seq = runs(sim.visuals)
    i = seq.index(("walk", "hood_silver"))
    assert seq[i + 1] == ("idle", "hoodie_silver")
    assert "hood_up" not in [s for s, _ in seq] and "hood_down" not in [s for s, _ in seq]


@pytest.mark.parametrize("reaction", ["drag", "talk", "wave"])
def test_reaction_cancels_hood(meta, reaction):  # noqa: F811
    sim = hooded_sim(meta, "hoodie_black")
    sim.bh.perform(sim.t, "walk")
    clip = meta.variant("hood_up", "hood_black")
    sim.run(clip.frames / clip.fps + 0.5)  # yurish boshlandi
    assert sim.bh.step.slot == "walk" and sim.bh.look.outfit == "hood_black"
    if reaction == "drag":
        sim.bh.start_drag(sim.t)
    elif reaction == "talk":
        sim.bh.set_talking(sim.t, True)
    else:
        sim.bh.play(sim.t, "wave")
    assert sim.bh.look.outfit == "hoodie_black"
    assert all(s.slot != "hood_down" for s in sim.bh.plan)
    sim.visuals.clear()
    if reaction == "drag":
        sim.bh.end_drag(0, 0)
    sim.run(8)
    assert all(v.slot != "hood_down" for v in sim.visuals)
    assert all(v.look.outfit != "hood_black" for v in sim.visuals[:20])
