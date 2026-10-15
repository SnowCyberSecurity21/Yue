# Claude Code uchun: v1.3.2 — ovozning kunlik chegarasi va reaksiyani kesayotgan gap

```
Ikkita tuzatish bor.

## A. Ovozning kunlik chegarasi
Nima bo'ldi:
- 15-oktabr soat 00:55 da kunlik chegara tugadi. config: voice.usage = {chars: 2992, off: true}, voice.daily_chars = 3000.
- O'shandan beri Nora butunlay jim.
- Logda ham, tray'da ham bu haqda hech narsa yo'q, shuning uchun foydalanuvchi ovoz buzilgan deb o'yladi.
- 3000 harf soat 00:11 dan 00:55 gacha ketgan, asosan AI javoblarini ovozda o'qishga.

1. Keshdagi iboralar chegara tugagandan keyin ham o'ynasin.
   - Kesh kredit sarflamaydi, lekin hozir active() ichidagi off_today() uni ham jim qilib qo'yadi.
   - off_today() ni active() dan olib tashla. Chegara faqat jonli so'rovni to'xtatsin (_live / _within_limit).
   - Chegara tugaganda aytiladigan ibora ("ovoz", "chegara") keshda bo'lsa, u ovozda aytilsin.
2. Chegarani o'zgartirsa, bugungi o'chirish bekor bo'lsin.
   - Hozir Sozlamalarda chegarani oshirsa ham voice.usage.off true bo'lib qoladi va ovoz faqat ertaga qaytadi.
   - Saqlashda yangi chegara 0 (cheklovsiz) bo'lsa yoki bugun ishlatilgandan katta bo'lsa, off false bo'lsin.
   - Chegara o'zgarmagan bo'lsa, off ham o'zgarmasin. Aks holda 2992/3000 holatida har saqlashda chegara iborasi qaytadan aytiladi.
3. Foydalanuvchi buni ko'rsin.
   - Chegara tugaganda pufakdagi iboradan tashqari tray bildirishnomasi ham chiqsin, kuniga bir marta. Sarlavha voice.notify.title, matn taxminan: "Bugungi ovoz chegarasi tugadi (3000 harf). Ovoz ertaga qaytadi yoki Sozlamalar → Ovoz bo'limida chegarani oshiring."
   - Tray menyusidagi "Ovoz" bandi: off_today bo'lsa, yonida "(bugungi chegara tugadi)".
4. Log.
   - Chegara tugaganda INFO qator: "ovoz: kunlik chegara tugadi (2992/3000)".
   - Ishga tushganda bitta INFO qator: ovoz yoqilganmi, manba online'mi, voice_id bormi (ha/yo'q), kalit bormi (ha/yo'q), bugun ishlatilgan/chegara, off. Kalit va voice_id qiymatlari yozilmasin.

## B. Gap reaksiya animatsiyasini kesmasin
1.3.1 hisobotingda yozgan muammo: tashlanganda land deyarli ko'rinmaydi, chunki darhol aytiladigan gap uni talk bilan to'xtatadi. Ha, tuzat.
- Bir martalik reaksiyalar oxirigacha o'ynasin: land, sayr oxiridagi wave, qaytgandagi wave, excited_jump va shunga o'xshashlari.
- Pufak va ovoz avvalgidek darhol chiqadi, faqat talk animatsiyasi kutib turadi.
- Reaksiya tugaganda:
  - gap hali davom etayotgan bo'lsa, talk boshlansin;
  - gap tugagan bo'lsa, talk'siz gapdan keyingi ifoda yoki odatiy reja davom etsin (after_talk dagidek).
- Sudrash (dangle), uyqu va foydalanuvchi buyrug'i (command) qoidalari o'zgarmaydi.
- Qaysi reaksiyalarda shu muammo bo'lganini o'zing tekshir va hisobotda ro'yxatini yoz.

## Testlar
- off_today paytida keshdagi ibora o'ynaydi, jonli so'rov yuborilmaydi.
- Chegara oshirilsa yoki 0 qilinsa, off bekor bo'ladi. Chegara o'zgarmasa, off qoladi.
- Chegara tugaganda bildirishnoma bir marta chiqadi, log qatori yoziladi, menyu bandida belgi paydo bo'ladi.
- Ishga tushish log qatorida kalit va voice_id qiymatlari yo'q.
- land paytida set_talking(True) kelsa, land oxirigacha o'ynaydi, keyin talk boshlanadi. Gap land davomida tugasa, talk umuman boshlanmaydi.
- Sayr oxiridagi wave ham xuddi shunday ishlaydi.
- Barcha eski testlar o'tsin, ruff toza.

## Yakunda
- Versiya 1.3.2. dist va setup'ni yig', jim o'rnat. Logda bitta "ishga tushdi" bo'lsin, xato bo'lmasin.
- Commit va push.
- Qisqa o'zbekcha hisobot: nima o'zgardi, qaysi reaksiyalar kesilayotgan edi, qanday muammolar qoldi.
```
