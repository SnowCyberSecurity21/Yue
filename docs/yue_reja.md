# Yue — reja

Yue — Nora asosida yasalgan alohida ilova, boshqalarga tarqatish uchun. Qiz, rasmlar va animatsiyalar Nora'niki, faqat ismi Yue. Munosabat va romantika yo'q. Hazil, jig'iga tegish, g'amxo'rlik va vazifalar qoladi.

Papka: `C:\Yue`, yangi git repo (Nora tarixisiz). Nora (`C:\nora`) o'zgarmaydi va manba bo'lib qoladi.

## 1. Nima qoladi, nima olib tashlanadi

**Qoladi**
- Ish stolidagi hayot: yurish, sayr, uyqu, choy, kod yozish, musiqa, kapalak, gul, mashq va boshqalar. Kun qismiga qarab kiyimlar va kapyushon ham qoladi.
- AI suhbat: Online rejimda Claude, Gemini va OpenRouter, Offline rejimda Ollama. Navbat avvalgidek ishlaydi, foydalanuvchi "limit tugadi" degan gapni ko'rmaydi.
- Ovoz (ElevenLabs). Ixtiyoriy, 3-qarorga qarang.
- Hazil:
  - kesatiq va jig'iga tegish, foydalanuvchi ustidan do'stona kulish ("stajyor", "yana ertagami?");
  - "hazil ayt" buyrug'i;
  - hazil darajasi sozlamasi.
- Ifodalar: kulgi, xursandlik, jahl, g'urur, hayrat, o'ylanish, uyqusirash.
- Vazifalar daftari va o'z vaqtidagi eslatmalar.
- Foydalanuvchiga g'amxo'rlik: tanaffus, uyqu, choy va suv, ko'z, qad, batareya eslatmalari. Sog'liq savollaridagi ehtiyotkorlik qoidalari ham qoladi.
- Xotira: faktlar va suhbat xulosasi, shifrlangan holda.

**Olib tashlanadi**
- Munosabat tizimi:
  - Yaqin va Maxfiy rejimlar;
  - Sozlamalardagi "Maxfiy" bo'limi va uning paroli;
  - Ctrl+Alt+Y, /yaqin va /maxfiy buyruqlari.
- Yaqinlik ballari va darajalari, "tanishganimizga N kun", laqab, "sevgi" hodisasi.
- "yaqin" iboralari, noz-karashma, shirin so'zlar ("jonim", "azizim"), rashk o'yini.
- O'pish, quchoqlash va erkalanish harakatlari, love ifodasi, yaqinlikka qarab kiyim tanlash.
- Silashga mehr bilan javob berish. Uning o'rniga Yue kesatiq qiladi ("Men mushuk emasman!").
- Bog'lanib qolishga undaydigan kayfiyatlar: "sog'ingan" va "arazlagan".

**O'zgaradi**
- Ism hamma joyda Nora → Yue bo'ladi. Qo'shimchalar: Yuening, Yueni, Yuega, Yuedan.
- Persona: jig'iga tegish ko'proq, romantika yo'q. Ilovani begona odamlar ishlatadi, shuning uchun hazil chegaralari qat'iy. Tashqi ko'rinish, tana, oila, pul, sog'liq va haqiqiy muvaffaqiyatsizlik ustidan kulinmaydi.
- Maqtovga javob: Nora'dagidek uyaladi va buni jahl bilan yashiradi ("B-bu sizga emas!"). Bu romantika emas, faqat maqtovga reaksiya.
- "Yue" ovozda "Yu-e" deb o'qiladi (`talaffuz.json`).
- Xudining ko'kragidagi "N" harfi "Y" ga almashadi (4-bosqich).
- Raqs (standart): oddiy o'yin harakati, hamma uchun ishlaydi va rad etilmaydi.

## 2. Tarqatish uchun shartlar
- **Kalitlar.** Ilovaga hech qanday kalit qo'shilmaydi, har kim o'z kalitini kiritadi. Birinchi ochilishda sozlash ustasi chiqadi va to'rt yo'lni ko'rsatadi:
  - bepul: Gemini kaliti qanday olinishi qadamma-qadam;
  - pullik: Claude;
  - oflayn: Ollama;
  - kalitsiz.
