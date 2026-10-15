# Claude Code uchun: Yue 0.1.0 — Nora'dan ko'chirish, nomni almashtirish, munosabatni olib tashlash

```
Yangi loyiha: Yue. Bu Nora asosida yasalgan alohida ilova, boshqalarga tarqatiladi. Papka: C:\Yue. Avval docs\yue_reja.md ni o'qi.
C:\nora faqat manba: u yerda hech narsani o'zgartirma, hech narsa yozma, commit ham qilma.

## 0. Repo va muhit
- C:\Yue da git init. Tarix yangidan boshlanadi, Nora tarixi ko'chirilmaydi.
- GitHub'da private repo yarat: gh repo create SnowCyberSecurity21/Yue --private --source C:\Yue --remote origin. gh ishlamasa, menga yoz va push'siz davom et.
- .venv ni Nora'dagidek yarat, requirements.txt dan o'rnat.

## 1. Ko'chirish (faqat ro'yxatdagilar)
Ko'chiriladi:
- nora\ → yue\ (Python paketi), nora.pyw → yue.pyw;
- tests\;
- persona\;
- assets\ui\;
- build\nora.spec → build\yue.spec, build\nora.iss → build\yue.iss, build\version_info.txt;
- pyproject.toml, requirements.txt, .gitignore.

Ko'chirilmaydi:
- .git, .venv*, __pycache__, .pytest_cache, .ruff_cache, dist\ va build\ ichidagi yig'ish natijalari;
- art_src\ (unda _voice\ ham bor, boshqa odamning ovoz namunasi);
- tools\ (art vositalari Nora'da qoladi);
- reference\ (MaoMao, litsenziyasiz);
- docs\ (C:\Yue\docs dagi yangi hujjatlarga tegma), PROMPT.md, README.md, CLAUDE.md;
- assets\packs\nora\ (eski vektor to'plam);
- %APPDATA%\Nora dagi hech narsa: config, baza, kalitlar, ovoz keshi.

Rasmlar uchun tools\sync_pack.py yoz (Yue'dagi yagona vosita):
- C:\nora\assets\packs\nora_ai ni assets\packs\yue ga ko'chiradi. Manba yo'li argument bilan beriladi, standart qiymati shu.
- nora.ico → yue.ico. icon.png nomi o'zgarmaydi.
- pack.json'da Yue'da ishlatilmaydigan teglar ("love" ifodasi) chaqiriladigan ro'yxatlardan chiqariladi. Kadrlar qolishi mumkin.
- Keyin Nora'da yangi rasm qo'shilsa, shu skript qayta ishga tushiriladi.
- assets\packs\yue ni shu skript bilan yarat.

## 2. Nomni almashtirish
- Paket nora → yue. Importlar, testlar, spec, pyproject (name, scripts, ruff exclude) ham shunga mos o'zgarsin.
- Muhit o'zgaruvchilari: NORA_DATA, NORA_DEBUG, NORA_PACK → YUE_DATA, YUE_DEBUG, YUE_PACK.
- Ma'lumotlar papkasi: %APPDATA%\Yue (yue.db, config.json, logs\, voice\, ctl.token).
- Exe va o'rnatuvchi:
  - exe nomi Yue.exe, o'rnatish papkasi %LOCALAPPDATA%\Programs\Yue;
  - Inno AppId — yangi GUID;
  - avtostart qiymati "Yue";
  - QLocalServer va lock nomlari, AppUserModelID ham Yue'niki.
  - Nora va Yue bitta kompyuterda bir vaqtda ishlay olsin va bir-biriga xalaqit bermasin.
- Foydalanuvchiga ko'rinadigan matnlar (i18n, iboralar, persona, bildirishnomalar, o'rnatuvchi): "Nora" → "Yue". Qo'shimchalar to'g'ri bo'lsin: Yuening, Yueni, Yuega, Yuedan, Yue bilan.
- Tezkor tugmalar:
  - ko'rsatish/yashirish: standart Ctrl+Alt+Y. Sozlamalarda o'zgartirsa bo'ladigan qil, ovoz tugmasidagidek.
  - ovozni o'chirish: standart Ctrl+Alt+Shift+U.
  - band bo'lsa, logga va Sozlamalarga izoh chiqsin (Nora'dagidek). Hotkey ID'lari ham Nora'nikidan farq qilsin.
- Shaxsiy narsalar:
  - persona\talaffuz.json dan Nora foydalanuvchisining laqabini olib tashla va "Yue": "Yu-e" qo'sh (u faqat ovoz matniga ta'sir qiladi);
  - kodda, testlarda va personada foydalanuvchiga tegishli narsa qolmasin: ism, laqab, C:\Users\user kabi yo'llar, email.

## 3. Munosabat tizimini olib tashlash
Yue'da munosabat yo'q. Hamma uchun bitta xulq: hazilkash, jig'iga tegadi, g'amxo'r, romantikasiz.

Kod:
- Olib tashlanadi:
  - parol (lock.py) va Sozlamalar → Maxfiy (ui\relation.py);
  - munosabat.* sozlamalari va modes'dagi munosabat qismi;
  - Ctrl+Alt+Y "yaqin" tugmasi;
  - /yaqin, /maxfiy, /oddiy kalit so'zlari.
- AI manbasi (Online/Offline) qoladi.
- feelings:
  - Bond (yaqinlik ballari, darajalar, sevgi, tanishuv sanasi, laqab) olib tashlanadi, store'dagi bond jadvali ham;
  - Mood qoladi, lekin "sog'ingan" va "arazlagan" kayfiyatlari bo'lmaydi;
  - "xursand", "xavotirda", "charchagan" va "g'ururli" qoladi.
- core'dan olib tashlanadi:
  - love_reached, yaqinlik_daraja va yaqinlik_sana iboralari;
  - xabarlardagi "yaqin" belgisi;
  - prompt'dagi [Yaqin muloqot] bloki;
  - [Holat] dagi Munosabat va Yaqinlik qatorlari, laqab.
- app'dan olib tashlanadi:
  - TOUCH_COMMANDS, _touch_too_early, _on_love_reached, _sync_affection_wardrobe;
  - bubble'ning intimate rejimi va clear_sensitive;
  - menyu va tray'da munosabatga oid hamma narsa.
- harakatlar.json:
  - o_pish, bagirga_bosil va erka olib tashlanadi;
  - uyal qoladi, lekin faqat maqtovga uyalish uchun, romantik ma'noda emas;
  - raqs qoladi. U oddiy o'yin harakati bo'ladi: rad iborasi yo'q, hamma uchun ishlaydi.
- Ifodalar:
  - parse.py dagi ruxsat etilgan teglardan "love" ni olib tashla. AI "love" qaytarsa, "happy" ga almashsin.
  - shy va embarrassed_angry qoladi: maqtovga uyalish va jahl uchun, romantik ma'noda emas.
- Silash (pat):
  - mehr bilan javob bo'lmaydi;
  - boshini silasa, qisqa kesatiq va grumpy yoki smug ifoda ("Men mushuk emasman!");
  - pat iboralari shu ma'noda qayta yozilsin.
- persona\hissiyot.json (yaqin uslub namunalari) o'chirilsin.
- Xotira oynasida yaqinlik qismi qolgan bo'lsa, uni ham olib tashla.
- config o'z sxemasidan boshlanadi (versiya 1). Nora migratsiyalari kerak emas.

Persona va iboralar. Hozircha faqat mexanik tozalash, to'liq Yue personasini keyingi bosqichda men yozaman:
- persona_uz.txt va persona_qisqa_uz.txt:
  - "KAYFIYAT VA YAQINLIK" bo'limidan yaqinlik, sog'ingan, arazlagan va "Bugun" qismlarini olib tashla;
  - "IKKI MUNOSABATDA HAM BIR XIL", "MUNOSABAT: MAXFIY" va "MUNOSABAT: YAQIN" bo'limlarini olib tashla;
  - o'rniga qisqa "MUNOSABAT" bo'limi yoz: Yue do'stona hamroh. Romantika, noz-karashma, shirin so'zlar ("jonim", "azizim"), quchoq va o'pish roleplay'i, rashk yo'q. Foydalanuvchi shunday gapirsa, kesatiq bilan ishga qaytaradi;
  - HARAKATLAR ro'yxati harakatlar.json bilan bir xil bo'lsin.
- iboralar.json:
  - o'chirilsin: "yaqin" bo'limi, munosabat.*, yaqinlik_daraja.*, yaqinlik_sana.*, kayfiyat.sogingan, kayfiyat.arazlagan, harakat.raqs_rad;
  - qolgan gaplarda Nora → Yue;
  - "love" tegli gaplar boshqa tegga o'tkazilsin yoki o'chirilsin;
  - romantik so'zlar qolmasin.
- ovoz_bosqich.json yangi kalitlarga moslansin.

## 4. Testlar
- test_munosabat va yaqinlikka oid testlarni olib tashla yoki Yue'ga moslab qayta yoz.
- Yangi testlar:
  - iboralar.json, persona fayllari, i18n va harakatlar.json da quyidagilar yo'q:
    - "Nora" so'zi;
    - romantik so'zlar: jonim, azizim, sevgilim, yuragim, sevaman, sevgi, o'pich, o'pay, quchoq, noz;
  - Nora foydalanuvchisining laqabi hech qayerda yo'q;
  - data_dir %APPDATA%\Yue ni beradi, YUE_DATA uni almashtiradi;
  - AI o_pish, bagirga_bosil yoki erka tegini qaytarsa, e'tiborsiz qoladi. "love" ifodasi "happy" ga almashadi;
  - silash kesatiq iborasini beradi, love yoki happy emas;
  - promptda Munosabat va Yaqinlik qatorlari ham, yaqin bloki ham yo'q;
  - vazifa eslatmasi, tanaffus, uyqu va batareya eslatmalari ishlaydi;
  - Yue va Nora'ning lock, QLocalServer, AppId va avtostart nomlari har xil.
- Barcha testlar o'tsin, ruff toza bo'lsin.

## 5. Hujjatlar
- C:\Yue\CLAUDE.md: Nora'dagi qoidalar (til, buyruqlar, xavfsizlik) Yue uchun moslanadi. Qo'shimcha qoidalar:
  - romantika yo'q;
  - ilovaga hech qanday kalit qo'shilmaydi;
  - rasmlar manbasi Nora'da, yangilash faqat sync_pack.py bilan.
- README.md: qisqa, dasturchi uchun. Foydalanuvchi uchun README keyingi bosqichda yoziladi.

## 6. Yakunda
- Versiya 0.1.0. Yig'ish:
  - pyinstaller build\yue.spec → dist\Yue\Yue.exe;
  - ISCC build\yue.iss → dist\Yue-0.1.0-setup.exe.
- Shu kompyuterga avtostartsiz, jim o'rnat: /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /TASKS="desktopicon".
- Ishga tushir va tekshir:
  - logda bitta "Yue 0.1.0 ishga tushdi" qatori bor, xato yo'q;
  - Nora ham shu paytda ishlab turibdi, ikkalasi xalaqit bermaydi: tray'da ikki belgi, ikki xil ma'lumot papkasi.
- Commit va push.
- Qisqa o'zbekcha hisobot:
  - nima ko'chirildi, nima qolib ketdi;
  - qaysi modul va fayllar olib tashlandi;
  - testlar soni;
  - o'rnatuvchi hajmi;
  - topilgan shaxsiy narsalar;
  - ikonka va rasmlarda "N" harfi qayerlarda bor.
```
