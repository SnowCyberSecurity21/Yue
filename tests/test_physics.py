from yue.pet.physics import (
    THROWN_SPEED,
    Body,
    Rect,
    Seg,
    WinInfo,
    build_surfaces,
    screen_for,
    subtract,
)

SCREEN = Rect(0, 0, 1920, 1040)  # 1080 - taskbar
SCREEN2 = Rect(1920, 0, 3200, 760)


def run_fall(body, surfaces, screens=(SCREEN,), max_t=5.0, dt=1 / 60):
    t = 0.0
    while t < max_t:
        speed = body.step_fall(dt, surfaces, screens, half_width=20)
        if speed is not None:
            return speed
        t += dt
    raise AssertionError("qo'nmadi")


def test_subtract():
    assert subtract([(0, 100)], 20, 30) == [(0, 20), (30, 100)]
    assert subtract([(0, 100)], -5, 200) == []
    assert subtract([(0, 100)], 100, 200) == [(0, 100)]


def test_floor_per_screen():
    segs = build_surfaces([SCREEN, SCREEN2])
    assert Seg(0, 1920, 1040, None) in segs
    assert Seg(1920, 3200, 760, None) in segs


def test_window_top_occluded_by_higher_window():
    top = WinInfo(1, Rect(300, 100, 700, 600))
    below = WinInfo(2, Rect(100, 400, 1000, 900))
    segs = build_surfaces([SCREEN], [top, below])
    mine = sorted((s.a, s.b) for s in segs if s.owner == 2)
    assert mine == [(100, 300), (700, 1000)]
    assert any(s.owner == 1 and (s.a, s.b) == (300, 700) for s in segs)


def test_maximized_and_no_headroom_windows_skipped():
    segs = build_surfaces(
        [SCREEN],
        [WinInfo(1, Rect(0, 0, 1920, 1040), maximized=True), WinInfo(2, Rect(100, 20, 500, 400))],
    )
    assert all(s.owner is None for s in segs)


def test_fall_lands_on_window_top():
    segs = build_surfaces([SCREEN], [WinInfo(7, Rect(200, 500, 900, 1000))])
    body = Body(x=400, y=100)
    body.drop()
    run_fall(body, segs)
    assert body.y == 500 and body.seg.owner == 7


def test_fall_beside_window_lands_on_floor():
    segs = build_surfaces([SCREEN], [WinInfo(7, Rect(200, 500, 900, 1000))])
    body = Body(x=1500, y=100)
    body.drop()
    run_fall(body, segs)
    assert body.y == 1040 and body.seg.owner is None


def test_hard_throw_reports_high_speed_and_walls_bounce():
    segs = build_surfaces([SCREEN])
    body = Body(x=1800, y=0)
    body.drop(vx=3000, vy=-200)
    speed = run_fall(body, segs)
    assert speed > THROWN_SPEED
    assert 20 <= body.x <= 1900


def test_falls_below_everything_lands_on_screen_floor():
    body = Body(x=500, y=900)
    body.drop()
    run_fall(body, surfaces=[])
    assert body.y == SCREEN.bottom


def test_walk_and_walk_off_edge():
    segs = build_surfaces([SCREEN], [WinInfo(7, Rect(200, 500, 900, 1000))])
    body = Body(x=400, y=500)
    body.land(next(s for s in segs if s.owner == 7), None)
    for _ in range(600):
        if body.step_walk(1 / 60, 600, 52):
            break
    assert body.x == 600 and body.grounded
    for _ in range(2000):
        body.step_walk(1 / 60, 1000, 52)
        if not body.grounded:
            break
    assert not body.grounded and body.vx > 0


def test_follow_moving_window():
    win = WinInfo(7, Rect(200, 500, 900, 1000))
    segs = build_surfaces([SCREEN], [win])
    body = Body(x=400, y=500)
    body.land(next(s for s in segs if s.owner == 7), win.rect)
    moved = WinInfo(7, win.rect.translated(150, -100))
    segs2 = build_surfaces([SCREEN], [moved])
    assert body.follow_ground(segs2, [moved]) == "moved"
    assert (body.x, body.y) == (550, 400)
    assert body.follow_ground(segs2, [moved]) == "ok"


def test_window_closed_or_covered_drops():
    win = WinInfo(7, Rect(200, 500, 900, 1000))
    segs = build_surfaces([SCREEN], [win])
    body = Body(x=400, y=500)
    body.land(next(s for s in segs if s.owner == 7), win.rect)
    cover = WinInfo(9, Rect(300, 300, 600, 800))
    segs2 = build_surfaces([SCREEN], [cover, win])
    assert body.follow_ground(segs2, [cover, win]) == "lost"
    assert not body.grounded

    body.land(Seg(0, 1920, 1040, None), None)
    assert body.follow_ground(build_surfaces([SCREEN]), []) == "ok"


def test_screen_for_gap_picks_nearest():
    assert screen_for(100, 100, [SCREEN, SCREEN2]) == SCREEN
    assert screen_for(2500, 900, [SCREEN, SCREEN2]) == SCREEN2
