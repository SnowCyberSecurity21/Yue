# Claude Code uchun: "N" → "Y" ni bekor qilish va Yue 1.0.0 ni yakunlash

```
cc_yue_2.md dagi 4-qism ("N" → "Y") bekor qilindi: xudidagi "N" harfi qoladi. Shu qism bo'yicha qilingan hamma o'zgarishni orqaga qaytar, keyin ishni yakunla.

## A. "N" → "Y" ni orqaga qaytarish
- git status va git log bilan 4-qismda nima o'zgarganini aniqla. 3-qism push qilingandan keyingi hamma narsa shu qismga tegishli.
- Commit qilinmagan o'zgarishlarni olib tashla:
  - tools\logo.py;
  - sync_pack.py dagi logo bosqichi va --review;
  - requirements.txt ga qo'shilgan numpy;
  - harf namunalari, shablonlar va boshqa yordamchi fayllar.
- Bulardan birortasi commit qilingan bo'lsa, push qilingan tarixni qayta yozma, alohida revert commit qil.
- 3-qismda yozilgan joylarni ham tozala:
  - DEVELOPING.md dagi "N harfini Y ga almashtiradi" gapi va --review;
  - README, CHANGELOG, testlar va boshqa joylarda "Y" harfi haqida gap bo'lsa, uni ham.
- build\review\ ni o'chir.
- numpy faqat logo uchun o'rnatilgan bo'lsa, uni .venv dan ham olib tashla. requirements.txt Nora'dagidek bo'lsin.
- assets\packs\yue ni sync_pack.py bilan qayta yasa. Natija C:\nora\assets\packs\nora_ai bilan bir xil bo'lsin, faqat kelishilgan ikki farq qoladi: yue.ico nomi va pack.json'dan olib tashlangan "love". Fayllar xeshini solishtirib tekshir.
- Persona:
  - docs\yue_persona.txt da bitta qator o'zgardi: xudidagi "N" — "Night, tungi smenaning formasi". Faylni qaytadan persona\persona_uz.txt ga ko'chir.
  - persona_qisqa_uz.txt da xudidagi harf haqida gap bo'lsa, unga moslashtir.
- Testlar o'tsin, ruff toza bo'lsin. Commit va push.

## B. Ishni yakunlash
- docs\cc_yue_2.md dagi 5-qismni (yangi foydalanuvchi sifatida sinov) va 6-qismni (1.0.0 reliz) bajar.
- 6-qism hisobotida "N" → "Y" bandi kerak emas. O'rniga A qismida nima orqaga qaytarilganini yoz.
- docs\yue_reja.md va docs\yue_persona.txt yangilangan, ularni ham commit qil.
```
