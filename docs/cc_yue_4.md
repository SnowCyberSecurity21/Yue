# Claude Code uchun: Yue 1.0.1 — tarqatishdan oldingi mayda tuzatishlar

```
1.0.0 hisobotidagi ochiq qolgan narsalarni yop va 1.0.1 ni chiqar. C:\nora ga tegma.

## 1. Fayllar har qanday kompyuterda ochilsin
- Start menyusidagi "Yue — qo'llanma" README.md ni ochyapti. .md fayli dasturga bog'lanmagan kompyuterda Windows qaysi dastur bilan ochishni so'raydi. LICENSE faylida esa kengaytma umuman yo'q, u ham shunday bo'ladi.
- Tuzatish:
  - yig'ishda README.md dan README.html yasalsin. Yangi paket qo'shma: PySide6'dagi QTextDocument.setMarkdown → toHtml yetadi. Sahifa o'qishga qulay bo'lsin: oddiy CSS, kenglik ~800 px, rasm bilan (docs\yue.png ham yoniga ko'chiriladi);
  - o'rnatish papkasiga LICENSE fayli LICENSE.txt nomi bilan tushsin;
  - Start menyusidagi qo'llanma yorlig'i va "Yue haqida" oynasidagi tugmalar README.html, LICENSE.txt va THIRD_PARTY_LICENSES.txt ni ochsin;
  - "Yue haqida" oynasi o'rnatilmagan (manba) holatda ham ishlasin.

## 2. pack.json dagi "Nora" matnlari
- 1.0.0 da pack.json dagi name va izohlar yana Nora'nikiga qaytdi.
- Tekshir: pack.json dagi matnlar foydalanuvchiga ko'rinadimi (oyna, menyu, xato, log'dan tashqari joylar) yoki AI promptiga tushadimi?
  - Tushsa: sync_pack.py ularda "Nora" ni "Yue" ga almashtirsin. Bu kelishilgan uchinchi farq bo'ladi, testi va DEVELOPING.md dagi izohi bilan.
  - Tushmasa: tegma, faqat hisobotda yoz.

## 3. O'chirishdagi "ma'lumotlarni ham o'chiraymi?" savolini sinash
- Avval %APPDATA%\Yue ni zaxiraga ko'chir.
- Uninstaller'ni oddiy (jim emas) rejimda ishga tushir (UI Automation bilan):
  - "Yo'q" javobida %APPDATA%\Yue qoladi;
  - qayta o'rnatib, "Ha" javobida %APPDATA%\Yue o'chadi;
  - ikkala holatda ham %APPDATA%\Nora va Nora o'rnatmasi joyida qoladi.
- Oxirida zaxirani qaytar va 1.0.1 ni jim o'rnat (avtostartsiz). Sozlamalar va Ctrl+Alt+Shift+Y joyida qolsin.

## 4. Reliz 1.0.1
- Versiyani hamma joyda 1.0.1 qil, CHANGELOG'ga yoz.
- docs\release_1.0.1.md: nima o'zgardi va setup faylining SHA256.
- Testlar o'tsin, ruff toza bo'lsin. Logda bitta "Yue 1.0.1 ishga tushdi" qatori bo'lsin, xato bo'lmasin.
- Commit, git tag v1.0.1, push (teglar bilan).
- Qisqa o'zbekcha hisobot: har qism natijasi, setup hajmi va SHA256.
```
