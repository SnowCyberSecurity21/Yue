# Yue

Windows 10/11 uchun ish stoli hamrohi: kichkina chibi qiz taskbar va oynalar ustida yuradi, o'zbek
tilida gaplashadi, vazifalarni eslatadi va g'amxo'rlik qiladi. Nora asosida yasalgan, romantikasiz.

Bu fayl — dasturchi uchun. Foydalanuvchi uchun README keyingi bosqichda yoziladi.

## Ishga tushirish

```powershell
py -3.12 -m venv .venv
.venv\Scripts\pip install -r requirements.txt               # xeshlar bilan qotirilgan
.venv\Scripts\python -m yue                                 # ishga tushirish
.venv\Scripts\python -m pytest -q                           # testlar (tarmoqsiz)
.venv\Scripts\python -m ruff check . ; .venv\Scripts\python -m ruff format --check .
.venv\Scripts\pip-audit -r requirements.txt --disable-pip   # zaifliklar tekshiruvi
```

Muhit o'zgaruvchilari: `YUE_DEBUG=1` — batafsil log va "Sinov" menyusi; `YUE_PERIOD=night` — kun
qismini qotirish; `YUE_DATA=papka` — ma'lumotlar papkasi (standart `%APPDATA%\Yue`);
`YUE_PACK=<nom>` — `assets/packs/<nom>` to'plami.

## Rasmlar

Rasm va animatsiyalar manbasi Nora'da. Yue tayyor to'plamni ko'chirib oladi:

```powershell
.venv\Scripts\python tools\sync_pack.py                     # C:\nora\assets\packs\nora_ai → assets\packs\yue
.venv\Scripts\python tools\sync_pack.py D:\boshqa\nora_ai   # boshqa manba
```

`assets\packs\yue` ni qo'lda tahrirlamang.

## Yig'ish

```powershell
.venv\Scripts\pyinstaller build\yue.spec --noconfirm        # dist\Yue\Yue.exe
"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" build\yue.iss   # dist\Yue-0.1.0-setup.exe
```

O'rnatuvchi administrator huquqisiz `%LOCALAPPDATA%\Programs\Yue` ga o'rnatadi. Nora bilan bir
kompyuterda yonma-yon ishlaydi: ma'lumotlar papkasi, AppId, avtostart, lock va boshqaruv kanali
alohida.

## Tuzilma

`yue/pet` (personaj, fizika, kiyim), `yue/ai` (provayderlar, router, prompt, teglar), `yue/memory`
(shifrlash, ombor, xulosa), `yue/tasks`, `yue/voice`, `yue/ui`, `yue/platform` (Windows),
`persona/` (persona, iboralar, harakatlar), `tools/sync_pack.py`. Qoidalar: [`CLAUDE.md`](CLAUDE.md),
reja: [`docs/yue_reja.md`](docs/yue_reja.md).
