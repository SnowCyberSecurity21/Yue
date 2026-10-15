"""15-okt (1-bosqich): xudilarga reaksiyalar, kumushga ifodalar — to'plamda va ilovada."""

import statistics

import pytest
from PySide6.QtGui import QImage

from tests.test_behavior import Sim, meta  # noqa: F401 — fixture

HOODIES = ("hoodie_black", "hoodie_silver")
NEW_SHEETS = {"dangle": 6, "fall": 4, "land": 8, "excited_jump": 6, "wave": 6}
OPEN_R = 18  # qo'l va barmoqlar (ingichka) olib tashlanadi, bosh qoladi
HEAD_ROWS = 110  # figura tepasidan shuncha qator — bosh


@pytest.mark.parametrize("look", HOODIES)
@pytest.mark.parametrize(("slot", "frames"), sorted(NEW_SHEETS.items()))
def test_new_hoodie_sheets(meta, slot, frames, look):  # noqa: F811
    v = meta.variant(slot, look)
    assert v is not None and v.frames == frames
    raw = meta.raw["slots"][slot]["variants"][look]
    assert raw["file"] == f"{look}/{slot}.png"
    assert set(meta.slots[slot].variants) >= {"tee", "hoodie_black", "hoodie_silver"}


def test_silver_expressions(meta):  # noqa: F811
    v = meta.variant("expressions", "hoodie_silver")
    assert [s.frames for s in v.strips] == [8, 8]
    assert v.names == meta.variant("expressions", "tee").names
    rules = " ".join(meta.raw["wardrobe"]["rules"])
    assert "Expressions exist for all three outfits" in rules


def _mask(img: QImage, i: int, fw: int) -> list[int]:
    """Kadr i: har qator — bitmask (alfa > 128)."""
    bpl = img.bytesPerLine()
    data = bytes(img.constBits())[: bpl * img.height()]
    rows = []
    for y in range(img.height()):
        bits = 0
        line = data[y * bpl + i * fw * 4 + 3 : y * bpl + (i + 1) * fw * 4 : 4]
        for x, a in enumerate(line):
            if a > 128:
                bits |= 1 << x
        rows.append(bits)
    return rows


def _open(rows: list[int], r: int) -> list[int]:
    """Morfologik ochish (kvadrat 2r+1): avval eroziya, keyin kengaytirish."""

    def h(rows, op):
        out = []
        for b in rows:
            acc = b
            for k in range(1, r + 1):
                acc = op(op(acc, b << k), b >> k)
            out.append(acc)
        return out

    def v(rows, op, empty):
        n = len(rows)
        out = []
        for y in range(n):
            acc = rows[y]
            for k in range(1, r + 1):
                acc = op(acc, rows[y - k] if y - k >= 0 else empty)
                acc = op(acc, rows[y + k] if y + k < n else empty)
            out.append(acc)
        return out

    def land(a, b):
        return a & b

    def lor(a, b):
        return a | b

    eroded = v(h(rows, land), land, 0)
    return v(h(eroded, lor), lor, 0)


def head_width(meta, slot, look) -> float:  # noqa: F811
    """Bosh kengligi: qo'llarsiz figura tepasidagi qatorlar kengligining medianasi (kadrlar bo'yicha)."""
    strip = meta.variant(slot, look).strips[0]
    img = QImage(str(meta.path(strip))).convertToFormat(QImage.Format.Format_ARGB32)
    out = []
    for i in range(strip.frames):
        rows = _open(_mask(img, i, strip.frame_width), OPEN_R)
        top = next(y for y, b in enumerate(rows) if b)
        widths = [b.bit_length() - (b & -b).bit_length() for b in rows[top : top + HEAD_ROWS] if b]
        out.append(statistics.median(widths))
    return statistics.median(out)


def test_head_metric_agrees_on_standing_idle(meta):  # noqa: F811
    """O'lchovning o'zi: turgan Yue (330 px ga keltirilgan) uchala kiyimda bir xil (±3%)."""
    tee = head_width(meta, "idle", "tee")
    for look in HOODIES:
        assert abs(head_width(meta, "idle", look) / tee - 1) <= 0.03, look


@pytest.mark.parametrize("slot", ["dangle", "fall"])
def test_hoodie_dangle_fall_same_size_as_tee(meta, slot):  # noqa: F811
    """Xudidagi Yue futbolkadagidan katta ham, kichik ham emas (±3%). Pozalar har xil
    (xudida havoda o'tirgandek, futbolkada osilib) — shuning uchun bo'y emas, bosh solishtiriladi."""
    tee = head_width(meta, slot, "tee")
    for look in HOODIES:
        ratio = head_width(meta, slot, look) / tee
        assert abs(ratio - 1) <= 0.03, (look, round(ratio, 3))


# --- ilovada --------------------------------------------------------------------------------------


@pytest.mark.parametrize("outfit", HOODIES)
def test_hoodie_reactions_play_own_art(meta, outfit):  # noqa: F811
    sim = Sim(meta, seed=4, outfit=outfit).run(3)
    for slot in ("wave", "excited_jump"):
        sim.bh.play(sim.t, slot, 1.5)
        sim.run(0.5)
        vis = sim.visuals[-1]
        assert (vis.slot, vis.look.outfit) == (slot, outfit)


@pytest.mark.parametrize("outfit", HOODIES)
def test_dance_sequence_moves_in_hoodies(meta, outfit):  # noqa: F811
    """Raqs (excited_jump → wave → excited_jump → music): xudilarda ham qimirlaydi."""
    from yue.app import DANCE_STEPS

    sim = Sim(meta, seed=4, outfit=outfit).run(3)
    shown = []
    for slot, secs in DANCE_STEPS:
        if sim.bh.wardrobe.has(slot):
            sim.bh.play(sim.t, slot, secs)
        sim.run(secs)
        shown.append({v.slot for v in sim.visuals[-int(secs / 0.05) :]})
    assert "excited_jump" in shown[0] and "wave" in shown[1] and "excited_jump" in shown[2]
    frames = {v.frame for v in sim.visuals if v.slot == "excited_jump"}
    assert len(frames) > 1  # qotgan rasm emas


def test_returned_wave_in_silver(meta):  # noqa: F811
    sim = Sim(meta, seed=4, outfit="hoodie_silver").run(3)
    assert sim.bh.wardrobe.has("wave")
    sim.bh.play(sim.t, "wave", 2.5)
    sim.run(0.3)
    assert (sim.visuals[-1].slot, sim.visuals[-1].look.outfit) == ("wave", "hoodie_silver")


def test_hooded_reaction_returns_to_plain_hoodie_art(meta):  # noqa: F811
    """Kapyushonli look'da reaksiya: odatiy xudiga qaytadi va uning o'z rasmi o'ynaydi."""
    sim = Sim(meta, period="night", seed=4, outfit="hoodie_black").run(3)
    sim.bh.wardrobe.overrides.hood = True
    sim.bh.set_focus(sim.t, True)
    sim.run(3)
    sim.bh.perform(sim.t, "walk")
    clip = meta.variant("hood_up", "hood_black")
    sim.run(clip.frames / clip.fps + 0.5)
    assert sim.bh.look.outfit == "hood_black"
    sim.bh.play(sim.t, "wave", 2.0)
    sim.run(0.3)
    assert (sim.visuals[-1].slot, sim.visuals[-1].look.outfit) == ("wave", "hoodie_black")
