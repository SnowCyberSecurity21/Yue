"""Yuening xatti-harakati: holat mashinasi va faoliyat rejalashtiruvchi.

Qt'ga bog'liq emas. Vaqt (`now`, monotonic soniyalar) va tasodif (`rng`) tashqaridan beriladi.
Har `tick()` da jism (`Body`) yangilanadi va chizish uchun `Visual` qaytariladi.

Harakat = qadamlar rejasi. Masalan `type`: sitdown (bir marta) → type (vaqt) → standup.
Uxlash: sitdown → ~250 ms crossfade → sleep; uyg'onish: crossfade → sit → standup.

Yurish: variantda `speed` bo'lsa (videodan olingan lentalar) — o'zgarmas tezlik
speed × chizish masshtabi, kadr esa floor(t × fps) mod kadrlar; `walk_tempo` ikkalasini bir xil
ko'paytiradi (oyoq sirpanmaydi). `speed` siz variantlar — `walk_speed` × `WALKS` nisbati.

Kapyushonli yurish (xudida, `Wardrobe.decide_hood`): joyida hood_up → kapyushonli look bilan
yurish (klip oxiriga mos `walk_frame` dan) → joyida hood_down → odatiy xudi look'i. Look'da
hood_up klipi bo'lmasa (kumush) — ~250 ms crossfade. Ketma-ketlik o'rtasida reaksiya
(sudrash, gap, silash...) — kapyushon bekor: hood_down o'ynamasdan odatiy look'ga (`restore`).

Bir martalik reaksiyalar (`KEEP_SLOTS`: land, wave, excited_jump, angry_stomp) gap boshlansa ham
oxirigacha o'ynaydi: pufak va ovoz darhol chiqadi, faqat talk animatsiyasi kutadi. Reaksiya
tugaganda gap davom etayotgan bo'lsa — talk, tugagan bo'lsa — gapdan keyingi ifoda (after_talk).

Buyruq qatlami (`run_command`, `persona/harakatlar.json`): foydalanuvchi aytgan harakat o'z-o'zidan
faoliyatni to'xtatib boshlanadi; gapirish uni to'xtatmaydi, sudrash/otish/yiqilish bekor qiladi.
Joriy kiyimda rasmi bo'lmasa — buyruq uchun kiyim almashadi (kun qismiga mosrog'i), `time`
cheklovi hisobga olinmaydi. Sayr — maxsus: turgan yuzasi bo'ylab yuradi, 15–30 s da to'xtab
gapiradi.

Nima chiziladi (`resolve`): slotning joriy look'dagi rasmi; bo'lmasa joriy asosiy kiyimdagi
boshqa look; bo'lmasa `fallback` (boshqa slot yoki `expressions:<teg>`), agar uning joriy kiyimda
rasmi bo'lsa; u ham bo'lmasa — joriy kiyim `idle` ining birinchi kadri. Reaksiya kiyimni hech
qachon almashtirmaydi.
"""

from __future__ import annotations

import random
from collections import deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from typing import Literal

from yue.commands import CommandSpec
from yue.pet.pack import PackMeta, SlotInfo, Variant
from yue.pet.physics import THROWN_SPEED, WALK_SPEED, Body, Rect, Seg, WinInfo
from yue.pet.wardrobe import Look, Period, Wardrobe

StepMode = Literal["once", "time", "walk", "forever"]

SEATED = frozenset({"sitdown", "sit", "type", "sleep"})
HOOD_BACK_S = 0.6  # klipsiz look: crossfade bilan kapyushon yechilgach joyida turish
HOOD_FADE = 0.2  # turgan Yue → hood_up 1-kadri (yurish pozasi) va hood_down oxiri → keyingi holat
# `speed` siz (eski, 8 kadrli) yurish variantlari uchun nisbiy tezlik
# (asosiy tezlik — `Behavior.walk_speed`, config: pet.walk_speed).
# Tayanch oyoq siljishidan o'lchangan (sirpanish eng kam): walk ~52, walk_music ~42–49,
# walk_pocket ~48 mantiqiy px/s — asos 50 da 50 / 45 / 47.5.
WALKS = {"walk": 1.0, "walk_music": 0.9, "walk_pocket": 0.95}
LOOP_SECONDS: dict[str, tuple[float, float]] = {
    "idle": (3.0, 8.0),
    "look_around": (5.0, 10.0),
    "butterfly": (6.0, 12.0),
    "music": (12.0, 35.0),
    "ponder": (8.0, 18.0),
    "train": (5.0, 10.0),
    "wave": (2.0, 3.0),
    "excited_jump": (1.5, 2.5),
    "angry_stomp": (1.6, 2.4),
}
SEATED_SECONDS = {"sit": (8.0, 30.0), "type": (20.0, 70.0)}
NAP_SECONDS = (60.0, 200.0)
CROSSFADE = 0.25
WALK_TEMPO = (0.7, 1.3)  # pet.walk_tempo oralig'i: yurish fps i va tezligi birga ko'payadi
HOLD_END = 1.0  # `loop: false` slot oxirgi kadrda shuncha turadi (sitdown, flower, tea, stretch)
HELD_FRAME = 2.0  # rasm yo'q — ifoda yoki idle kadri "once" qadamda shuncha ushlab turiladi
BLINK_FPS = 12.0  # ko'z yumib-ochish kadrlari tezroq (~0.25 s), rest kadrlari odatdagi fps da
LAND_MIN_AIR = 0.25  # havoda shundan kam bo'lsa (fall'ning ~2 kadri) — `land` o'ynamaydi
EDGE_WALK_OFF = 0.12  # oyna ustida yurganda chetidan tushib ketish ehtimoli
UNTIL_NEXT_MAX = 600.0  # "keyingi_buyruqgacha" — ko'pi bilan 10 daqiqa, keyin odatiy hayot
SAYR_STOP_EVERY = (15.0, 30.0)  # sayrda yurish vaqti to'xtashlar orasida
SAYR_STOP_S = 4.0  # to'xtab gapirish
SAYR_LAUGH = 0.3  # to'xtashlarning shu qismida — kulish (happy ifoda)
# Gap boshlansa ham oxirigacha o'ynaydigan reaksiyalar (talk ularni kesmaydi)
KEEP_SLOTS = frozenset({"land", "wave", "excited_jump", "angry_stomp"})