- **Kalitsiz ham ishlasin.** Animatsiyalar, tayyor gaplar, vazifalar va eslatmalar AI'siz ham ishlaydi.
- **Ovoz.** Nora'ning ovozi (dublyaj qizining kloni) Yue'da standart bo'lmaydi, chunki:
  - u sizning ElevenLabs akkauntingizga bog'langan, boshqalarning kaliti bilan ishlamaydi;
  - qizning roziligi Nora uchun berilgan, ommaga tarqatish uchun emas.
- **Shaxsiy narsalar chiqmaydi:**
  - Nora'dagi laqabingiz va sizga tegishli boshqa tafsilotlar;
  - ovoz namunasi (`art_src/_voice`);
  - `reference/maomao` (litsenziyasiz);
  - Nora hujjatlari va git tarixi.
- **Nora bilan yonma-yon ishlasin.** Alohida `%APPDATA%\Yue`, `Yue.exe`, o'rnatuvchi ID, avtostart nomi, lock va ctl nomlari bo'ladi. Tezkor tugmalarni Sozlamalarda o'zgartirsa bo'ladi.
- **Litsenziyalar.** Kutubxonalar litsenziyalari `THIRD_PARTY_LICENSES` faylida bo'ladi (PySide6 — LGPL). Yue'ning o'z litsenziyasi keyin hal qilinadi.
- **SmartScreen.** Imzosiz exe'da Windows "Windows himoya qildi" oynasini chiqaradi. README'da "Batafsil → Baribir ishga tushirish" yo'riqnomasi bo'ladi. Kod imzosi sertifikati keyinroq.
- **Maxfiylik.** README'da qisqa yoziladi:
  - ma'lumotlar faqat kompyuterda, shifrlangan holda saqlanadi;
  - suhbat faqat tanlangan AI provayderga ketadi;
  - telemetriya yo'q.
- **Yoshlar ham ishlatishi mumkin.** Romantika yo'q, hazil chegaralari qat'iy.

