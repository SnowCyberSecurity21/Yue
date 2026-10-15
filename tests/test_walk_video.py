"""Videodan olingan yurishlar: variant fps i, o'zgarmas tezlik, tempo va crossfade egri chizig'i."""

import pytest

from tests.test_behavior import Sim, meta  # noqa: F401 — fixture
from yue.commands import Commands
from yue.pet.behavior import clamp_tempo, crossfade_alphas

VIDEO_WALKS = [  # (slot, look, kadrlar, speed) — pack.json dagi qiymatlar
    ("walk", "tee", 26, 163.6),
    ("walk", "hoodie_black", 27, 140.4),
    ("walk", "hoodie_silver", 25, 170.4),
    ("walk_music", "tee_phones", 38, 122.9),  # 14-oktabrda qayta yasaldi
    ("walk_music", "hood_black", 27, 155.0),
    ("walk_pocket", "hoodie_black", 28, 153.5),
    ("walk", "hood_silver", 25, 162.0),
]
HZ = 60


def test_variant_fps_overrides_slot_and_frames_from_pack(meta):  # noqa: F811
    raw = meta.raw["slots"]
    for slot, look, frames, speed in VIDEO_WALKS:
        v = meta.variant(slot, look)
        d = raw[slot]["variants"][look]
        strip = v.strips[0]
        assert v.frames == d["frames"] == frames
        size = (strip.frame_width, strip.frame_height, strip.foot_y)
        assert size == (d["frame_width"], d["frame_height"], d["foot_y"])
        assert v.speed == speed and v.fps == 18.0 != meta.slots[slot].fps
        assert meta.slots[slot].fps_of(v) == 18.0


def walk(meta, slot, outfit, period="day", size=1.0, tempo=1.0, seconds=1.0, hood=False):  # noqa: F811
    """Yurishni boshlab, 60 Hz da `seconds` yuradi → (qadam, [(t, x, kadr, ko'zgu)]).

    `hood` — kapyushonli look bilan (hood_up klipi o'tkazib yuboriladi)."""
    sim = Sim(meta, period=period, seed=3, outfit=outfit).run(3)
    bh = sim.bh
    bh.scale, bh.walk_tempo = size, tempo
    bh.wardrobe.overrides.hood = hood
    bh.perform(sim.t, slot)
    while bh.step is not None and bh.step.slot == "hood_up":
        bh._advance(sim.t)
    step = bh.step
    assert step is not None and step.slot == slot and step.mode == "walk"
    # Uzoqroq yursin (ekranning keng tomoniga).
    bh.face_right = sim.body.x < 960
    step.target_x = sim.body.x + (700 if bh.face_right else -700)
    out = []
    t0 = sim.t
    for i in range(1, round(seconds * HZ) + 1):
        now = t0 + i / HZ
        vis = bh.tick(now)
        assert bh.step is step
        out.append((now - bh.step_t0, sim.body.x, vis.frame, vis.mirror))
    return step, out


@pytest.mark.parametrize("size", [1.0, 1.25])
@pytest.mark.parametrize(("slot", "look", "frames", "speed"), VIDEO_WALKS)
def test_video_walk_moves_at_constant_speed(meta, slot, look, frames, speed, size):  # noqa: F811
    step, out = walk(meta, slot, meta.looks[look].outfit, size=size, hood=meta.looks[look].hood)
    assert step.look is not None and step.look.outfit == look
    expected = speed * meta.scale_for(size)  # lenta px/s × chizish masshtabi (0.5 × o'lcham)
    assert step.speed == pytest.approx(expected)
    assert 60 <= speed * meta.scale_for(1.0) <= 86  # 100% da ekranda ~60–85 px/s
    # x(t) chiziqli: har tikda bir xil siljish; bir soniyada — speed × masshtab
    xs = [x for _, x, _, _ in out]
    deltas = [b - a for a, b in zip(xs, xs[1:], strict=False)]
    assert all(abs(abs(d) - expected / HZ) < 1e-6 for d in deltas)
    assert abs(xs[-1] - xs[0]) == pytest.approx(expected * (len(xs) - 1) / HZ)
    # kadr = floor(t × fps) mod kadrlar: 0 dan (hood_up dan keyin — `frame0` dan) boshlanadi,
    # sakramaydi (+1 yoki aylanib 0)
    f0 = step.frame0
    assert all(f == int((t + f0 / 18) * 18) % frames for t, _, f, _ in out)
    seen = [f for _, _, f, _ in out]
    assert seen[0] == f0 and set(seen) == {(f0 + k) % frames for k in range(19)}  # 1 s da 18 fps
    assert all((b - a) % frames in (0, 1) for a, b in zip(seen, seen[1:], strict=False))
    # chapga yurganda rasm ko'zgulanadi
    left = deltas[0] < 0
    assert all(m == left for _, _, _, m in out)


def test_walk_tempo_scales_fps_and_speed_together(meta):  # noqa: F811
    base, _ = walk(meta, "walk", "tee", tempo=1.0)
    fast, out = walk(meta, "walk", "tee", tempo=1.2)
    assert fast.speed == pytest.approx(base.speed * 1.2)
    assert all(f == int(t * 18 * 1.2) % 26 for t, _, f, _ in out)  # fps ham ×1.2
    xs = [x for _, x, _, _ in out]
    assert abs(xs[-1] - xs[0]) == pytest.approx(fast.speed * (len(xs) - 1) / HZ)
    assert clamp_tempo(2.0) == 1.3 and clamp_tempo(0.1) == 0.7 and clamp_tempo("x") == 1.0


def test_sayr_uses_video_walk(meta):  # noqa: F811
    sim = Sim(meta, period="day", seed=4, outfit="tee").run(3)
    spec = Commands.load().get("sayr")
    assert spec is not None
    sim.bh.run_command(sim.t, spec)
    sim.run(0.5)
    step = sim.bh.step
    assert step is not None and step.slot == "walk" and step.mode == "walk"
    assert step.speed == pytest.approx(163.6 * meta.scale_for(1.0))


def test_crossfade_alphas_never_dim():
    assert crossfade_alphas(0.0) == (1.0, 0.0)
    assert crossfade_alphas(0.5) == (1.0, 1.0)
    assert crossfade_alphas(1.0) == (0.0, 1.0)
    for i in range(11):
        assert max(crossfade_alphas(i / 10)) == 1.0  # hech bir paytda ikkalasi ham xira emas