CommandResult = Literal["ok", "outfit", "missing", "idle", "busy"]


def clamp_tempo(value: object) -> float:
    """pet.walk_tempo → 0.7…1.3 (noto'g'ri qiymat — 1.0)."""
    try:
        tempo = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 1.0
    return max(WALK_TEMPO[0], min(WALK_TEMPO[1], tempo))


def crossfade_alphas(t: float) -> tuple[float, float]:
    """Crossfade (t = 0…1): (eski, yangi) shaffofligi. Yangisi eskining ustiga chiziladi.

    O'rtada ikkalasi ham to'liq ko'rinadi — Yue bir zum ham xira bo'lmaydi.
    """
    t = max(0.0, min(1.0, t))
    return min(1.0, 2.0 * (1.0 - t)), min(1.0, 2.0 * t)


@dataclass
class Step:
    slot: str
    mode: StepMode
    seconds: float = 0.0
    target_x: float = 0.0
    speed: float = 0.0
    fade_in: float = 0.0
    look: Look | None = None
    tag: str = ""  # sayr: "sayr_stop" (to'xtab gapirish), "sayr_pause" (javob paytida)
    frame0: int = 0  # shu kadrdan boshlanadi (hood_up dan keyingi yurish)
    start_look: Look | None = None  # birinchi kadrdagi look (o'tish klipi: crossfade kerak emas)
    end_look: Look | None = None  # tugagach shu look (hood_down oxiri — odatiy xudi)
    restore: Look | None = None  # kapyushonli ketma-ketlik bekor bo'lsa — shu look'ga qaytadi
    fade_next: float = 0.0  # tugagach keyingi qadam shuncha crossfade bilan boshlanadi


def _hood_up(hooded: Look, plain: Look) -> Step:
    """Joyida kapyushon kiyish: turgan pozadan crossfade bilan (klip 1-kadri — yurish pozasi)."""
    return Step("hood_up", "once", fade_in=HOOD_FADE, look=hooded, start_look=plain, restore=plain)


def _hood_down(hooded: Look, plain: Look) -> Step:
    """Joyida kapyushon yechish; tugagach — odatiy look, keyingi holatga crossfade bilan."""
    return Step(
        "hood_down", "once", look=hooded, end_look=plain, restore=plain, fade_next=HOOD_FADE
    )


@dataclass
class ActiveCommand:
    name: str
    mode: str
    started: float


@dataclass
class Sayr:
    end: float
    next_stop: float | None = None  # yurish davom etganda belgilanadi


@dataclass(frozen=True)
class Visual:
    slot: str  # chiziladigan slot (fallback'dan keyin)
    frame: int  # variantdagi kadr
    look: Look  # chiziladigan look
    mirror: bool = False
    fade_from: Visual | None = None
    fade: float = 1.0  # crossfade jarayoni 0…1 (shaffoflik — `crossfade_alphas`)


