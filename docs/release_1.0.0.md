# Yue 1.0.0

Yue — Windows uchun ish stoli hamrohi. Kichkina chibi qiz ish stolingizda yuradi, o'zbek tilida
gaplashadi, vazifalaringizni eslatadi, tanaffus va uyquni nazorat qiladi. Hazilkash: ustingizdan
do'stona kuladi, lekin hech qachon ranjitmaydi. Bepul, shaxsiy foydalanish uchun.

## Nimalar bor

- **Ish stolidagi hayot**: yurish, sayr, choy, kod yozish, musiqa, kapalak, gul, mashq, uyqu; kun
  vaqtiga qarab kiyimlar.
- **Suhbat o'zbek tilida**: bepul Google Gemini, Claude, OpenRouter yoki oflayn Ollama — o'zingiz
  tanlaysiz. Kalitsiz ham ishlaydi: animatsiyalar, tayyor gaplar, vazifalar va eslatmalar.
- **Vazifalar va eslatmalar**: oddiy gap bilan («ertaga 9 da dori ichishni eslat») yoki tez
  buyruq bilan («eslat 18:00: suv ichish», «vazifalar»). O'z vaqtida aytadi va bildirishnoma
  chiqaradi.
- **G'amxo'rlik**: tanaffus, uyqu, suv, ko'z, batareya eslatmalari.
- **Ovoz (ixtiyoriy)**: o'z ElevenLabs kalitingiz va tanlagan ovozingiz; kunlik chegara bilan.
- **Birinchi ochilish ustasi**: ism, AI (bepul Gemini kalitini olish qadamma-qadam), ovoz,
  avtoyuklash.
- **Maxfiylik**: ma'lumotlar faqat shu kompyuterda, shifrlangan holda. Suhbat faqat tanlangan AI
  provayderga ketadi. Telemetriya yo'q.

## O'rnatish

1. `Yue-1.0.0-setup.exe` ni yuklab oling va ishga tushiring (Windows 10/11, 64-bit).
   Administrator huquqi kerak emas.
2. Litsenziyaga rozilik bildiring va **O'rnatish** ni bosing.
3. Birinchi ochilishda usta sizni bir necha qadamda sozlaydi.

Batafsil qo'llanma — o'rnatilgan papkadagi `README.md` (Start → «Yue — qo'llanma»).

## SmartScreen

Dasturda hali pullik kod imzosi yo'q, shuning uchun Windows "Windows kompyuteringizni himoya
qildi" oynasini ko'rsatishi mumkin. **Batafsil** → **Baribir ishga tushirish** ni bosing
(ruscha Windows'da «Подробнее» → «Выполнить в любом случае», inglizchada «More info» →
«Run anyway»).

Faylning haqiqiyligini SHA256 bilan tekshirish mumkin (PowerShell):

```powershell
Get-FileHash .\Yue-1.0.0-setup.exe -Algorithm SHA256
```

## Fayl

| Fayl | Hajmi | SHA256 |
|---|---|---|
| `Yue-1.0.0-setup.exe` | 89 836 684 bayt (~86 MB) | `d02e34df98accf600d94e1b7e99d2c5fe745433d5b7ef83fa7bc23bf87035cb2` |
