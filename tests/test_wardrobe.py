import json
import random
from collections import Counter

import pytest

from yue import paths
from yue.pet.wardrobe import (
    GLASSES,
    PHONES_HEAD,
    PHONES_NECK,
    Overrides,
    Wardrobe,
    period_for_hour,
)


@pytest.fixture(scope="module")
def pack():
    """Asosiy to'plam (v4)."""
    return json.loads((paths.DEFAULT_PACK / "pack.json").read_text(encoding="utf-8"))


def make(pack, seed=1, **kw):
    w = Wardrobe.from_pack(pack, rng=random.Random(seed), **kw)
    w.update_period("day")
    return w


@pytest.mark.parametrize(
    ("hour", "period"),
    [
        (0, "night"),
        (5, "night"),
        (6, "morning"),
        (11, "morning"),
        (12, "day"),
        (17, "day"),
        (18, "evening"),
        (21, "evening"),
        (22, "night"),
        (23, "night"),
    ],
)
def test_period_for_hour(hour, period):
    assert period_for_hour(hour) == period


def test_base_outfit_only_changes_on_period_change(pack):
    w = make(pack)
    first = w.base_outfit
    for _ in range(200):
        w.dress("walk")
        assert w.base_outfit == first
    assert w.update_period("day") is False
    assert w.update_period("night") is True


def test_outfit_distribution_follows_period(pack):
    w = make(pack, seed=7)
    for period, expect_top in (("day", "tee"), ("night", "hoodie_black")):
        w.period = period
        counts = Counter(w.reroll_base() for _ in range(3000))
        assert counts.most_common(1)[0][0] == expect_top
        weights = pack["wardrobe"]["outfit_weights"][period]
        for outfit, p in weights.items():
            assert abs(counts[outfit] / 3000 - p) < 0.05


# --- v4: look'lar ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("outfit", "look"),
    [("tee", "tee_glasses"), ("hoodie_black", "hood_black"), ("hoodie_silver", "hood_silver")],
)
def test_v4_type_look_per_outfit(pack, outfit, look):
    w = make(pack)
    w.base_outfit = outfit
    for _ in range(20):
        got = w.dress("type")
        assert got.outfit == look and got.base_outfit == outfit
        assert w.base_outfit == outfit  # kiyim almashmaydi


def test_v4_look_matches_outfit_for_every_slot(pack):
    w = make(pack, seed=2)
    for outfit in pack["wardrobe"]["base_outfits"]:
        w.base_outfit = outfit
        for slot in pack["slots"]:
            look = w.look_for(slot)
            if look is None:
                continue
            assert pack["looks"][look.outfit]["outfit"] == outfit, (slot, outfit)


def test_v4_random_choice_between_several_looks(pack):
    w = make(pack, seed=3)
    w.base_outfit = "tee"
    assert w.look_names("walk_music") == ["tee_phones"]
    # Sun'iy ikkinchi variant: ikkalasi ham tanlanadi.
    slots = {**pack["slots"]}
    slots["walk_music"] = {
        **slots["walk_music"],
        "variants": {**slots["walk_music"]["variants"], "tee": {"file": "x"}},
    }
    w.slots = slots
    assert {w.dress("walk_music").outfit for _ in range(60)} == {"tee", "tee_phones"}


def test_v4_missing_variant_keeps_outfit(pack):
    w = make(pack)
    w.base_outfit = "hoodie_silver"
    assert not w.has("walk_music") and not w.has("tea")
    assert w.has("dangle")  # 15-okt: kumushda ham reaksiyalar bor
    assert w.look_for("tea") is None
    assert w.dress("tea").outfit == "hoodie_silver"  # idle look, kiyim o'zgarmaydi
    assert w.base_outfit == "hoodie_silver"


def test_v4_accessories_from_look(pack):
    w = make(pack)
    hood = w.make_look("hood_black")
    assert hood.hood and hood.base_outfit == "hoodie_black" and hood.overlays == ()
    assert set(hood.accessories) == {GLASSES, PHONES_HEAD}
    assert w.make_look("hoodie_black").accessories == (GLASSES, PHONES_NECK)
    assert w.make_look("tee").accessories == ()


@pytest.mark.parametrize(("period", "want"), [("night", "hoodie_black"), ("day", "hoodie_silver")])
def test_v4_sleep_moves_tee_to_hoodie(pack, period, want):
    w = make(pack)
    w.period = period
    w.base_outfit = "tee"
    assert w.ensure_base_for("sleep") is True
    assert w.base_outfit == want
    assert w.dress("sleep").outfit == want
    assert w.ensure_base_for("sleep") is False


def test_v4_manual_outfit_only(pack):
    w = make(pack, overrides=Overrides(outfit="hoodie_black", glasses=False, phones="none"))
    w.update_period("morning")
    assert w.base_outfit == "hoodie_black"
    # v4 da ko'zoynak/quloqchin majburlanmaydi — rasmdagi look ishlatiladi
    assert w.dress("type").outfit == "hood_black"
