# Yue — loyiha qoidalari

Yue — Windows uchun ish stoli hamrohi (desktop pet) va o'zbek tilida gaplashadigan AI yordamchi. Nora
asosida yasalgan alohida ilova, boshqalarga tarqatiladi. Reja: `docs/yue_reja.md`.
Nora (`C:\nora`) — faqat manba: u yerda hech narsa o'zgartirilmaydi, yozilmaydi, commit qilinmaydi.

## Til
- Foydalanuvchiga ko'rinadigan **hamma narsa** o'zbek tilida (lotin): UI, menyular, bildirishnomalar,
  xatolar, Yuening gaplari. Standart til `uz`, OS tiliga qarab avtomatik tanlanmaydi.
- Kod identifikatorlari inglizcha; izohlar va commit xabarlari o'zbekcha.
- Yangi UI satri qo'shsang — `yue/i18n.py` ga yoz; Yuening tayyor gaplari — `persona/iboralar.json` da.
- Ism qo'shimchalari: Yuening, Yueni, Yuega, Yuedan, Yue bilan.

## Buyruqlar
- Muhit: `py -3.12 -m venv .venv` → `.venv\Scripts\pip install -r requirements.txt`
- Ishga tushirish: `.venv\Scripts\python -m yue` (debug: `set YUE_DEBUG=1`)
- Testlar: `.venv\Scripts\python -m pytest -q`; stil: `.venv\Scripts\python -m ruff check .` va
  `ruff format --check .`
