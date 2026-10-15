import pytest
from PySide6.QtGui import QImage, QImageReader

from yue import paths
from yue.pet.pack import PackError, load_pack
from yue.pet.sprites import SpriteStore, visible_box


@pytest.fixture(scope="module")
def meta():
    return load_pack(paths.DEFAULT_PACK)


def test_pack_meta(meta):
    assert meta.version == 4
    assert meta.outfits == ("tee", "hoodie_black", "hoodie_silver")
    assert meta.layers == ("base",)
    assert len(meta.looks) == 7
    assert meta.looks["hood_black"].outfit == "hoodie_black" and meta.looks["hood_black"].hood
    assert meta.scale_for(1.0) == pytest.approx(0.5)  # 330 px lenta → 165 px ekranda
    sleep = meta.variant("sleep", "hoodie_black").strips[0]
    raw = meta.raw["slots"]["sleep"]["variants"]["hoodie_black"]
    assert (sleep.frame_width, sleep.frame_height) == (raw["frame_width"], raw["frame_height"])
    assert sleep.frame_width > sleep.frame_height  # yonboshlab yotadi — keng kadr
    assert meta.slots["sleep"].pose == "lying"
    assert meta.slots["walk"].faces_right and not meta.slots["idle"].faces_right
    assert meta.slots["type"].sit and meta.slots["dangle"].kind == "reaction"
    assert meta.variant("expressions", "tee").frames == 16


def test_every_variant_file_has_expected_size(meta):
    """Har variant fayli bor: kenglik = kadrlar × kadr eni, balandlik = kadr bo'yi; foot_y ichida."""
    checked = set()
    for info in meta.slots.values():
        for variant in info.variants.values():
            for s in variant.strips:
                if s.file in checked:
                    continue
                path = meta.path(s)
                assert path.is_file(), path
                size = QImageReader(str(path)).size()
                assert size.width() == s.frames * s.frame_width, s.file
                assert size.height() == s.frame_height, s.file
                assert 0 < s.foot_y <= s.frame_height, s.file
                if s.names:
                    assert len(s.names) == s.frames, s.file
                checked.add(s.file)
    files = set()
    for s in meta.raw["slots"].values():
        for v in s.get("variants", {}).values():
            files.update(x["file"] for x in v.get("sheets", [v]))
    assert checked == files and len(files) >= 39


def test_sit_and_standup_come_from_sitdown(meta):
    sitdown, sit, standup = (meta.slots[n] for n in ("sitdown", "sit", "standup"))
    for look in ("tee", "hoodie_black", "hoodie_silver"):
        assert sit.variants[look] == sitdown.variants[look]
        assert standup.variants[look] == sitdown.variants[look]
    n = sitdown.frames
    assert sit.frame_at(0) == sit.frame_at(5.0) == n - 1
    assert standup.reverse and standup.fps == 12 and not standup.loop
    assert standup.frame_at(0) == n - 1 and standup.frame_at(10) == 0
    assert standup.duration() == pytest.approx(n / 12)


def test_expression_map_resolves(meta):
    for tag in meta.raw["expression_map"]:
        for look in ("tee", "hoodie_black", "hoodie_silver"):
            assert meta.expression_frame(look, tag) is not None, (tag, look)
            # ro'yxatdagi birinchi mavjud nom tanlanadi
            names = meta.variant("expressions", look).names
            first = next(n for n in meta.raw["expression_map"][tag] if n in names)
            assert names[meta.expression_frame(look, tag)] == first


def test_bad_pack_version(tmp_path):
    (tmp_path / "pack.json").write_text('{"version": 2}', encoding="utf-8")
    with pytest.raises(PackError):
        load_pack(tmp_path)


def test_yue_pack_env(monkeypatch):
    monkeypatch.delenv("YUE_PACK", raising=False)
    assert paths.pack_dir() == paths.DEFAULT_PACK
    monkeypatch.setenv("YUE_PACK", "yue")
    assert paths.pack_dir() == paths.PACKS_DIR / "yue"
    for bad in ("..\\..", "yo'q", "nonexistent"):
        monkeypatch.setenv("YUE_PACK", bad)
        assert paths.pack_dir() == paths.DEFAULT_PACK


