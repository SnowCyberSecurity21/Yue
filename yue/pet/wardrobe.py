"""Kiyim tizimi: `pack.json → wardrobe` qoidalari bo'yicha kiyim va ko'rinish tanlash.

Qt'ga bog'liq emas. Tasodif (`random.Random`) tashqaridan beriladi — testlarda qotiriladi.

Umumiy qoidalar:
- kun qismi kompyuter soatidan;
- asosiy kiyim faqat kun qismi o'zgarganda, uyg'onganda va dastur ochilganda qayta tanlanadi.

v4 (`looks`): ko'zoynak, quloqchin va kapyushon rasmga chizilgan. Slot o'ynalganda joriy asosiy
kiyimga mos look tanlanadi (`looks[look].outfit`), bir nechta bo'lsa — tasodifiy. Varianti yo'q
slot uchun `look_for` None qaytaradi — qolganini `Behavior` hal qiladi (faoliyat tanlanmaydi,
reaksiya `fallback` ga o'tadi). Uxlash faqat xudida: futbolkada bo'lsa kechasi qora, aks holda
kumush xudiga o'tiladi — ataylab kiyim almashtiradigan yagona joy.

v4 kapyushonli yurish (`wardrobe.hood_walk`): shu slotlarda (walk, walk_music) kapyushonli look
tasodifan tanlanmaydi — faqat `decide_hood` qarori bilan (yurishdan oldin, xudida): kun qismi
ehtimoli (`probability`), sozlamadagi kapyushon tanlovi (`Overrides.hood`) ustun. Faqat
kapyushonli look'i bor slot (qora xudida walk_music) — doim kapyushon bilan, "hech qachon"
tanlansa — umuman tanlanmaydi.

v3 (qatlamlar):
- kapyushon faqat `hood.slots` harakatlarida, xudi kiyilgan bo'lsa, `hood.probability` bilan;
  `walk_pocket` da faqat quloqchin boshda bo'lsa;
- aksessuarlar har harakatda `accessory_weights[period]` bo'yicha; slotdagi
  `require`/`forbid`/`prefer` ustun; `phones_head` va `phones_neck` bir vaqtda bo'lmaydi.
"""

from __future__ import annotations

import random
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

Period = Literal["morning", "day", "evening", "night"]
PERIODS: tuple[Period, ...] = ("morning", "day", "evening", "night")

GLASSES = "glasses"
PHONES_HEAD = "phones_head"
PHONES_NECK = "phones_neck"
# Chizish tartibi: base → glasses → phones_head yoki phones_neck.
OVERLAY_ORDER = (GLASSES, PHONES_HEAD, PHONES_NECK)


@dataclass(frozen=True)
class Look:
    """Bitta harakat uchun tashqi ko'rinish."""

    outfit: str  # papka (look) nomi: tee, tee_glasses, hoodie_black, hood_black, ...
    base_outfit: str  # asosiy kiyim: tee, hoodie_black, hoodie_silver
    overlays: tuple[str, ...] = ()  # v3 qatlamlari, OVERLAY_ORDER tartibida (v4 da bo'sh)
    hood: bool = False
    accessories: tuple[str, ...] = ()  # AI prompti uchun: glasses, phones_head, phones_neck

    @classmethod
    def layered(cls, outfit: str, base_outfit: str, overlays: tuple[str, ...]) -> Look:
        """v3: kapyushon — papka nomi asosiy kiyimdan farq qilsa; aksessuarlar = qatlamlar."""
        return cls(outfit, base_outfit, overlays, outfit != base_outfit, overlays)


@dataclass
class Overrides:
    """Sozlamadagi "Kiyim: qo'lda" rejimi. `None` — avtomatik. v4 da faqat `outfit` ishlaydi."""

    outfit: str | None = None  # tee / hoodie_black / hoodie_silver
    glasses: bool | None = None
    phones: Literal["head", "neck", "none"] | None = None
    hood: bool | None = None

    @classmethod
    def from_config(cls, data: Mapping[str, Any] | None) -> Overrides:
        data = data or {}
        return cls(
            outfit=data.get("outfit"),
            glasses=data.get("glasses"),
            phones=data.get("phones"),
            hood=data.get("hood"),
        )