class Behavior:
    def __init__(
        self,
        pack: PackMeta,
        wardrobe: Wardrobe,
        body: Body,
        period_fn: Callable[[], Period],
        rng: random.Random | None = None,
        scale: float = 1.0,
        half_width: float = 30.0,
    ) -> None:
        self.pack = pack
        self.slots = pack.slots
        self.activity_weights = pack.raw["wardrobe"]["activity_weights"]
        self.wardrobe = wardrobe
        self.body = body
        self.period_fn = period_fn
        self.rng = rng or random.Random()
        self.scale = scale
        self.half_width = half_width
        self.walk_speed = WALK_SPEED  # mantiqiy px/s, o'lcham 1.0 da (`speed` siz variantlar)
        self.walk_tempo = 1.0  # yurish fps i va tezligi ko'paytiruvchisi (config: pet.walk_tempo)

        self.surfaces: Sequence[Seg] = ()
        self.screens: Sequence[Rect] = ()
        self.windows: Sequence[WinInfo] = ()

        self.plan: deque[Step] = deque()
        self.step: Step | None = None
        self.step_t0 = 0.0
        self.activity = ""
        self.look: Look = Look("tee", "tee")
        self.face_right = True
        self.dragging = False
        self.drag_t0 = 0.0
        self.released = False  # foydalanuvchi ko'tarib qo'yib yubordi (qo'nguncha)
        self.focus = False
        self.talking = False
        self._talk_wait = False  # reaksiya o'ynayapti — talk shu tugashini kutyapti
        self._talk_expr: str | None = None  # kutish paytida tugagan gapning ifodasi
        self.forced_sleep = False
        self.reroll_after = False
        self.expression = "neutral"
        self.events: list[tuple[str, object]] = []
        self.last_visual: Visual | None = None
        self.last = None  # type: float | None
        self._fade_from: Visual | None = None
        self._air_t0: float | None = None
        self.gentle_drop = False  # ekran tepasidan tushib kelish (ochilish, chaqirish) — land yo'q
        self._blink_next: float | None = None  # keyingi ko'z yumib-ochish vaqti
        self._blink_t0: float | None = None  # hozirgi ko'z yumib-ochish boshlangan vaqt
        self.command: ActiveCommand | None = None  # foydalanuvchi aytgan harakat
        self.sayr: Sayr | None = None
        self._resolved: dict[tuple[str, Look], tuple[str, Look, int | None]] = {}

    # --- holat ------------------------------------------------------------------------------

    @property
    def sleeping(self) -> bool:
        return self.step is not None and self.step.slot == "sleep" and self.body.grounded

    @property
    def seated(self) -> bool:
        return self.step is not None and self.step.slot in SEATED

    # --- nima chiziladi ---------------------------------------------------------------------

    def resolve(self, slot: str, look: Look) -> tuple[str, Look, int | None]:
        """(chiziladigan slot, look, qotirilgan kadr yoki None). Natija keshlanadi."""
        key = (slot, look)
        got = self._resolved.get(key)
        if got is None:
            got = self._resolved[key] = self._resolve(slot, look)
        return got

    def _resolve(self, slot: str, look: Look) -> tuple[str, Look, int | None]:
        meta = self.pack
        if meta.variant(slot, look.outfit) is not None:
            return slot, look, None
        base, wr = look.base_outfit, self.wardrobe
        seen: set[str] = set()
        cur = slot
        while cur and cur not in seen:
            seen.add(cur)
            if cur.startswith("expressions:"):
                tag = cur.split(":", 1)[1]
                for name in meta.looks_for("expressions", base):
                    frame = meta.expression_frame(name, tag)
                    if frame is not None:
                        return "expressions", wr.make_look(name), frame
                break
            names = meta.looks_for(cur, base)
            if names:
                return cur, wr.make_look(look.outfit if look.outfit in names else names[0]), None
            info = self.slots.get(cur)
            cur = info.fallback if info else ""
        idle = meta.looks_for("idle", base)
        if idle:
            return "idle", wr.make_look(idle[0]), 0
        return slot, look, None  # buzilgan to'plam — chizuvchi bo'sh kadrni o'tkazib yuboradi

    def expression_available(self, tag: str, look: Look | None = None) -> bool:
        """Joriy kiyimda shu teg uchun ifoda kadri bormi (15-okt dan uchala kiyimda bor)."""
        slot, lk, _ = self.resolve("expressions", look or self.look)
        return slot == "expressions" and self.pack.expression_frame(lk.outfit, tag) is not None

    def fps(self, slot: str, variant: Variant | None) -> float:
        """Chizish fps i: variantniki (bo'lsa) yoki slotniki; yurishlarda × `walk_tempo`."""
        fps = self.slots[slot].fps_of(variant)
        return fps * self.walk_tempo if slot in WALKS else fps

    def walk_speed_for(self, slot: str, look: Look) -> float:
        """Yurish tezligi (mantiqiy px/s) — chiziladigan variant bo'yicha.

        `speed` bor variant: speed × chizish masshtabi (height/standing_height × o'lcham) ×
        tempo. DPI ni Qt o'zi hisobga oladi (koordinatalar mantiqiy pikselda).
        """
        dslot, dlook, _ = self.resolve(slot, look)
        variant = self.pack.variant(dslot, dlook.outfit)
        if variant is not None and variant.speed:
            return variant.speed * self.pack.scale_for(self.scale) * self.walk_tempo
        return self.walk_speed * self.scale * WALKS.get(slot, 1.0) * self.walk_tempo

    def _duration(self, slot: str) -> float:
        """Bir martalik ("once") qadam vaqti: kadrlar / fps (+ oxirgi kadrda to'xtash)."""
        dslot, dlook, frame = self.resolve(slot, self.look)
        if frame is not None:
            return HELD_FRAME
        info = self.slots[dslot]
        variant = self.pack.variant(dslot, dlook.outfit)
        secs = info.duration(variant.frames if variant else None, self.fps(dslot, variant))
        if not info.loop and not info.reverse and info.hold is None and info.kind != "transition":
            secs += HOLD_END
        return secs

    def _reaction_look(self, slot: str) -> Look | None:
        """Reaksiya ko'rinishi: v3 — qatlam qoidalari bo'yicha; v4 — joriy ko'rinish qoladi."""
        return None if self.wardrobe.v4 else self.wardrobe.dress(slot)

    # --- boshlanish -------------------------------------------------------------------------

    def start(self, now: float) -> None:
        """Dastur ochilganda: kun qismi bo'yicha kiyim tanlanadi."""
        self.wardrobe.update_period(self.period_fn())
        self.wardrobe.reroll_base()
        self.look = self.wardrobe.adapt(self.wardrobe.dress("idle"), "fall")
        self.last = now

    def emit(self, name: str, data: object = None) -> None:
        self.events.append((name, data))

    def pop_events(self) -> list[tuple[str, object]]:
        ev, self.events = self.events, []
        return ev

    # --- tashqi buyruqlar ---------------------------------------------------------------------

    def start_drag(self, now: float) -> None:
        self.dragging = True
        self.drag_t0 = now
        self.forced_sleep = False
        self._end_command()  # sudrash buyruq va sayrni bekor qiladi
        self._drop_hood()
        self.body.drop()
        self.plan.clear()
        self.step = None
        self._talk_wait, self._talk_expr = False, None
        self.look = self.wardrobe.adapt(self.look, "dangle")
        self.emit("drag")

    def drag_to(self, x: float, y: float) -> None:
        self.body.x, self.body.y = x, y

    def end_drag(self, vx: float, vy: float) -> None:
        self.dragging = False
        self.released = True
        self.body.drop(vx, vy)
        self.look = self.wardrobe.adapt(self.look, "fall")

    def go_sleep(self, now: float, forced: bool = False) -> None:
        """Uxlash (foydalanuvchi uzoq harakatsiz yoki menyudan)."""
        self._end_command()
        self.forced_sleep = forced
        if self.sleeping:
            return
        self._drop_hood()
        changed = self.wardrobe.ensure_base_for("sleep")
        look = self.wardrobe.dress("sleep")
        steps = [Step("sleep", "forever", fade_in=CROSSFADE, look=look)]
        if not (self.step and self.step.slot in ("sit", "sitdown", "type")):
            # Kiyim almashsa (futbolka → xudi) — o'tirishga ham crossfade.
            steps.insert(0, Step("sitdown", "once", fade_in=CROSSFADE if changed else 0, look=look))
        self._replace_plan(now, steps, "sleep")

    def wake(self, now: float) -> None:
        if not self.sleeping:
            return
        if self.command is not None and self.command.mode == "uygonguncha":
            self._end_command()
        self.forced_sleep = False
        self.reroll_after = True
        self._replace_plan(
            now,
            [Step("sit", "time", 1.2, fade_in=CROSSFADE), Step("standup", "once")],
            "wake",
        )
        self.expression = "sleepy"

    def play(self, now: float, slot: str, seconds: float | None = None) -> None:
        """Bir martalik harakat (qo'l silkitish, sakrash, depsinish)."""
        if slot not in self.slots or self.dragging or not self.body.grounded:
            return
        info = self.slots[slot]
        mode: StepMode = "once" if not info.loop else "time"
        secs = seconds if seconds is not None else self.rng.uniform(*LOOP_SECONDS.get(slot, (2, 3)))
        self._interrupt(now, [Step(slot, mode, secs, look=self._reaction_look(slot))], slot)

    def show_expression(self, now: float, tag: str, seconds: float = 4.0) -> None:
        """Ifodani darhol ko'rsatish (sinov menyusi)."""
        if self.dragging or not self.body.grounded:
            return
        self.expression = tag
        self._interrupt(now, [Step("expressions", "time", seconds)], "expression")

    def set_focus(self, now: float, on: bool) -> None:
        """Suhbat oynasi ochiq — Yue to'xtab tinglaydi."""
        self.focus = on
        if self.command is not None:
            return  # buyruq (sayr ham) suhbat oynasi ochilsa ham davom etadi
        if on and not self.dragging and self.body.grounded and not self.sleeping:
            self._interrupt(now, [Step("idle", "forever")], "listen")
        elif not on and self.step and self.step.mode == "forever" and not self.sleeping:
            self.step.mode, self.step.seconds = "time", 0.0

    def set_talking(self, now: float, on: bool, expression: str | None = None) -> None:
        self.talking = on
        if self.sayr is not None:
            self._sayr_talking(now, on, expression)
            return
        if self.command is not None:
            return  # buyruq animatsiyasi gap paytida ham davom etadi (uxlasa — uyg'onmaydi)
        if on:
            if self.sleeping:
                self.wake(now)
            elif self._reaction_playing():
                self._talk_wait, self._talk_expr = True, None  # reaksiya tugagach talk
                return
            self._interrupt(now, [Step("talk", "forever")], "talk")
            return
        if self._talk_wait:
            self._talk_expr = expression  # gap reaksiya davomida tugadi — talk boshlanmaydi
            return
        if self.step and self.step.slot == "talk":
            self._after_talk(now, expression)

    def _after_talk(self, now: float, expression: str | None) -> None:
        steps: list[Step] = []
        if expression and self.expression_available(expression):
            self.expression = expression
            steps.append(Step("expressions", "time", self.rng.uniform(3.0, 5.0)))
        if self.focus:
            steps.append(Step("idle", "forever"))
        self._replace_plan(now, steps or [Step("idle", "time", 1.0)], "after_talk")

    def _reaction_playing(self) -> bool:
        step = self.step
        return (
            step is not None
            and step.slot in KEEP_SLOTS
            and step.mode in ("once", "time")
            and not step.tag
            and not self.dragging
            and self.body.grounded
        )

    def _finish_reaction(self, now: float) -> None:
        """Reaksiya tugadi, gap esa uni kutgan edi."""
        expr = self._talk_expr
        self._talk_wait, self._talk_expr = False, None
        if self.talking:
            self._replace_plan(now, [Step("talk", "forever")], "talk")
        else:
            self._after_talk(now, expr)

    # --- rejalashtirish ---------------------------------------------------------------------

    def _drop_hood(self) -> None:
        """Kapyushonli ketma-ketlik bekor (reaksiya): hood_down siz odatiy xudi look'iga."""
        step = self.step
        if step is not None and step.restore is not None:
            self.look = step.restore
            step.restore = step.end_look = None
            step.fade_next = 0.0

    def _interrupt(self, now: float, steps: list[Step], name: str) -> None:
        self._drop_hood()
        if self.sleeping:
            self.wake(now)
            self.plan.extend(steps)
            return
        staying_seated = bool(steps) and steps[0].slot in SEATED
        if self.step and self.step.slot in ("sit", "type", "sitdown") and not staying_seated:
            steps = [Step("standup", "once"), *steps]
        self._replace_plan(now, steps, name)

    def _replace_plan(self, now: float, steps: list[Step], name: str) -> None:
        self._talk_wait, self._talk_expr = False, None  # yangi reja — reaksiya kutilmaydi
        self.plan = deque(steps)
        self.activity = name
        self._advance(now)

    def _advance(self, now: float) -> None:
        self._fade_from = self.last_visual
        ended = self.step.end_look if self.step is not None else None
        fade_next = self.step.fade_next if self.step is not None else 0.0
        if ended is not None:
            self.look = ended  # o'tish klipi tugadi (hood_down): odatiy look
        if not self.plan:
            self._choose_next(now)
        self.step = self.plan.popleft()
        if fade_next > 0 and self.step.fade_in <= 0 and self.body.grounded and not self.dragging:
            self.step.fade_in = fade_next  # hood_down oxirgi kadri (yurish pozasi) → keyingi holat
        if self.step.look is not None:
            self.look = self.step.look
        self.step_t0 = now
        self._blink_next = self._blink_t0 = None
        # Look almashsa (kapyushon, ko'zoynak, quloqchin birdan paydo bo'lmasin) — crossfade:
        # oldingi slotning oxirgi kadri → yangisining birinchi kadri. O'tish klipining chetidagi
        # kadr boshqa look'ni ko'rsatadi (`start_look`, `end_look`) — u yerda crossfade yo'q.
        prev = self._fade_from
        start = self.step.start_look or self.resolve(self.step.slot, self.look)[1]
        if (
            self.step.fade_in <= 0
            and prev is not None
            and self.body.grounded
            and not self.dragging
            and start.outfit != (ended or prev.look).outfit
        ):
            self.step.fade_in = CROSSFADE
            self.emit("crossfade", (prev.look.outfit, self.step.slot))
        self.emit("step", self.step.slot)

    def _choose_next(self, now: float) -> None:
        if self.sayr is not None:
            self._sayr_next(now)
            return
        if self.command is not None:
            self._end_command()  # buyruq qadamlari tugadi — odatiy hayot
        if self.reroll_after:
            self.reroll_after = False
            self.wardrobe.reroll_base()
        period = self.period_fn()
        self.wardrobe.update_period(period)

        if self.focus:
            self.plan.append(Step("idle", "forever"))
            self.activity = "listen"
            return

        weights = self.activity_choices(period) or {"idle": 1.0}
        if self.activity in weights and len(weights) > 1:
            weights[self.activity] *= 0.3
        name = self.rng.choices(list(weights), weights=list(weights.values()), k=1)[0]
        self.activity = name
        self.emit("action", name)
        self.plan.extend(self._plan_activity(name, period))

    def activity_choices(self, period: Period) -> dict[str, float]:
        """Shu kun qismida tanlash mumkin bo'lgan faoliyatlar va og'irliklari.

        Faqat `time` ga mos va joriy kiyimda rasmi borlari (uxlash bundan mustasno — u kiyimni
        o'zi almashtiradi).
        """
        return {
            k: float(w)
            for k, w in self.activity_weights.get(period, {}).items()
            if k in self.slots
            and self.slots[k].allowed_in(period)
            and (k == "sleep" or self.wardrobe.has(k))
        }

    def _plan_activity(self, name: str, period: Period) -> list[Step]:
        """Bitta faoliyat uchun qadamlar rejasi (ko'rinish shu yerda tanlanadi)."""
        if name == "sleep":
            changed = self.wardrobe.ensure_base_for("sleep")
            look = self.wardrobe.dress("sleep")
            self.reroll_after = True
            return [
                Step("sitdown", "once", fade_in=CROSSFADE if changed else 0, look=look),
                Step("sleep", "time", self.rng.uniform(*NAP_SECONDS), fade_in=CROSSFADE),
                Step("sit", "time", 1.2, fade_in=CROSSFADE),
                Step("standup", "once"),
            ]
        info = self.slots[name]
        if info.kind == "reaction" and self.wardrobe.v4:
            look = self.look  # reaksiya kiyimni almashtirmaydi
        elif name in WALKS:
            look = self.wardrobe.dress(name, period, hood=self.wardrobe.decide_hood(name, period))
        else:
            look = self.wardrobe.dress(name, period)
        if name in WALKS:
            step = self._walk_step(name, look)
            if step is not None:
                return self._hood_walk(step, period) if look.hood else [step]
            name, look = "idle", self.wardrobe.dress("idle", period)
            info = self.slots[name]
        if name in SEATED_SECONDS or info.sit:
            secs = self.rng.uniform(*SEATED_SECONDS.get(name, SEATED_SECONDS["type"]))
            return [
                Step("sitdown", "once", look=look),
                Step(name, "time", secs),
                Step("standup", "once"),
            ]
        if info.kind == "transition":  # sinov menyusi: kapyushon kiyib-yechish joyida
            return self._hood_clip_steps(name, period)
        if name == "train":
            self.face_right = self.rng.random() < 0.5
        if info.loop:
            secs = self.rng.uniform(*LOOP_SECONDS.get(name, (4.0, 8.0)))
            return [Step(name, "time", secs, look=look)]
        return [Step(name, "once", look=look)]

    def _hood_walk(self, walk: Step, period: Period) -> list[Step]:
        """Kapyushonli yurish: hood_up → yurish → hood_down → odatiy look (klipsiz — crossfade)."""
        hooded = walk.look
        assert hooded is not None
        plain = self.wardrobe.dress("idle", period)
        walk.restore = plain
        clip = self.pack.variant("hood_up", hooded.outfit)
        if clip is None:  # klip yo'q (kumush) — crossfade bilan kiyadi va yechadi
            walk.fade_in = CROSSFADE
            return [walk, Step("idle", "time", HOOD_BACK_S, fade_in=CROSSFADE, look=plain)]
        walk_v = self.pack.variant(self.resolve(walk.slot, hooded)[0], hooded.outfit)
        loop_v = self.pack.variant("walk", hooded.outfit)
        if (
            clip.walk_frame is not None
            and walk_v is not None
            and loop_v is not None
            and walk_v.strips[0].file == loop_v.strips[0].file  # klip shu lentaga moslangan
        ):
            walk.frame0 = clip.walk_frame % walk_v.frames
            self._whole_cycles(walk, walk_v)
        return [_hood_up(hooded, plain), walk, _hood_down(hooded, plain)]

    def _whole_cycles(self, walk: Step, variant: Variant) -> None:
        """Yurish butun sikllar soni davom etsin: `frame0` da boshlanib, yana o'sha kadrda
        (hood_down ning birinchi kadri) tugaydi. Masofa ≈ avvalgisi; yuzadan chiqsa — kamroq sikl.
        Tempo tezlik va fps ni birga ko'paytiradi — bir sikl masofasi o'zgarmaydi."""
        seg = self.body.seg
        fps = self.fps(walk.slot, variant)
        if seg is None or fps <= 0 or walk.speed <= 0:
            return
        lo, hi = seg.a + self.half_width, seg.b - self.half_width
        if not lo <= walk.target_x <= hi:
            return  # chetdan tushib ketish rejalashtirilgan — kapyushon baribir bekor bo'ladi
        cycle = walk.speed * variant.frames / fps
        x, sign = self.body.x, 1.0 if walk.target_x >= self.body.x else -1.0
        k = max(1, round(abs(walk.target_x - x) / cycle))
        while k >= 1 and not lo <= x + sign * k * cycle <= hi:
            k -= 1
        if k >= 1:
            walk.target_x = x + sign * k * cycle

    def _hood_clip_steps(self, name: str, period: Period) -> list[Step]:
        """Sinov: hood_up → hood_down (yoki faqat hood_down) joyida, yurishsiz."""
        hooded = self.wardrobe.look_for("hood_up")
        if hooded is None or self.pack.variant("hood_up", hooded.outfit) is None:
            return [Step("idle", "time", 1.0)]
        plain = self.wardrobe.dress("idle", period)
        down = _hood_down(hooded, plain)
        return [down] if name == "hood_down" else [_hood_up(hooded, plain), down]

    def perform(self, now: float, name: str) -> None:
        """Faoliyatni darhol boshlash (menyu / sinov)."""
        if name not in self.slots or self.dragging or not self.body.grounded:
            return
        if name == "sleep":
            self.go_sleep(now, forced=True)
            return
        if name == "standup":
            name = "idle"
        steps = self._plan_activity(name, self.period_fn())
        if steps and steps[0].slot == "sitdown" and self.seated and not self.sleeping:
            steps = steps[1:]
        self._interrupt(now, steps, name)

    # --- buyruqlar (foydalanuvchi aytgan harakatlar) -----------------------------------------

    def run_command(self, now: float, spec: CommandSpec) -> CommandResult:
        """Buyruqni boshlash. Natija iborani tanlash uchun (Behavior gapirmaydi):

        ok — boshlandi; outfit — kiyim almashib boshlandi; missing — hech qaysi kiyimda rasmi
        yo'q; idle — maxsus buyruq hech narsa qilmadi (uyg'oq ekan "uygon"); busy — havoda/qo'lda.
        """
        if self.dragging or not self.body.grounded:
            return "busy"
        if spec.mode == "maxsus":
            return self._run_special(now, spec)
        slot = spec.slot
        if slot not in self.slots:
            return "missing"
        if slot == "sleep":
            self.go_sleep(now, forced=True)  # kiyimni o'zi tanlaydi (faqat xudida)
            self.command = ActiveCommand(spec.name, spec.mode, now)
            return "ok"
        changed = False
        if not self.wardrobe.has(slot):
            base = self._outfit_for(slot)
            if base is None:
                return "missing"
            self.wardrobe.base_outfit = base  # keyingi odatiy qayta tanlovgacha shunday qoladi
            changed = True
        self._end_command()
        steps = self._command_steps(spec)
        self.command = ActiveCommand(spec.name, spec.mode, now)
        self._interrupt(now, steps, slot)  # faoliyat nomi — slot (AI prompti uchun)
        self.emit("command", spec.name)
        return "outfit" if changed else "ok"

    def _outfit_for(self, slot: str) -> str | None:
        """Slotning rasmi bor kiyimlardan kun qismiga mosrog'i (kunduzi tee, kechasi qora xudi)."""
        allowed = self.wardrobe.allowed_base(slot)
        if not allowed:
            return None
        weights = self.wardrobe.rules["outfit_weights"].get(self.period_fn(), {})
        return max(allowed, key=lambda o: float(weights.get(o, 0.0)))

    def _command_steps(self, spec: CommandSpec) -> list[Step]:
        slot, info = spec.slot, self.slots[spec.slot]
        look = self.wardrobe.dress(slot, self.period_fn())
        if spec.mode == "keyingi_buyruqgacha":
            core = Step(slot, "time", UNTIL_NEXT_MAX)
        elif spec.mode == "uygonguncha":
            core = Step(slot, "forever")
        elif (spec.mode == "soniya" and info.loop) or slot in SEATED:
            secs = spec.seconds or self.rng.uniform(*LOOP_SECONDS.get(slot, (4.0, 8.0)))
            core = Step(slot, "time", secs)
        else:
            core = Step(slot, "once")
        if slot == "train":
            self.face_right = self.rng.random() < 0.5
        if slot in SEATED or info.sit:
            core.look = None
            steps = [core, Step("standup", "once")]
            if not (self.seated and not self.sleeping):
                steps.insert(0, Step("sitdown", "once"))
            steps[0].look = look
            return steps
        core.look = look
        return [core]

    def _run_special(self, now: float, spec: CommandSpec) -> CommandResult:
        name = spec.name
        expression = {"uyal": "shy"}.get(name)
        if expression is not None:
            self._end_command()
            self.show_expression(now, expression)
            return "ok"
        if name == "sayr":
            return self._start_sayr(now, spec.seconds or 150.0)
        if name == "toxta":
            self._end_command()
            self._interrupt(now, [Step("idle", "time", 1.5)], "idle")
            return "ok"
        if name in ("uygon", "tur") and self.sleeping:
            self.wake(now)
            return "ok"
        if name == "tur" and self.seated:
            self._end_command()
            self._interrupt(now, [Step("idle", "time", 1.0)], "idle")
            return "ok"
        return "idle"

    def _end_command(self) -> None:
        if self.command is None and self.sayr is None:
            return
        name = self.command.name if self.command else "sayr"
        self.command = None
        self.sayr = None
        self.emit("command_end", name)

    # --- sayr ---------------------------------------------------------------------------------

    def _start_sayr(self, now: float, seconds: float) -> CommandResult:
        self._end_command()
        self.command = ActiveCommand("sayr", "maxsus", now)
        self.sayr = Sayr(end=now + seconds)
        self.emit("sayr", "start")
        self._interrupt(now, [], "sayr")  # o'tirgan bo'lsa — avval turadi
        return "ok"

    def _sayr_next(self, now: float) -> None:
        """Sayrning keyingi qadami: yurish, to'xtab gapirish yoki tugash."""
        sayr = self.sayr
        assert sayr is not None
        self.activity = "sayr"
        if now >= sayr.end:
            self._finish_sayr()
            return
        if sayr.next_stop is not None and now >= sayr.next_stop:
            sayr.next_stop = None  # keyingi to'xtash — yurish qayta boshlanganda belgilanadi
            laugh = self.rng.random() < SAYR_LAUGH
            self.emit("sayr", "kulish" if laugh else "gap")
            if laugh and self.expression_available("happy"):
                self.expression = "happy"
                self.plan.append(Step("expressions", "time", SAYR_STOP_S, tag="sayr_stop"))
            else:
                self.plan.append(Step("talk", "time", SAYR_STOP_S, tag="sayr_stop"))
            return
        if sayr.next_stop is None:
            sayr.next_stop = now + self.rng.uniform(*SAYR_STOP_EVERY)
        step = self._sayr_walk()
        self.plan.append(step or Step("idle", "time", 1.0))

    def _sayr_walk(self) -> Step | None:
        """Turgan yuzasi bo'ylab chetigacha; chetda burilib qaytadi (boshqa oynaga o'tmaydi)."""
        seg = self.body.seg
        if seg is None:
            return None
        lo, hi = seg.a + self.half_width, seg.b - self.half_width
        if hi - lo < 40 * self.scale:
            return None
        if self.face_right and self.body.x >= hi - 2:
            self.face_right = False
        elif not self.face_right and self.body.x <= lo + 2:
            self.face_right = True
        target = hi if self.face_right else lo
        look = self.wardrobe.dress("walk", self.period_fn())
        speed = self.walk_speed_for("walk", look)
        return Step("walk", "walk", target_x=target, speed=speed, look=look)

    def _sayr_talking(self, now: float, on: bool, expression: str | None) -> None:
        """Sayr paytida javob: yurish to'xtaydi (talk), gap tugagach davom etadi."""
        step = self.step
        if step is not None and step.tag == "sayr_stop":
            return  # o'zi to'xtab gapiryapti — vaqti tugagach yuradi
        if on:
            if step is None or step.tag != "sayr_pause":
                self._replace_plan(now, [Step("talk", "forever", tag="sayr_pause")], "sayr")
            return
        if step is not None and step.tag == "sayr_pause" and self.sayr is not None:
            self.sayr.next_stop = None  # javobdan keyin darhol yana to'xtamasin
            self._replace_plan(now, [], "sayr")

    def _finish_sayr(self) -> None:
        """Oxirida: qo'l silkitadi (rasmi bo'lmasa — xursand ifoda); keyin odatiy hayot."""
        self._end_command()
        self.emit("sayr", "end")
        if self.wardrobe.has("wave"):
            self.plan.append(Step("wave", "time", 2.5, look=self.wardrobe.dress("wave")))
        elif self.expression_available("happy"):
            self.expression = "happy"
            self.plan.append(Step("expressions", "time", 3.0))
        else:
            self.plan.append(Step("idle", "time", 1.0))

    def restart(self, now: float) -> None:
        """Kun qismi yoki kiyim sozlamasi o'zgarganda: yangi faoliyatni darhol tanlash."""
        self.wardrobe.update_period(self.period_fn())
        if self.sleeping:
            return
        if self.command is not None:
            return  # buyruq tugagach odatiy hayot yangi kun qismi bilan davom etadi
        if self.look.base_outfit != self.wardrobe.base_outfit:
            self.look = self.wardrobe.dress("idle")  # yangi kiyim reaksiyalarda ham ko'rinsin
        if self.dragging or not self.body.grounded or self.focus:
            return
        self._interrupt(now, [], "restart")

    def _walk_step(self, slot: str, look: Look) -> Step | None:
        seg = self.body.seg
        if seg is None:
            return None
        lo, hi = seg.a + self.half_width, seg.b - self.half_width
        if hi - lo < 40 * self.scale:
            return None
        dist = self.rng.uniform(80, 400) * self.scale
        go_right = self.rng.random() < 0.5
        if self.body.x + dist > hi and self.body.x - dist >= lo:
            go_right = False
        elif self.body.x - dist < lo and self.body.x + dist <= hi:
            go_right = True
        target = self.body.x + dist if go_right else self.body.x - dist
        if seg.owner is not None and self.rng.random() < EDGE_WALK_OFF:
            target = seg.b + self.half_width if go_right else seg.a - self.half_width
        else:
            target = max(lo, min(hi, target))
        if abs(target - self.body.x) < 10:
            return None
        self.face_right = target > self.body.x
        speed = self.walk_speed_for(slot, look)
        return Step(slot, "walk", target_x=target, speed=speed, look=look)

    # --- har kadr -----------------------------------------------------------------------------

    def tick(self, now: float) -> Visual:
        dt = 0.0 if self.last is None else max(0.0, min(0.1, now - self.last))
        self.last = now

        if self.dragging or self.body.grounded:
            self._air_t0 = None
        elif self._air_t0 is None:
            self._air_t0 = now

        if self.dragging:
            pass
        elif not self.body.grounded:
            speed = self.body.step_fall(dt, self.surfaces, self.screens, self.half_width)
            if speed is not None:
                self._on_landed(now, speed)
        else:
            self._tick_ground(now, dt)

        vis = self._visual(now)
        self.last_visual = vis
        return vis

    def _blink_frame(self, info: SlotInfo, now: float, t: float, n: int, fps: float) -> int:
        """Idle: `rest` kadrlari aylanadi; tasodifiy 3–6 s da bir marta `blink.frames`."""
        blink = info.blink
        assert blink is not None
        if max(*blink.frames, *blink.rest) >= n or fps <= 0:
            return info.frame_at(t, n, fps)  # lenta mos emas — oddiy aylanish
        if self._blink_next is None:
            self._blink_next = now + self.rng.uniform(*blink.every_s)
        if self._blink_t0 is None and now >= self._blink_next:
            self._blink_t0 = now
        if self._blink_t0 is not None:
            i = int((now - self._blink_t0) * max(fps, BLINK_FPS))
            if i < len(blink.frames):
                return blink.frames[i]
            self._blink_t0 = None
            self._blink_next = now + self.rng.uniform(*blink.every_s)
        return blink.rest[int(t * fps) % len(blink.rest)]

    def blink_now(self, now: float) -> None:
        """Sinov: darhol bir marta ko'z yumib-ochish (idle bo'lmasa — avval idle)."""
        if self.dragging or not self.body.grounded or self.sleeping:
            return
        if self.step is None or self.step.slot != "idle":
            self._interrupt(now, [Step("idle", "time", 4.0)], "idle")
        self._blink_t0 = None
        self._blink_next = now

    def _on_landed(self, now: float, speed: float) -> None:
        """Yerga tegdi: `land` bir marta to'liq (oxirida ~1 s), keyin odatiy hayot.

        Past balandlikdan yoki ekran tepasidan "tushib kelish" (ochilish, chaqirish) — land yo'q.
        Varianti yo'q look'da fallback (15-okt dan uchala kiyimda o'z rasmi bor).
        """
        self.body.attach_owner(self.windows)
        self.emit("landed", speed)
        self._end_command()  # otish yoki yiqilish buyruqni bekor qiladi
        self.plan.clear()
        self.step = None
        air = now - self._air_t0 if self._air_t0 is not None else 0.0
        thrown, self.released = self.released and speed >= THROWN_SPEED, False
        gentle, self.gentle_drop = self.gentle_drop, False
        if thrown:
            self.emit("thrown", speed)  # faqat ibora uchun
        if "land" in self.slots and not gentle and air >= LAND_MIN_AIR:
            self._replace_plan(
                now, [Step("land", "once", look=self._reaction_look("land"))], "land"
            )
        else:
            self._replace_plan(now, [Step("idle", "time", self.rng.uniform(0.5, 1.2))], "landed")

    def _tick_ground(self, now: float, dt: float) -> None:
        if self.step is None:
            self._advance(now)
        step = self.step
        assert step is not None
        t = now - self.step_t0
        done = False
        if step.mode == "walk":
            done = self.body.step_walk(dt, step.target_x, step.speed)
            if not self.body.grounded:  # chetdan tushib ketdi
                self._end_command()
                self._drop_hood()
                self.plan.clear()
                self.step = None
                self.look = self.wardrobe.adapt(self.look, "fall")
                return
            sayr = self.sayr
            if sayr is not None and (
                now >= sayr.end or (sayr.next_stop is not None and now >= sayr.next_stop)
            ):
                self.plan.clear()  # sayr: to'xtash yoki tugash vaqti — yurish shu yerda to'xtaydi
                done = True
        elif step.mode == "once":
            done = t >= self._duration(step.slot)
        elif step.mode == "time":
            done = t >= step.seconds
        if done and self._talk_wait and step.slot in KEEP_SLOTS:
            self._finish_reaction(now)
        elif done:
            self._advance(now)

    def _visual(self, now: float) -> Visual:
        if self.dragging:
            slot, t = "dangle", now - self.drag_t0
        elif not self.body.grounded or self.step is None:
            # Tushish kadrlari havoda takrorlanadi.
            slot, t = "fall", now - (self._air_t0 if self._air_t0 is not None else now)
        else:
            slot, t = self.step.slot, now - self.step_t0
        dslot, look, frame = self.resolve(slot, self.look)
        info = self.slots[dslot]
        if frame is None:
            variant = self.pack.variant(dslot, look.outfit)
            n = variant.frames if variant else 1
            fps = self.fps(dslot, variant)
            if info.static:
                frame = self.pack.expression_frame(look.outfit, self.expression) or 0
            elif info.blink is not None and slot == dslot and self.body.grounded:
                frame = self._blink_frame(info, now, t, n, fps)
            else:
                step0 = self.step.frame0 if self.step is not None and self.body.grounded else 0
                frame = info.frame_at(t + (step0 / fps if fps > 0 else 0.0), n, fps)
        mirror = info.faces_right and not self.face_right
        vis = Visual(dslot, frame, look, mirror)
        step = self.step
        if (
            step is not None
            and step.fade_in > 0
            and t < step.fade_in
            and self._fade_from is not None
            and self.body.grounded
        ):
            vis = replace(
                vis, fade_from=replace(self._fade_from, fade_from=None), fade=t / step.fade_in
            )
        return vis
