import pytest

from yue.ai.guard import detect, needs_translation, translate_instruction, wants_other_language

UZ_LATIN = [
    "Salom! Bugun qanday ishlayapsiz? Tushlik qildingizmi, rostini ayting.",
    "Yozdim. Soat 15:00 da eslataman, unutmang.",
    "Parolingiz juda zaif. Kamida 12 belgi va har xil harflar ishlating.",
    "Bu oson savol. Javobi — SHA-256, chunki u bir tomonlama xesh funksiya.",
    "Boshingiz og'riyaptimi? Qachondan beri? Suv ichdingizmi o'zi?",
    "Mayli, yordam beraman. (Yana ish ko'paydi...)",
    "Kechqurun yaxshi fikrlar keladi. Menga ham, sizga ham.",
    "Git'da o'zgarishlarni saqlash uchun git commit -m buyrug'ini ishlating, keyin push qiling.",
]
UZ_CYRILLIC = [
    "Салом! Бугун қандай ишлаяпсиз? Тушлик қилдингизми?",
    "Ёздим. Соат 15:00 да эслатаман, унутманг.",
    "Бу осон савол, жавоби жуда содда.",
]
ENGLISH = [
    "Hello! How are you doing today? I hope you had lunch.",
    "This is an easy question. The answer is SHA-256 because it is a one-way hash.",
    "Sure, I can help you with that. What do you want to do first?",
]
RUSSIAN = [
    "Привет! Как у вас дела? Вы уже пообедали?",
    "Это очень простой вопрос, и ответ на него можно найти быстро.",
]
MIXED_MOSTLY_EN = [
    "Okay, so the main idea is that you should use a strong password, ok? Rahmat.",
]


@pytest.mark.parametrize("text", UZ_LATIN)
def test_uzbek_latin_passes(text):
    v = detect(text)
    assert v.uzbek and v.script in ("latin", "unknown")


@pytest.mark.parametrize("text", UZ_CYRILLIC)
def test_uzbek_cyrillic_passes(text):
    v = detect(text)
    assert v.uzbek and v.script == "cyrillic"


@pytest.mark.parametrize("text", ENGLISH + RUSSIAN + MIXED_MOSTLY_EN)
def test_foreign_detected(text):
    assert not detect(text).uzbek


def test_tags_and_code_ignored():
    text = "[smug] Mana: `print('hello world')` <eslab>Python o'rganyapti</eslab>"
    assert detect(text).uzbek


def test_short_replies_pass():
    assert detect("OK.").uzbek
    assert detect("Yes, sure").uzbek  # juda qisqa — tekshirilmaydi


@pytest.mark.parametrize(
    "request_text",
    [
        "Buni inglizchaga tarjima qil",
        "ingliz tilida yozib ber",
        "ruscha qanday bo'ladi?",
        "Translate this to English please",
        "переведи на русский",
        "Инглизчага таржима қил",
    ],
)
def test_other_language_request_exception(request_text):
    assert wants_other_language(request_text)
    assert not needs_translation(request_text, ENGLISH[0])


def test_needs_translation_without_request():
    assert needs_translation("Salom, qandaysan?", ENGLISH[0])
    assert needs_translation("Salom", RUSSIAN[0])
    assert not needs_translation("Salom", UZ_LATIN[0])


def test_translate_instruction_follows_script():
    assert "lotin" in translate_instruction("Salom, qalaysan?")
    assert "kirill" in translate_instruction("Салом, қалайсан?")