def period_for_hour(hour: int, periods: Mapping[str, list[int]] | None = None) -> Period:
    """Soatdan kun qismini aniqlash. Oraliq [start, end); tun yarim tundan o'tadi."""
    periods = periods or {
        "morning": [6, 12],
        "day": [12, 18],
        "evening": [18, 22],
        "night": [22, 6],
    }
    for name in PERIODS:
        start, end = periods[name]
        if start <= end:
            if start <= hour < end:
                return name
        elif hour >= start or hour < end:
            return name
    return "day"


def _weighted(rng: random.Random, weights: Mapping[str, float]) -> str:
    items = [(k, w) for k, w in weights.items() if w > 0]
    if not items:
        raise ValueError("bo'sh og'irliklar")
    keys, ws = zip(*items, strict=True)
    return rng.choices(keys, weights=ws, k=1)[0]


@dataclass
class Wardrobe:
    rules: Mapping[str, Any]
    slots: Mapping[str, Mapping[str, Any]]
    rng: random.Random = field(default_factory=random.Random)
    overrides: Overrides = field(default_factory=Overrides)
    base_outfit: str = "tee"
    period: Period | None = None
    looks: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)  # v4

    @classmethod
    def from_pack(
        cls, pack: Mapping[str, Any], rng: random.Random | None = None, **kw: Any
    ) -> Wardrobe:
        looks = pack.get("looks", {}) if int(pack.get("version", 3)) >= 4 else {}
        return cls(
            rules=pack["wardrobe"],
            slots=pack["slots"],
            rng=rng or random.Random(),
            looks=looks,
            **kw,
        )

    @property
    def v4(self) -> bool:
        return bool(self.looks)

    # --- kun qismi va asosiy kiyim ---------------------------------------------------------

    def period_for_hour(self, hour: int) -> Period:
        return period_for_hour(hour, self.rules.get("periods"))

    def update_period(self, period: Period) -> bool:
        """Kun qismi o'zgarsa asosiy kiyimni qayta tanlaydi. True — kiyim qayta tanlandi."""
        if period == self.period:
            return False
        self.period = period
        self.reroll_base()
        return True

    def reroll_base(self) -> str:
        """Dastur ochilganda, kun qismi almashganda va uyg'onganda chaqiriladi."""
        if self.overrides.outfit:
            self.base_outfit = self.overrides.outfit
        else:
            weights = self.rules["outfit_weights"][self.period or "day"]
            self.base_outfit = _weighted(self.rng, weights)
        return self.base_outfit

    # --- v4: look'lar ------------------------------------------------------------------------

    def _variants(self, slot: str) -> Mapping[str, Any]:
        info = self.slots.get(slot, {})
        source = info.get("source")
        if source:
            info = self.slots.get(source, {})
        return info.get("variants", {})

    def _all_looks(self, slot: str, outfit: str | None = None) -> list[str]:
        outfit = outfit or self.base_outfit
        return [
            name
            for name in self._variants(slot)
            if name in self.looks and self.looks[name].get("outfit") == outfit
        ]

    def hood_slot(self, slot: str) -> bool:
        """Kapyushonli look'i faqat qaror bilan tanlanadigan slot (walk, walk_music)."""
        return self.v4 and slot in self.rules.get("hood_walk", {}).get("slots", ())

    def _hood_split(self, slot: str, outfit: str | None = None) -> tuple[list[str], list[str]]:
        """(kapyushonsiz, kapyushonli) look'lar."""
        names = self._all_looks(slot, outfit)
        hooded = [n for n in names if self.looks[n].get("hood")]
        return [n for n in names if n not in hooded], hooded

    def look_names(
        self, slot: str, outfit: str | None = None, hood: bool | None = None
    ) -> list[str]:
        """v4: slotning shu asosiy kiyimdagi look'lari (pack tartibida).

        Kapyushonli yurish slotlarida — faqat `hood` ga mos look'lar (None — kapyushonsiz).
        """
        if not self.hood_slot(slot):
            return self._all_looks(slot, outfit)
        plain, hooded = self._hood_split(slot, outfit)
        return hooded if hood else plain

    def has(self, slot: str, outfit: str | None = None) -> bool:
        """Slotning joriy (yoki berilgan) asosiy kiyimda rasmi bormi."""
        if not self.v4:
            return (outfit or self.base_outfit) in self.allowed_base(slot)
        if self.hood_slot(slot):
            plain, hooded = self._hood_split(slot, outfit)
            return bool(plain) or (bool(hooded) and self.overrides.hood is not False)
        return bool(self.look_names(slot, outfit))

    def decide_hood(self, slot: str, period: Period | None = None) -> bool:
        """Yurishdan oldin: kapyushon kiyiladimi (faqat xudida, faqat hood_walk slotlarida).

        Sozlama ("har doim" / "hech qachon") ustun; faqat kapyushonli look'i bor slot — doim.
        """
        if not self.hood_slot(slot):
            return False
        plain, hooded = self._hood_split(slot)
        if not hooded:
            return False
        if not plain:
            return self.overrides.hood is not False
        if self.overrides.hood is not None:
            return bool(self.overrides.hood)
        chance = self.rules["hood_walk"].get("probability", {}).get(period or self.period or "day")
        return self.rng.random() < float(chance or 0.0)

    def make_look(self, name: str) -> Look:
        """v4: look nomidan `Look` (aksessuarlar — prompt uchun, look ma'lumotidan)."""
        info = self.looks.get(name, {})
        acc: list[str] = []
        if info.get("glasses"):
            acc.append(GLASSES)
        phones = info.get("phones")
        if phones == "head":
            acc.append(PHONES_HEAD)
        elif phones == "neck":
            acc.append(PHONES_NECK)
        return Look(
            outfit=name,
            base_outfit=str(info.get("outfit", self.base_outfit)),
            hood=bool(info.get("hood", False)),
            accessories=tuple(acc),
        )

    def look_for(
        self, slot: str, outfit: str | None = None, hood: bool | None = None
    ) -> Look | None:
        """v4: slot uchun joriy kiyimdagi look (bir nechta bo'lsa — tasodifiy), yo'q bo'lsa None.

        Kapyushonli yurish slotlarida kapyushonli look faqat `hood=True` bilan.
        """
        names = self.look_names(slot, outfit, hood)
        if not names:
            return None
        return self.make_look(names[0] if len(names) == 1 else self.rng.choice(names))

    # --- bitta harakat uchun kiyinish --------------------------------------------------------

    def allowed_base(self, slot: str) -> list[str]:
        if self.v4:
            bases: list[str] = []
            for name in self._variants(slot):
                base = self.looks.get(name, {}).get("outfit")
                if base and base not in bases:
                    bases.append(base)
            return bases
        info = self.slots.get(slot, {})
        return list(info.get("outfits") or self.rules["base_outfits"])

    def ensure_base_for(self, slot: str) -> bool:
        """Slot ma'lum kiyimni talab qilsa (uxlash → xudi), asosiy kiyimni almashtiradi.

        True — kiyim almashdi. Qo'lda tanlangan kiyim ham bu talabga bo'ysunadi.
        """
        allowed = self.allowed_base(slot)
        if self.base_outfit in allowed or not allowed:
            return False
        if self.v4:
            # Futbolkadan uyquga: kechasi qora xudi, qolgan paytda kumush.
            want = "hoodie_black" if self.period == "night" else "hoodie_silver"
            self.base_outfit = want if want in allowed else allowed[0]
            return True
        weights = self.rules["outfit_weights"][self.period or "day"]
        sub = {k: weights.get(k, 0.0) for k in allowed}
        if not any(v > 0 for v in sub.values()):
            sub = {k: 1.0 for k in allowed}
        self.base_outfit = _weighted(self.rng, sub)
        return True

    def dress(self, slot: str, period: Period | None = None, hood: bool | None = None) -> Look:
        """Harakat boshlanishida ko'rinishni tanlaydi (aksessuar va kapyushon qayta o'raladi).

        v4: joriy kiyimdagi look; slotning bu kiyimda rasmi bo'lmasa — `idle` look'i
        (kiyim almashmaydi, nima chizilishini `Behavior` hal qiladi). `hood` — `decide_hood`
        qarori (kapyushonli yurish slotlari uchun).
        """
        if self.v4:
            return (
                self.look_for(slot, hood=hood)
                or self.look_for("idle")
                or self.make_look(self.base_outfit)
            )
        period = period or self.period or "day"
        info = self.slots.get(slot, {})
        require = set(info.get("require", ()))
        forbid = set(info.get("forbid", ()))
        prefer: Mapping[str, float] = info.get("prefer", {})
        acc = self.rules["accessory_weights"][period]

        on: set[str] = set()

        # Ko'zoynak
        if self.overrides.glasses is not None:
            if self.overrides.glasses:
                on.add(GLASSES)
        elif self.rng.random() < prefer.get(GLASSES, acc.get(GLASSES, 0.0)):
            on.add(GLASSES)

        # Quloqchin: bitta kategorik tanlov — bosh / bo'yin / yo'q
        if self.overrides.phones is not None:
            phones = {"head": PHONES_HEAD, "neck": PHONES_NECK}.get(self.overrides.phones)
        else:
            p_head = prefer.get(PHONES_HEAD, acc.get(PHONES_HEAD, 0.0))
            p_neck = min(prefer.get(PHONES_NECK, acc.get(PHONES_NECK, 0.0)), 1.0 - p_head)
            r = self.rng.random()
            phones = PHONES_HEAD if r < p_head else PHONES_NECK if r < p_head + p_neck else None
        if phones:
            on.add(phones)

        # Slot talablari ustun
        for layer in require:
            on.add(layer)
        if PHONES_HEAD in require:
            on.discard(PHONES_NECK)
        elif PHONES_NECK in require:
            on.discard(PHONES_HEAD)
        if PHONES_HEAD in forbid and PHONES_HEAD in on:
            # Quloqchin boshdan tushsa — bo'yinga osiladi (yo'qolib qolmaydi).
            on.discard(PHONES_HEAD)
            if PHONES_NECK not in forbid:
                on.add(PHONES_NECK)
        on -= forbid

        overlays = tuple(layer for layer in OVERLAY_ORDER if layer in on)
        outfit = self._outfit_with_hood(slot, PHONES_HEAD in on)
        return Look.layered(outfit, self.base_outfit, overlays)

    def adapt(self, look: Look, slot: str) -> Look:
        """Joriy ko'rinishni qayta o'ramasdan yangi slot talablariga moslash (yiqilish, osilish).

        Masalan, `fall` quloqchinni boshda taqiqlaydi — u bo'yinga tushadi, ko'zoynak qoladi.
        v4 da qatlam yo'q — ko'rinish o'zgarmaydi.
        """
        if self.v4:
            return look
        info = self.slots.get(slot, {})
        require = set(info.get("require", ()))
        forbid = set(info.get("forbid", ()))
        on = set(look.overlays) | require
        if PHONES_HEAD in require:
            on.discard(PHONES_NECK)
        if PHONES_HEAD in forbid and PHONES_HEAD in on:
            on.discard(PHONES_HEAD)
            if PHONES_NECK not in forbid:
                on.add(PHONES_NECK)
        on -= forbid
        overlays = tuple(layer for layer in OVERLAY_ORDER if layer in on)
        return Look.layered(look.outfit, look.base_outfit, overlays)

    def _outfit_with_hood(self, slot: str, phones_head: bool) -> str:
        hood = self.rules.get("hood", {})
        hood_outfit = hood.get("map", {}).get(self.base_outfit)
        if not hood_outfit or slot not in hood.get("slots", ()):
            return self.base_outfit
        if slot == "walk_pocket" and hood.get("walk_pocket_requires") == PHONES_HEAD:
            if not phones_head:
                return self.base_outfit
        if self.overrides.hood is not None:
            up = self.overrides.hood
        else:
            up = self.rng.random() < float(hood.get("probability", 0.5))
        return hood_outfit if up else self.base_outfit
