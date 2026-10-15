"""Til himoyasi: javob o'zbekcha ekanini evristik tekshirish.

- Lotin: o'zbekcha harf birikmalari (o', g', oʻ, gʻ, sh, ch) va keng tarqalgan so'z/qo'shimchalar
  ulushi inglizcha stop-so'zlar ulushi bilan solishtiriladi.
- Kirill: o'zbekcha harflar (ў қ ғ ҳ) va so'zlar ruscha stop-so'zlar bilan solishtiriladi.
- Kod, buyruqlar, havolalar va teglar hisobga olinmaydi; juda qisqa javoblar o'tkaziladi.
Foydalanuvchi boshqa tilni aniq so'ragan bo'lsa ("inglizchaga tarjima qil") — tekshirilmaydi.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

TRANSLATE_PROMPT = (
    "Quyidagi matnni o'zbek tiliga (lotin yozuvida) o'gir. Ma'nosini, ohangini, boshidagi "
    "[ifoda] tegini va oxiridagi <...> teglarni o'zgartirmasdan qoldir. Kod, buyruqlar va "
    "atamalarni o'zgartirma. Faqat o'girilgan matnni qaytar, izoh yozma."
)

_TAG_RE = re.compile(r"<(\w+)[^>]*>.*?</\1>|\[\w+\]", re.S)
_CODE_RE = re.compile(r"`[^`]*`|https?://\S+|\S+[._/\\]\S+|\S*\d\S*")
_WORD_RE = re.compile(r"[a-zA-Zа-яА-ЯёЁўЎқҚғҒҳҲʻʼ'‘’]+")

UZ_LATIN_WORDS = frozenset(
    """va bu men siz sen biz ular u uchun bilan emas kerak ham bor yo'q nima qanday qanaqa juda
    yaxshi endi lekin chunki mumkin shu o'sha bir ikki keyin oldin hozir bugun ertaga kecha
    qiling qildim qilaman bo'ladi bo'lsa edi ekan deb dedi ha yoq mana yana faqat hamma
    agar balki albatta rahmat salom xayr kun soat vaqt ish narsa ko'p kam katta kichik qilib
    ishlayapsiz qilyapsiz aytaman aytdim eslatma eslataman yozdim kim qayer qachon necha""".split()
)
UZ_SUFFIXES = (
    "lar",
    "ning",
    "ni",
    "ga",
    "da",
    "dan",
    "dagi",
    "miz",
    "ngiz",
    "ingiz",
    "siz",
    "man",
    "di",
    "yapti",
    "yapman",
    "moqda",
    "gan",
    "mi",
    "chi",
    "roq",
    "lik",
    "siz",
)
EN_STOP = frozenset(
    """the and is are you to of it that this for with what have be not can will your i my a
    in on was were do does did am an or but if so at as by from we they he she them his her
    there here which would could should just about how why when where who me""".split()
)
RU_STOP = frozenset(
    """и в не что это как я вы на с то он но для по так же ты мы они она его ее её был
    была было быть уже или если только ещё еще очень можно нужно когда где кто""".split()
)
UZ_CYR_WORDS = frozenset(
    """ва бу мен сиз сен биз улар учун билан эмас керак ҳам хам бор йўқ нима қандай жуда
    яхши энди лекин чунки мумкин шу бир кейин олдин ҳозир бугун эртага ҳа рахмат салом""".split()
)
UZ_CYR_LETTERS = set("ўқғҳЎҚҒҲ")
UZ_CYR_SUFFIXES = (
    "лар",
    "нинг",
    "ни",
    "га",
    "дан",
    "даги",
    "миз",
    "нгиз",
    "ингиз",
    "сиз",
    "ман",
    "ди",
    "япти",
    "япман",
    "япсиз",
    "моқда",
    "ган",
    "ми",
    "чи",
    "роқ",
    "лик",
    "аман",
    "имиз",
)

OTHER_LANGUAGE_REQUEST = re.compile(
    r"inglizcha|ingliz tilida|ruscha|rus tilida|tarjima|arabcha|turkcha|nemischa|fransuzcha|"
    r"koreyscha|yaponcha|xitoycha|english|translate|по-русски|на русском|переведи|перевод|"
    r"инглизча|русча|таржима",
    re.I,
)


@dataclass(frozen=True)
class Verdict:
    uzbek: bool
    script: str  # latin / cyrillic / unknown
    score: float


def _clean(text: str) -> str:
    text = _TAG_RE.sub(" ", text)
    return _CODE_RE.sub(" ", text)


def detect(text: str) -> Verdict:
    words = [w.lower() for w in _WORD_RE.findall(_clean(text))]
    if len(words) < 4:
        return Verdict(True, "unknown", 1.0)
    cyr = sum(1 for w in words if re.search(r"[а-яёўқғҳ]", w))
    if cyr > len(words) / 2:
        joined = " ".join(words)
        uz = (
            sum(1 for w in words if w in UZ_CYR_WORDS)
            + 2 * sum(1 for ch in joined if ch in UZ_CYR_LETTERS)
            + 0.5 * sum(1 for w in words if len(w) > 4 and w.endswith(UZ_CYR_SUFFIXES))
        )
        ru = sum(1 for w in words if w in RU_STOP)
        score = (uz + 0.5) / (uz + ru + 1.0)
        # Ruscha stop-so'zlar ko'p va o'zbekcha belgilardan ustun bo'lsa — o'zbekcha emas.
        # Belgilar yo'q, stop-so'zlar ham yo'q — noaniq, o'zbekcha deb qabul qilinadi.
        return Verdict(not (ru / len(words) >= 0.12 and ru > uz), "cyrillic", score)

    n = len(words)
    uz_hits = 0
    for w in words:
        w2 = w.replace("ʻ", "'").replace("‘", "'").replace("’", "'").replace("ʼ", "'")
        if w2 in UZ_LATIN_WORDS or "o'" in w2 or "g'" in w2:
            uz_hits += 1
        elif len(w2) > 4 and w2.endswith(UZ_SUFFIXES):
            uz_hits += 0.5
        elif ("sh" in w2 or "ch" in w2) and w2 not in EN_STOP:
            uz_hits += 0.3
    en_hits = sum(1 for w in words if w in EN_STOP)
    uz_ratio, en_ratio = uz_hits / n, en_hits / n
    uzbek = not (en_ratio >= 0.2 and en_ratio > uz_ratio) and uz_ratio >= 0.12
    return Verdict(uzbek, "latin", uz_ratio - en_ratio)


def translate_instruction(user_text: str) -> str:
    """Foydalanuvchi kirillda yozgan bo'lsa — tarjima ham kirillda."""
    words = _WORD_RE.findall(user_text or "")
    cyr = sum(1 for w in words if re.search(r"[а-яёўқғҳА-ЯЁЎҚҒҲ]", w))
    if words and cyr > len(words) / 2:
        return TRANSLATE_PROMPT.replace("(lotin yozuvida)", "(kirill yozuvida)")
    return TRANSLATE_PROMPT


def wants_other_language(user_text: str) -> bool:
    return bool(OTHER_LANGUAGE_REQUEST.search(user_text or ""))


def needs_translation(user_text: str, reply: str) -> bool:
    """Javobni o'zbekchaga o'girish kerakmi."""
    if wants_other_language(user_text):
        return False
    return not detect(reply).uzbek