- Xavfsizlik: `.venv\Scripts\pip-audit -r requirements.txt --disable-pip`
- Rasmlarni yangilash: `.venv\Scripts\python tools\sync_pack.py` (Nora'dan, pastga qarang)
- Yig'ish: `.venv\Scripts\pyinstaller build\yue.spec --noconfirm` → `dist\Yue\Yue.exe`
- O'rnatuvchi: `"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" build\yue.iss` →
  `dist\Yue-<versiya>-setup.exe` (jim: `/VERYSILENT /SUPPRESSMSGBOXES /NORESTART`)
- Versiya uch joyda: `yue/__init__.py`, `build/yue.iss`, `build/version_info.txt`.

## Yue qoidalari (o'zgarmas)
- **Romantika yo'q.** Munosabat tizimi, yaqinlik ballari, laqab, "sevgi" hodisasi, love ifodasi,
  o'pish/quchoqlash/erkalanish harakatlari, rashk va shirin so'zlar qaytarilmaydi. Yue hamma uchun
  bitta: hazilkash, jig'iga tegadi, g'amxo'r. Maqtovga uyalish bor — u romantika emas.
  `tests/test_yue.py` iboralar, persona, i18n va harakatlar.json da romantik so'z va "Nora"
  yo'qligini tekshiradi.
- Hazil chegaralari qat'iy (ilovani begona odamlar, yoshlar ham ishlatadi): tashqi ko'rinish, tana,
  oila, pul, sog'liq va haqiqiy muvaffaqiyatsizlik ustidan kulinmaydi.
- **Ilovaga hech qanday kalit qo'shilmaydi** (API, ElevenLabs, token). Har kim o'z kalitini
  kiritadi. Kalitsiz ham animatsiyalar, tayyor gaplar, vazifalar va eslatmalar ishlaydi.
- **Shaxsiy narsalar yo'q:** kodda, testlarda, personada muallifning ismi, laqabi, uy papkasi
  yo'llari, emaili, ovoz namunasi bo'lmaydi.
- **Nora bilan yonma-yon:** ma'lumotlar `%APPDATA%\Yue`, exe `Yue.exe`, o'rnatish papkasi
  `%LOCALAPPDATA%\Programs\Yue`, Inno AppId, avtostart nomi "Yue", lock (`yue.lock`),
  QLocalServer (`yue-ctl-…`), AppUserModelID (`Yue.DesktopCompanion`), tezkor tugma ID lari —
  hammasi Nora'nikidan farqli. Muhit o'zgaruvchilari: `YUE_DATA`, `YUE_DEBUG`, `YUE_PACK`,
  `YUE_PERIOD`.
- Tezkor tugmalar Sozlamalarda o'zgaradi: ko'rsatish/yashirish (standart Ctrl+Alt+Y, `pet.hotkey`,
  Umumiy) va ovozni jim qilish (standart Ctrl+Alt+Shift+U, `voice.hotkey`, Ovoz). Band bo'lsa —
  logga va Sozlamalarga izoh.

## Manbalar
- Rasmlar manbasi Nora'da (`C:\nora\art_src`, tayyor to'plam `C:\nora\assets\packs\nora_ai`).
  Yue'da `assets/packs/yue/` ni qo'lda tahrirlama — yangilash faqat `tools/sync_pack.py` bilan
  (yue.ico nomi, "love" ifodasini chaqiriladigan ro'yxatlardan chiqarish shu skriptda).
- Persona va promptlar: `persona/` (`harakatlar.json` — Yue bajaradigan buyruqlar; yangi harakat =
  shu fayl + `persona_uz.txt` dagi HARAKATLAR ro'yxati + `persona_qisqa_uz.txt` dagi teglar).
- Foydalanuvchi ma'lumotlari: `%APPDATA%\Yue\` (`yue.db`, `config.json`, `logs\`, `voice\`,
  `ctl.token`). `config.json` sxemasi 1-versiyadan boshlangan (Nora migratsiyalari yo'q).

## Xavfsizlik (o'zgarmas)
- API kalitlar faqat DPAPI bilan himoyalangan holda `config.json` da. Kodda, logda, testlarda,
  git'da kalit yo'q.
- Suhbat, fakt, sog'liq, vazifa matnlari SQLite'da AES-GCM bilan shifrlangan.
- Loglarda xabar matni, oyna sarlavhalari, kalitlar yo'q (redaksiya filtri bor).
- `subprocess` faqat ro'yxat argumentlari bilan, `shell=True` yo'q. TLS tekshiruvini o'chirma.
- AI javobidan faqat oq ro'yxatdagi teglar bajariladi. Model kompyuterda boshqa hech narsa qila
  olmaydi. Ro'yxatda yo'q harakat (o_pish va h.k.) e'tiborsiz qoladi, `[love]` → `happy`.
- `private=False` provayderga (bepul Gemini) sog'liq daftari va shaxsiy faktlar yuborilmaydi.
- Ovoz (`yue/voice/`): ElevenLabs kaliti SecretStore'da `elevenlabs_key`; TTS so'rovi faqat
  Online'da. AI javoblari keshlanmaydi, keshda faqat tayyor iboralar (`%APPDATA%\Yue\voice\`).
  `voice.voice_id` faqat ElevenLabs formatida (`valid_voice_id`).

## AI
- Router zanjiri, cooldown va oflayn navbat — `yue/ai/router.py`. Foydalanuvchi hech qachon
  "limit/quota/429/keyinroq yozing" ko'rmaydi.
- Model nomlari `config.py` dagi standartlarda; o'zgartirishdan oldin rasmiy hujjatni tekshir.
- AI manbasi `ai.manba` (`yue/modes.py`): "online" (faqat bulut: Claude, Gemini, OpenRouter) yoki
  "offline" (faqat Ollama). OpenRouter so'rovlari `provider.data_collection="deny"` bilan.
- Iboralar: `{ism}` — `user.name` (bo'sh bo'lsa olib tashlanadi). Ovoz: talaffuz —
  `persona/talaffuz.json` (faqat ovoz matniga, "Yue" → "Yu-e"); bosqichlar —
  `persona/ovoz_bosqich.json`.
- Testlarda tarmoq yo'q — soxta provayderlar.

## Kod uslubi
- Python 3.12+, type hints, `ruff` bilan format. OS'ga bog'liq hamma narsa `yue/platform/` da.
- UI oqimini bloklama: AI so'rovlari alohida thread/async'da, natija Qt signal orqali.
- Har bosqich oxirida testlar o'tsin, ruff toza bo'lsin va commit qil.
