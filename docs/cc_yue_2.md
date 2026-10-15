# Claude Code uchun: Yue 1.0.0 — push, persona, boshqalar uchun tayyorlash, "N" → "Y", reliz

```
Maqsad: Yue'ni boshqa odamlar o'rnatib ishlata oladigan holatga keltirish va 1.0.0 relizini chiqarish. Avval docs\yue_reja.md ni qayta o'qi.
C:\nora faqat manba: u yerda hech narsani o'zgartirma.
Har qism tugagach: testlar, ruff, commit va push.

## 0. Push
- GitHub'da private repo ochilgan: https://github.com/SnowCyberSecurity21/Yue.git
- git remote add origin shu manzil. docs\ dagi o'zgarishlarni commit qil, keyin git push -u origin main. Butun tarix push bo'lsin.
- Kirish so'ralsa yoki xato chiqsa, menga yoz. Nora repo'sini push qiladigan git kirish ma'lumotlari shu kompyuterda bor.

## 1. Persona va iboralar
- docs\yue_persona.txt → persona\persona_uz.txt. Matnni o'zgartirma. HARAKATLAR ro'yxati harakatlar.json bilan mos kelmasa, menga yoz.
- persona_qisqa_uz.txt ni (Offline/Ollama) shu persona asosida qayta yoz:
  - mazmuni bir xil, faqat qisqaroq: kimligi, xarakteri, hazil va uning CHEGARAsi, DO'STLIK CHEGARASI (to'liq), harakatlar, til, vazifalar, sog'liq (qisqa), javob formati;
  - Offline prompt ≤ 6000 token bo'lsin.
- iboralar.json ni yangi persona bo'yicha qayta ko'rib chiq:
  - Har bir gapni personaga solishtir. Quyidagilarni olib tashla yoki qayta yoz:
    - romantika va ishqiy ishoralar;
    - "sizni kutdim", "sog'indim" kabi bog'lab qo'yadigan gaplar;
    - aybdor his qildiradigan gaplar.
  - Jig'iga tegish ko'paysin: greet va idle'da har kun qismidagi gaplarning kamida uchdan biri foydalanuvchi ustidan do'stona kulish bo'lsin.
  - hazil bo'limiga 15 ta yangi gap qo'sh, jami kamida 45 ta bo'lsin.
  - pat: 10 xil kesatiq, "Men mushuk emasman!" ohangida.
  - welcome_back: 8 ta gap. Aybdor qilmasin, quvnoq hazil bo'lsin ("Vazifalaringiz chang bosib qoldi").
- Sifat qoidalari Nora'dagidek:
  - hammasi o'zimiz yozgan, tabiiy o'zbekcha (lotin);
  - har gap ≤140 belgi;
  - teglar faqat ruxsat etilganlardan;
  - takror gap yo'q, "hihi", "pff", "hmf" gaplarning 10% idan oshmasin;
  - eng kuchsiz 20% gapni yaxshirog'iga almashtir, imloni bir marta to'liq tekshir.
- Hazil chegarasi: tashqi ko'rinish, tana, yosh, millat, din, jins, oila, pul, sog'liq va haqiqiy muvaffaqiyatsizlik ustidan kulinmaydi.
- ovoz_bosqich.json ni yangilangan kalitlarga moslab qo'y.
- Hisobotda bo'limlar bo'yicha gaplar soni bo'lsin: oldin va keyin.

## 2. Ovoz chegarasi va tashlanganda land
- docs\cc_ovoz_chegara.md (Nora uchun yozilgan) ning A va B qismlarini Yue'da bajar.
- Nora'da bu hali qilinmagan, u yerga tegma.

## 3. Boshqa foydalanuvchi uchun

### 3.1 Birinchi ochilish ustasi (welcome)
Qadamlar: tanishuv va ism → AI → ovoz (ixtiyoriy) → oxirgi qadam.

AI qadami — beshta variant, birinchisi tavsiya qilinadi:
1. "Bepul — Google Gemini":
   - qadamma-qadam yo'riqnoma: havola tugmasi (GEMINI_KEYS_URL) → Google akkaunt bilan kirish → "Create API key" → kalitni nusxalab shu yerga qo'yish;
   - kalit maydoni va "Tekshirish" tugmasi (mavjud tekshiruv);
   - bepul tarif haqidagi mavjud ogohlantirish.
2. "Claude (pullik, eng aqlli)":
   - havola, kalit maydoni, "Tekshirish";
   - izoh: pul oldindan to'lanadi, Yue standart holatda arzonroq Haiku modelini ishlatadi.
3. "OpenRouter": kalit maydoni va "Tekshirish".
4. "Oflayn — Ollama": qisqa izoh va havola. Model keyin Sozlamalarda tanlanadi.
5. "Hozircha kalitsiz": "Gaplashish ishlamaydi, lekin vazifalar, eslatmalar va animatsiyalar ishlaydi."

Kiritilgan kalitga qarab sozlamalar o'zi qo'yilsin:
- faqat Gemini → ai.primary = gemini;
- Claude bor → ai.primary = claude, rejim "Tez (Haiku)";
- Ollama tanlangan → ai.manba = offline.

Ovoz qadami (o'tkazib yuborsa ham bo'ladi):
- ElevenLabs kaliti maydoni va kalitga kerakli ruxsatlar: Text to Speech, Voices — Read, User — Read.
- Kalit kiritilgach, ovozlar ro'yxati GET /v1/voices dan olinadi. Ro'yxatdan tanlanadi yoki Voice ID qo'lda yoziladi.
- "Eshitib ko'rish" tugmasi bitta qisqa iborani o'qiydi. Bu harflar kunlik hisobga qo'shiladi.
- Izoh: 1 harf ≈ 1 kredit, ElevenLabs bepul tarifida oyiga 10 000 kredit. Kunlik chegarani Sozlamalarda o'zgartirish mumkin.

Oxirgi qadam:
- avtoyuklash va yorliq katakchalari;
- tezkor tugma haqidagi matnda haqiqiy birikma ko'rsatilsin.

Usta faqat bir marta ochiladi (welcome_done). Hammasini keyin Sozlamalardan ham qilish mumkin.

### 3.2 Kalitsiz rejim
- Chatga yozsa, no_keys iborasi chiqadi va pufakda "Sozlamalarni ochish" tugmasi bo'ladi. Bu har xabarda takrorlanmasin: oldingisidan kamida 10 daqiqa o'tgan bo'lishi kerak.
- AI'siz vazifa qo'shish uchun tez buyruqlar:
  - "eslat: <matn>";
  - "eslat 18:00: <matn>", "eslat ertaga 9:00: <matn>" (tasks\timeparse.py bilan);
  - "vazifalar" — ro'yxat chiqadi.
  - Bu buyruqlar AI'ga yuborilmaydi va kalit bor paytda ham ishlaydi.
- Hech qayerda "limit", "quota", "429" yoki texnik xato matni ko'rinmasin (mavjud qoida).

### 3.3 Ovoz va model standartlari
- voice.voice_id standart holatda bo'sh. Kalit va voice_id bo'lmasa, ovoz yo'q, hech qanday xabar ham chiqmaydi.
- Sozlamalar → Ovoz: ovozlar ro'yxati ("Yangilash" tugmasi bilan) va qo'lda Voice ID maydoni.
- Nora'ning voice_id si kodda, testlarda va standart sozlamalarda yo'qligini test bilan tekshir.
- Claude rejimi standart holatda "Tez (Haiku)".

### 3.4 Ilova
- "Sinov" menyusi va debug imkoniyatlari faqat YUE_DEBUG=1 bo'lganda ko'rinsin.
- "Yue haqida" oynasi:
  - versiya va qisqa tavsif;
  - README, LICENSE va THIRD_PARTY_LICENSES fayllarini ochadigan tugmalar;
  - qisqa maxfiylik matni.

### 3.5 O'rnatuvchi (build\yue.iss)
- AppPublisher: SnowCyberSecurity. MinVersion: Windows 10, faqat x64.
- Vazifalar: desktopicon va autostart, ikkalasi oldindan belgilangan.
- O'rnatish va o'chirishdan oldin ishlab turgan Yue yopilsin.
- O'chirishda so'ralsin: "Yue ma'lumotlarini (suhbatlar, vazifalar, sozlamalar) ham o'chiraymi?" Standart javob — Yo'q. Ha bo'lsa, %APPDATA%\Yue o'chiriladi.
- O'rnatish papkasiga README, LICENSE va THIRD_PARTY_LICENSES ham tushsin. Start menyusida "Yue" va "Yue — qo'llanma" yorliqlari bo'lsin.

### 3.6 Hujjatlar
- README.md — foydalanuvchi uchun, o'zbekcha:
  - Yue nima (rasm bilan: to'plamdagi bitta kadr);
  - tizim talablari;
  - o'rnatish va SmartScreen ("Batafsil → Baribir ishga tushirish");
  - birinchi sozlash va bepul Gemini kalitini olish (qadamlar);
  - Claude, OpenRouter va Ollama haqida qisqacha;
  - ovoz: ElevenLabs, kalit ruxsatlari, kredit va kunlik chegara;
  - nimalar qila oladi: suhbat, harakatlar ro'yxati, vazifa va eslatmalar (misollar bilan), tez buyruqlar;
  - tezkor tugmalar;
  - maxfiylik: ma'lumotlar shu kompyuterda shifrlangan holda saqlanadi, suhbat faqat tanlangan AI provayderga ketadi, telemetriya yo'q, bepul Gemini'ga sog'liq va shaxsiy faktlar yuborilmaydi;
  - tez-tez uchraydigan muammolar: tugma band, ovoz chiqmayapti (kunlik chegara), SmartScreen, kalit ishlamayapti;
  - o'chirish;
  - "Aloqa" bo'limi bo'sh qoldirilsin, uni men to'ldiraman.
- docs\DEVELOPING.md — hozirgi dasturchi README mazmuni shu yerga ko'chiriladi.
- LICENSE matni (o'zbekcha):
  "Yue — bepul dastur, shaxsiy foydalanish uchun bepul tarqatiladi. Barcha huquqlar muallifga (SnowCyberSecurity) tegishli. Dasturni sotish yoki o'zgartirilgan nusxasini tarqatish uchun muallifning ruxsati kerak. Dastur "boricha", hech qanday kafolatsiz taqdim etiladi. Sog'liq bo'yicha maslahatlar shifokor maslahati o'rnini bosmaydi."
- THIRD_PARTY_LICENSES.txt:
  - tools\third_party.py skripti yasaydi (importlib.metadata bilan, yangi paket kerak emas);
  - exe ichidagi har bir paket uchun nomi, versiyasi, litsenziyasi va litsenziya matni;
  - Qt (LGPLv3) va Qt Multimedia'dagi FFmpeg haqida izoh: kutubxonalar alohida DLL fayllar, foydalanuvchi ularni almashtirishi mumkin.
- CHANGELOG.md — 1.0.0 yozuvi.

## 4. "N" → "Y" (xudi ko'kragidagi harf)
- Qayerda bor: 0.1.0 hisobotingdagi ro'yxat va docs\yue_reja.md dagi "Holat" bo'limi. Endi faqat birinchi kadrlar emas, hamma kadrlar tekshirilsin.
- sync_pack.py ga logo bosqichi qo'sh. U faqat hoodie_black, hoodie_silver, hood_black va hood_silver kadrlarida ishlaydi:
  - harfni ko'krak sohasida top: tana chegarasiga nisbatan joy va shablon bo'yicha;
  - harfni atrofidagi xudi rangi bilan bo'ya;
  - o'rniga xuddi shu rang, balandlik va qalinlikdagi "Y" chiz. Harf qiyshiq yoki yondan ko'ringan bo'lsa, shunga moslashtir;
  - bosqich idempotent bo'lsin: qayta ishga tushganda hech narsa buzilmasin;
  - Nora'dan yangi rasm kelganda ham avtomatik qo'llanilsin.
- Biror kadrda ishonchli almashtirib bo'lmasa, harfni faqat o'chir (xudi rangi bilan bo'ya). Hech qayerda "N" qolmasin. Bunday kadrlar ro'yxatini hisobotda yoz.
- Tekshiruv varaqlari: build\review\<look>_<slot>.png. Har kadrdagi ko'krakning oldin va keyin ko'rinishi yonma-yon, 2× kattalashtirilgan. Git'ga qo'shilmaydi. Hammasini o'zing ko'rib chiq.
- Testlar:
  - logo bosqichi idempotent;
  - sync'dan keyin xudi look'larida "N" shablonining mos kelishi chegaradan past.

## 5. Yangi foydalanuvchi sifatida sinov
- Windows Sandbox yoqilgan bo'lsa, setup'ni o'sha yerda o'rnatib, birinchi ochilishni tekshir.
- Yoqilmagan bo'lsa, o'rnatilgan Yue.exe ni YUE_DATA = vaqtinchalik bo'sh papka bilan ishga tushir va tekshir:
  - usta chiqadi;
  - kalitsiz yo'lda chat no_keys iborasini faqat bir marta beradi;
  - "eslat 1 daqiqadan keyin" kabi vazifa qo'shiladi va o'z vaqtida eslatiladi;
  - ovozsiz ham xato chiqmaydi;
  - log toza.
- Maxfiylik tekshiruvi. Git tarixi va dist\Yue ichida quyidagilar yo'q:
  - kalit naqshlari: sk-ant-, sk-or-, AIza, sk_, xi-api-key;
  - Nora foydalanuvchisining laqabi;
  - C:\Users\ kabi shaxsiy yo'llar va email manzillari (commit muallifi metadatasidan tashqari).
- pip-audit -r requirements.txt --disable-pip.
- Barcha testlar o'tsin, ruff toza bo'lsin.

## 6. Reliz 1.0.0
- Versiyani 1.0.0 qil: ilova, spec, iss, version_info.
- Yig'ish: dist\Yue-1.0.0-setup.exe.
- docs\release_1.0.0.md (o'zbekcha reliz izohi): nimalar bor, qanday o'rnatiladi, SmartScreen, setup faylining SHA256.
- Shu kompyuterga yangilab o'rnat, avtostartsiz.
- Faqat shu kompyuterdagi %APPDATA%\Yue\config.json da ko'rsatish/yashirish tugmasini Ctrl+Alt+Shift+Y qilib qo'y, Nora'ning Ctrl+Alt+Y tugmasi bilan to'qnashmasin. Standart qiymat o'zgarmaydi.
- Ishga tushir: logda bitta "Yue 1.0.0 ishga tushdi" qatori bo'lsin, xato bo'lmasin.
- Commit, git tag v1.0.0, push (teglar bilan).
- Qisqa o'zbekcha hisobot:
  - nima qilindi (qismlar bo'yicha);
  - iboralar soni, oldin va keyin;
  - "N" → "Y": nechta kadr almashtirildi, nechtasida harf faqat o'chirildi, ro'yxati;
  - sinov natijalari, testlar soni;
  - setup hajmi va SHA256;
  - men qo'lda tekshirishim kerak bo'lgan narsalar.
```