## 3. Qarorlar
Qabul qilingan (15-oktabr):
| # | Savol | Qaror |
|---|---|---|
| 1 | Yue boshqalarda qaysi ovozda gapiradi | Har kim o'z ElevenLabs kalitini kiritadi va kutubxonadan ovoz tanlaydi. Kalit bo'lmasa, Yue ovozsiz ishlaydi. Nora ovozi Yue bilan tarqatilmaydi. |
| 2 | Maqtovga javob | Uyaladi (Nora'dagidek), romantikasiz |
| 3 | Xudidagi "N" harfi | "Y" ga almashadi |
| 4 | "Yue" ovozda | "Yu-e" |

Hali ochiq:
| # | Savol | Variantlar | Tavsiya |
|---|---|---|---|
| 5 | Asosiy AI | Gemini bepul kaliti asosiy, Claude, OpenRouter va Ollama ixtiyoriy | shunday |
| 6 | Repo | private, tarqatish Releases orqali / public | private |
| 7 | Tarqatish kanali | GitHub Releases va Telegram kanal | — |

## Holat (15-oktabr)
- 1-bosqich tayyor: Yue 0.1.0 yig'ildi va o'rnatildi, 960 test o'tdi, o'rnatuvchi ~87 MB. Nora bilan yonma-yon ishlaydi.
- Push qilinmadi: GitHub'da repo hali yo'q, gh o'rnatilmagan.
- Ctrl+Alt+Y: boshqalarda standart bo'lib qoladi. Sizning kompyuteringizda bu tugmani Nora "yaqin" uchun egallagan, shuning uchun Yue Sozlamalarida boshqa birikma qo'yiladi (masalan, Ctrl+Alt+Shift+Y).
- "N" harfi bor varaqlar:
  - hoodie_black va hoodie_silver: idle, walk, talk, sitdown, expressions, wave, dangle, fall, land, ponder, walk_pocket, tea, excited_jump;
  - hood_black: walk_music, music, hood_up;
  - hood_silver: walk (yondan).
  - Ikonkada va futbolkada harf yo'q.
- GitHub'da private repo ochildi: SnowCyberSecurity21/Yue.
- Keyingi qadam: `docs\cc_yue_2.md`. 2–6-bosqichlar (push, persona va iboralar, ovoz chegarasi, boshqalar uchun tayyorlash, "N" → "Y", sinov, 1.0.0 reliz) bitta promptda. Persona: `docs\yue_persona.txt`.
- Repo private bo'lgani uchun GitHub Releases boshqalarga ko'rinmaydi. Setup fayli Telegram orqali yoki keyinroq ochiladigan alohida public repo orqali tarqatiladi.

## 4. Bosqichlar
1. **CC-1 — Yue 0.1.0** (`docs/cc_yue_1.md`):
   - ko'chirish, nomni almashtirish;
   - munosabat tizimini olib tashlash;
   - persona va iboralarni mexanik tozalash;
   - testlar, o'rnatuvchi.
2. **Persona va iboralar:**
   - Yue personasini men yozaman: Nora'ning yaxshi tomonlari qoladi, romantika olib tashlanadi, jig'iga tegish ko'payadi;
   - CC iboralarni shu persona bo'yicha qayta yozadi: pat, greet, idle, hazil.
3. **CC-3 — tarqatishga tayyorlash:**
   - birinchi ochilishdagi kalit ustasi va kalitsiz rejim;
   - ovoz (1-qaror);
   - foydalanuvchi uchun README, `THIRD_PARTY_LICENSES`, ikonka.
4. **"N" → "Y":**
   - xudi kadrlarida harf kichkina, shuning uchun CC uni to'plam kadrlarida avtomatik almashtiradi: harfni topadi, xudi rangi bilan bo'yaydi, o'rniga bir xil rang va qalinlikdagi "Y" chizadi;
   - bu qadam `sync_pack.py` ichida bo'ladi, shuning uchun Nora'dan kelgan yangi rasmlarda ham harf o'zi almashadi;
   - har to'plam uchun kontakt varaq (hamma kadrlar bitta rasmda) yasaladi, men tekshiraman;
   - avtomat eplay olmagan kadrlar (yon va orqa ko'rinish, burmalar) ro'yxatga olinadi. Ular uchun ChatGPT'da faqat harfni tahrirlaydigan prompt yoziladi;
   - ikonkada ham "N" bo'lsa, u ham almashadi.
5. **Sinov:**
   - toza Windows'da (Windows Sandbox) o'rnatish: kalitsiz, Gemini bilan va ovozsiz;
   - Nora bilan yonma-yon;
   - 2–3 tanishga beta.
6. **1.0.0 reliz.**
7. **Keyin:** yangi versiya chiqqanini tekshirish, kod imzosi.

## 5. Nora va Yue'ni birga yuritish
- **Rasm va videolar.** Manba Nora'da qoladi (`C:\nora\art_src`). Yue faqat tayyor to'plamni oladi:
  - `tools\sync_pack.py` `C:\nora\assets\packs\nora_ai` ni `assets\packs\yue` ga ko'chiradi;
  - Yue'da ishlatilmaydigan teg va slotlar ko'chirilmaydi.
- **2-bosqich emotion videolari:**
  - Yue'da ishlatiladi: laugh, dance, sulk (jahl bilan), shy (faqat maqtovga);
  - Yue'da ishlatilmaydi: love, flirt, blush (iliq gapdagi qizarish), pat (mehr).
- **Umumiy kod tuzatishlari** (ovoz, AI router, platforma, xatolar):
  - Nora'da qilingach, CC promptiga "Yue'ga ham ko'chir" bandi qo'shiladi;
  - har Nora promptida "Yue'ga tegishlimi?" degan bitta qator bo'ladi.
- Repo public bo'ladigan bo'lsa, undan oldin `docs\` qayta ko'rib chiqiladi.