def opaque(img):
    return sum(
        1
        for x in range(0, img.width(), 3)
        for y in range(0, img.height(), 3)
        if img.pixelColor(x, y).alpha() > 200
    )


def test_load_frames_scaled(qapp, meta):
    store = SpriteStore(meta, k=0.5)
    idle = meta.variant("idle", "tee")
    store.load_now(idle)
    s = idle.strips[0]
    frames = store.frames(s)
    assert len(frames) == s.frames
    assert (frames[0].width(), frames[0].height()) == (
        round(s.frame_width * 0.5),
        round(s.frame_height * 0.5),
    )
    assert opaque(frames[0]) > 500
    assert store.frame(idle, 3) is frames[3]
    store.shutdown()


def test_expressions_two_strips(qapp, meta):
    store = SpriteStore(meta, k=0.25)
    ex = meta.variant("expressions", "hoodie_black")
    store.load_now(ex)
    assert store.ready(ex)
    first = ex.strips[0].frames
    assert ex.locate(first) == (ex.strips[1], 0)  # kadr raqami lentalar bo'ylab davom etadi
    assert store.frame(ex, first) is store.frames(ex.strips[1])[0]
    assert store.frame(ex, first - 1) is store.frames(ex.strips[0])[-1]
    store.shutdown()


def test_standup_uses_sitdown_strip(qapp, meta):
    store = SpriteStore(meta, k=0.25)
    store.load_now(meta.variant("standup", "tee"))
    assert store.ready(meta.variant("sitdown", "tee"))
    store.shutdown()


def test_lru_budget(qapp, meta):
    store = SpriteStore(meta, k=0.25, budget=1)
    idle, walk = meta.variant("idle", "tee"), meta.variant("walk", "tee")
    store.load_now(idle)
    store.load_now(walk)
    assert store.ready(walk)
    assert not store.ready(idle)
    store.shutdown()


def test_async_request(qtbot, meta):
    store = SpriteStore(meta, k=0.3)
    typ = meta.variant("type", "hood_black")
    with qtbot.waitSignal(store.loaded, timeout=10_000):
        store.request(typ)
    assert store.ready(typ)
    store.set_k(0.31)
    assert not store.ready(typ)
    store.shutdown()


def test_visible_box(qapp, meta):
    img = QImage(20, 10, QImage.Format.Format_ARGB32)
    img.fill(0)
    for x in range(5, 9):
        img.setPixelColor(x, 3, img.pixelColor(0, 0).fromRgb(255, 0, 0, 255))
    assert visible_box(img) == (5, 3, 9, 4)
    store = SpriteStore(meta)
    dangle = meta.variant("dangle", "tee")
    left, top, right, bottom = store.box(dangle, 0)
    s = dangle.strips[0]
    assert 0 <= left < right <= s.frame_width and 0 <= top < bottom <= s.frame_height
    store.shutdown()


def test_strip_boxes_match_frame_by_frame(qapp, meta):
    """Lenta dekodida hamma kadr `box` i birdan hisoblanadi — kadrma-kadr bilan bir xil."""
    store = SpriteStore(meta, k=0.25)
    walk = meta.variant("walk", "tee")
    store.load_now(walk)
    s = walk.strips[0]
    reader = QImageReader(str(meta.path(s)))
    full = reader.read()
    for i in (0, 7, s.frames - 1):
        assert store.box(walk, i) == visible_box(
            full.copy(i * s.frame_width, 0, s.frame_width, 999)
        )
    store.shutdown()


@pytest.mark.parametrize("k", [0.5, 0.5 * 1.25 * 1.25, 1.0])
def test_budget_fits_current_outfit_walks(qapp, meta, k):
    """Joriy kiyimning hamma yurishlari (va asosiy slotlari) LRU byudjetiga sig'adi."""
    store = SpriteStore(meta, k=k)
    for look in ("tee", "tee_phones"):
        for slot in ("idle", "talk", "walk", "walk_music", "dangle", "fall", "land"):
            v = meta.variant(slot, look)
            if v is not None:
                store.load_now(v)
    walks = [meta.variant("walk", "tee"), meta.variant("walk_music", "tee_phones")]
    assert all(store.ready(v) for v in walks)
    assert store.cached_bytes <= store.budget
    store.shutdown()
