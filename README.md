# Yue

<img src="docs/yue.png" alt="Yue" width="180" align="right">

**Yue** — Windows uchun ish stoli hamrohi. Kichkina chibi qiz taskbar va oynalar ustida yuradi,
kun vaqtiga qarab kiyinadi, choy ichadi, kod yozadi, kapalak quvlaydi va siz bilan **o'zbek
tilida** gaplashadi. Vazifalaringizni eslab qoladi va o'z vaqtida eslatadi, tanaffus qilishni,
suv ichishni va uxlashni aytadi. Hazilkash: ustingizdan do'stona kuladi, lekin hech qachon
ranjitmaydi.

Yue bepul dastur, shaxsiy foydalanish uchun.

## Tizim talablari

- Windows 10 yoki 11, 64-bit.
- Taxminan 200 MB bo'sh joy.
- Gaplashish uchun internet va AI kaliti (bepul Gemini kaliti ham bo'ladi). Kalitsiz ham Yue
  yuradi, vazifalarni yozadi va eslatadi.
- Ovoz (ixtiyoriy): ElevenLabs kaliti.

## O'rnatish

1. `Yue-1.0.2-setup.exe` ni ishga tushiring. Administrator huquqi kerak emas: dastur
   `%LOCALAPPDATA%\Programs\Yue` ga o'rnatiladi.
2. **SmartScreen.** Windows "Windows kompyuteringizni himoya qildi" oynasini ko'rsatishi mumkin.
   Sababi — dasturda pullik kod imzosi yo'q. **Batafsil** → **Baribir ishga tushirish** ni bosing
   (ruscha Windows'da «Подробнее» → «Выполнить в любом случае», inglizchada «More info» →
   «Run anyway»).
3. Litsenziyaga rozilik bildiring, kerakli katakchalarni tanlang (ish stolida yorliq, Windows
   bilan birga ishga tushirish) va **O'rnatish** ni bosing.

## Birinchi sozlash

Birinchi ochilishda Yue o'zini tanishtiradi va bir necha qadamda sozlaydi: ismingiz → AI → ovoz
(ixtiyoriy) → avtoyuklash. Hammasini keyin **Sozlamalar** dan ham o'zgartirish mumkin (Yue ustida
o'ng tugma → Sozlamalar).

### Bepul Gemini kalitini olish (tavsiya etiladi)

1. Ustada **Bepul — Google Gemini** ni tanlang va **Google AI Studio'ni ochish** tugmasini bosing
   (yoki https://aistudio.google.com/apikey sahifasini oching).
2. Google akkauntingiz bilan kiring.
3. **Create API key** tugmasini bosing.
4. Kalitni nusxalab, ustadagi maydonga qo'ying va **Tekshirish** ni bosing.

Bepul tarif haqida: Google bepul tarifdagi so'rovlarni o'z modellarini yaxshilash uchun ishlatishi
mumkin. Shuning uchun Yue bepul Gemini'ga **sog'liq daftari va shaxsiy faktlaringizni yubormaydi**.
Google API'dan foydalanish uchun 18 yoshdan katta bo'lish kerak.

### Boshqa yo'llar

- **Claude** (pullik, eng aqlli) — kalit: https://platform.claude.com/settings/keys. Pul oldindan
  to'lanadi. Yue standart holatda arzonroq Haiku modelini ishlatadi ("Tez" rejim); Sozlamalarda
  "Aqlliroq (Sonnet)" ni tanlash mumkin.
- **OpenRouter** — bitta kalit bilan ko'p modellar: https://openrouter.ai/settings/keys. Model
  Sozlamalar → AI bo'limida tanlanadi.
- **Oflayn — Ollama** — model kompyuterning o'zida ishlaydi, suhbat hech qayerga chiqmaydi, lekin
  kuchliroq kompyuter kerak. Ollama'ni o'rnating (https://ollama.com/download), modelni yuklab
  oling va Sozlamalar → Offline bo'limida tanlang.
- **Hozircha kalitsiz** — gaplashish ishlamaydi, lekin animatsiyalar, tayyor gaplar, vazifalar va
  eslatmalar ishlaydi.

Kalitlar faqat shu kompyuterda, Windows himoyasi (DPAPI) ostida saqlanadi.

## Ovoz (ixtiyoriy)

Yue gaplarini ovozda ham aytishi mumkin — buning uchun o'zingizning **ElevenLabs** kalitingiz
kerak (https://elevenlabs.io/app/settings/api-keys).

- Kalit yaratishda quyidagi ruxsatlarni yoqing: **Text to Speech**, **Voices — Read**,
  **User — Read**.
- Kalitni Sozlamalar → Ovoz (yoki ustada) kiriting va **Tekshirish** ni bosing: ovozlar ro'yxati
  chiqadi, bittasini tanlang (yoki Voice ID ni qo'lda yozing). **Eshitib ko'rish** tugmasi bitta
  qisqa iborani o'qiydi.
- 1 harf ≈ 1 kredit. ElevenLabs bepul tarifida oyiga 10 000 kredit bor.
- **Kunlik chegara** (standart 3000 harf) kreditni tejaydi. Chegara tugasa, Yue buni aytadi va
  bildirishnoma chiqadi; oldindan tayyorlangan iboralar o'ynayveradi, jonli o'qish ertaga qaytadi.
  Chegarani Sozlamalar → Ovoz bo'limida oshirsangiz, ovoz darhol qaytadi.
- Kalit yoki ovoz tanlanmagan bo'lsa, Yue jim ishlaydi — hech qanday xato chiqmaydi.

## Nimalar qila oladi

**Suhbat.** Yueni bosing va yozing: Enter — yuborish, Shift+Enter — yangi qator, Esc — yopish.
Dasturlash, kiberxavfsizlik, kundalik savollar — hammasiga o'zbekcha javob beradi. Sog'liq
savollarida ehtiyotkor maslahat beradi (shifokor o'rnini bosmaydi).

**Harakatlar.** Yozing — Yue bajaradi: «uxla», «uyg'on», «sakrab ber», «kuylab ber», «musiqa
tingla», «kod yoz», «choy damla», «yuring, sayr qilamiz», «qo'l silkit», «kerishib ol», «mashq
qil», «o'tir», «tur», «kapalak», «gul hidla», «o'ylab ko'r», «jahl qil», «to'xta», «raqsga tush»,
«hazil ayt».

**Vazifalar va eslatmalar.** Oddiy gap bilan:

- «ertaga soat 9 da dori ichishni eslat»
- «har kuni 8:00 da suv ichishni eslatib tur»
- «hisobotni yozish kerak, yozib qo'y»
- «vazifalarim qanday?»

Vaqti kelganda Yue gapiradi va Windows bildirishnomasini chiqaradi. Vazifalarni o'ng tugma →
Vazifalar menyusidan ham qo'shish va belgilash mumkin.

**Tez buyruqlar** (AI'siz ham, kalitsiz ham ishlaydi):

- `eslat: matn` — vazifa yozish;
- `eslat 18:00: matn`, `eslat ertaga 9:00: matn`, `eslat 30 daqiqadan keyin: matn`,
  `eslat har kuni 08:00: matn` — vaqtli eslatma;
- `vazifalar` — ochiq vazifalar ro'yxati;
- `/online`, `/offline` — AI manbasini almashtirish.

**G'amxo'rlik.** Uzoq ishlasangiz tanaffus, tunda uxlash, batareya kamaysa zaryadlash haqida
eslatadi.

## Tezkor tugmalar

- **Ctrl+Alt+Y** — Yueni ko'rsatish yoki yashirish (Sozlamalar → Umumiy'da o'zgartiriladi).
- **Ctrl+Alt+Shift+U** — ovozni jim o'chirish/yoqish (Sozlamalar → Ovoz'da o'zgartiriladi).
- **O'ng tugma** yoki tray belgisi — menyu: vazifalar, kiyim, sozlamalar, xotira, uxlatish.
- Yueni sichqoncha bilan ko'tarish mumkin. U buni yoqtirmaydi.

## Maxfiylik

- Suhbatlar, xotira, vazifalar va sog'liq daftari **faqat shu kompyuterda**, shifrlangan holda
  (AES-256-GCM) saqlanadi: `%APPDATA%\Yue`. Shifr kaliti va API kalitlar Windows himoyasi ostida.
- Suhbat **faqat siz tanlagan AI provayderga** yuboriladi (Gemini, Claude, OpenRouter). Ollama
  tanlansa — hech qayerga.
- **Telemetriya yo'q**: Yue sizning foydalanishingiz haqida hech kimga hech narsa yubormaydi.
- Bepul Gemini'ga sog'liq daftari va shaxsiy faktlar yuborilmaydi.
- AI kompyuteringizda hech narsa qila olmaydi: u faqat matn qaytaradi, Yue esa faqat ruxsat
  etilgan amallarni bajaradi (vazifa qo'shish, eslab qolish, ish stolidagi harakat).
- **Xotiram** oynasida hammasini ko'rish, o'chirish va eksport qilish mumkin.

## Tez-tez uchraydigan muammolar

- **"Bu birikma band" (tezkor tugma).** Boshqa dastur shu tugmani egallagan. Sozlamalar → Umumiy
  (yoki Ovoz) bo'limida boshqa birikma tanlang, masalan Ctrl+Alt+Shift+Y.
- **Ovoz chiqmayapti.** Tray menyusida "Ovoz (bugungi chegara tugadi)" yozuvi bo'lsa — kunlik
  chegara tugagan: ertaga qaytadi yoki Sozlamalar → Ovoz'da chegarani oshiring. Aks holda kalit,
  ovoz tanlangani va "Ovoz" katakchasini tekshiring; to'liq ekranli dastur ochiq bo'lsa, Yue
  jim turadi.
- **SmartScreen ishga tushirishga qo'ymayapti.** **Batafsil** → **Baribir ishga tushirish**.
- **Kalit ishlamayapti.** Sozlamalar → AI'da **Tekshirish** ni bosing: xabar sababini aytadi
  (kalit noto'g'ri, internet yo'q, balans tugagan). Kalitni bo'sh joysiz, to'liq nusxalang.
  Gemini ishlamasa, Yue avtomatik boshqa modelga o'tadi; hech biri bo'lmasa — savolni yozib
  qo'yadi va keyin o'zi javob beradi.

## O'chirish

1. **Windows Sozlamalari → Ilovalar** dan "Yue" ni o'chiring.
2. O'chirish paytida "Yue ma'lumotlarini (suhbatlar, vazifalar, sozlamalar) ham o'chiraymi?" deb
   so'raladi. **Yo'q** — ma'lumotlar `%APPDATA%\Yue` da qoladi (qayta o'rnatsangiz, Yue sizni
   eslaydi). **Ha** — hammasi o'chadi.

## Aloqa

Savol, taklif yoki xato topsangiz, Telegram'da yozing: [@SnowCybersecurity](https://t.me/SnowCybersecurity).

Xato haqida yozganda Yue versiyasini ("Yue haqida" oynasida) va nima bo'lganini qisqacha ayting.
