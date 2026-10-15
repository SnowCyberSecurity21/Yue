"""Interfeys satrlari. Til faqat o'zbek (lotin) — OS tiliga qarab tanlanmaydi.

Yangi UI satri faqat shu yerga qo'shiladi; kodda `t("kalit")` bilan olinadi.
`tests/test_i18n.py` bu yerda inglizcha so'z yo'qligini va UI modullarida matn qattiq
yozilmaganini tekshiradi.
"""

from __future__ import annotations

LANG = "uz"

STRINGS: dict[str, str] = {
    "app.name": "Yue",
    "app.tagline": "Ish stolingizdagi hamroh",
    # --- Menyu -----------------------------------------------------------------------------
    "menu.chat": "Gaplashish",
    "menu.sleep": "Uxla",
    "menu.wake": "Uyg'on",
    "menu.pat": "Boshini silash",
    "menu.wave": "Qo'l silkit",
    "menu.summon": "Bu yerga kel",
    "menu.tasks": "Vazifalar",
    "menu.tasks.add": "Vazifa qo'shish…",
    "menu.tasks.remind": "Vazifalarni eslat",
    "menu.tasks.empty": "Ochiq vazifa yo'q",
    "menu.tasks.done": "Bajarildi",
    "menu.tasks.delete": "O'chirish",
    "menu.outfit": "Kiyim",
    "menu.outfit.auto": "Avtomatik (soatga qarab)",
    "menu.outfit.manual": "Qo'lda tanlash…",
    "menu.outfit_now": "Kiyimni almashtir",
    "menu.settings": "Sozlamalar…",
    "menu.memory": "Xotiram…",
    "menu.hide": "Yashirish",
    "menu.show": "Ko'rsatish",
    "menu.about": "Dastur haqida",
    "menu.quit": "Chiqish",
    "menu.debug": "Sinov",
    "menu.period": "Kun qismi",
    "menu.period.auto": "Avtomatik (soat bo'yicha)",
    "menu.action": "Harakat",
    "menu.debug.outfit": "Kiyim (darhol)",
    "menu.debug.expression": "Ifoda",
    "menu.debug.speed": "Yurish tezligi",
    "menu.debug.no_art": "{name} — rasm yo'q",
    "menu.debug.drop": "Yiqilish (ekran tepasidan)",
    "menu.debug.blink": "Ko'z yumib-ochish (darhol)",
    "menu.debug.commands": "Buyruq",
    "menu.debug.sayr30": "Sayr (30 s)",
    "expr.neutral": "Odatiy (qovog'i solingan)",
    "expr.happy": "Xursand",
    "expr.excited": "Hayajonda",
    "expr.angry": "Jahli chiqqan",
    "expr.sad": "Xafa",
    "expr.surprised": "Hayron",
    "expr.sleepy": "Uyqusi kelgan",
    "expr.smug": "Mag'rur",
    "expr.curious": "Qiziqib qolgan",
    "expr.disgusted": "Jirkangan",
    "expr.thinking": "O'ylanib qolgan",
    "expr.shy": "Uyalgan",
    "period.morning": "Ertalab",
    "period.day": "Kunduzi",
    "period.evening": "Kechqurun",
    "period.night": "Tun",
    # --- Harakatlar (slot) nomlari ---------------------------------------------------------
    "slot.idle": "Kutish",
    "slot.walk": "Yurish",
    "slot.walk_music": "Musiqa tinglab yurish",
    "slot.walk_pocket": "Qo'l cho'ntakda yurish",
    "slot.talk": "Gapirish",
    "slot.wave": "Qo'l silkitish",
    "slot.sitdown": "O'tirish",
    "slot.sit": "O'tirib turish",
    "slot.sleep": "Uxlash",
    "slot.dangle": "Osilib qolish",
    "slot.fall": "Yiqilish",
    "slot.type": "Noutbukda ishlash",
    "slot.music": "Musiqa tinglash",
    "slot.look_around": "Atrofga alanglash",
    "slot.butterfly": "Kapalakni kuzatish",
    "slot.flower": "Gulni hidlash",
    "slot.ponder": "O'ylanish",
    "slot.tea": "Choy ichish",
    "slot.stretch": "Kerishish",
    "slot.excited_jump": "Sakrash",
    "slot.angry_stomp": "Depsinish",
    "slot.train": "Boks mashqi",
    "slot.expressions": "Yuz ifodalari",
    "slot.standup": "Turish",
    "slot.land": "Yerga tushish",
    "slot.hood_up": "Kapyushon kiyish",
    "slot.hood_down": "Kapyushon yechish",
    # --- Gap pufagi --------------------------------------------------------------------------
    "bubble.placeholder": "Yuega yozing…  (Enter — yuborish, Shift+Enter — yangi qator)",
    "bubble.send": "Yuborish",
    "bubble.copy": "Nusxalash",
    "bubble.copied": "Nusxalandi",
    "bubble.close": "Yopish (Esc)",
    "bubble.thinking": "Yue o'ylayapti…",
    # --- Matn maydoni menyusi -----------------------------------------------------------------
    "edit.undo": "Bekor qilish",
    "edit.redo": "Qaytarish",
    "edit.cut": "Kesish",
    "edit.copy": "Nusxalash",
    "edit.paste": "Qo'yish",
    "edit.delete": "O'chirish",
    "edit.select_all": "Hammasini belgilash",
    # --- Umumiy tugmalar ----------------------------------------------------------------------
    "btn.save": "Saqlash",
    "btn.cancel": "Bekor qilish",
    "btn.close": "Yopish",
    "btn.yes": "Ha",
    "btn.no": "Yo'q",
    "btn.next": "Keyingisi",
    "btn.back": "Orqaga",
    "btn.finish": "Boshlash",
    "btn.add": "Qo'shish",
    "btn.delete": "O'chirish",
    "btn.check": "Tekshirish",
    "btn.show_key": "Ko'rsatish",
    # --- Vazifa qo'shish oynasi --------------------------------------------------------------
    "task.title": "Yangi vazifa",
    "task.text": "Nima qilish kerak?",
    "task.text.placeholder": "Masalan: dori ichish",
    "task.when": "Qachon? (bo'sh qoldirsangiz — muddatsiz)",
    "task.when.placeholder": "15:30 · ertaga 9:00 · har kuni 08:00 · 30 daqiqadan keyin",
    "task.when.bad": "Vaqtni tushunmadim. Masalan: «ertaga 9:00» yoki «2026-10-20 14:00».",
    "task.added": "Qo'shildi: {text}",
    # --- Sozlamalar ---------------------------------------------------------------------------
    "settings.title": "Yue — sozlamalar",
    "settings.tab.ai": "AI",
    "settings.tab.yue": "Yue",
    "settings.tab.reminders": "Eslatmalar",
    "settings.tab.wardrobe": "Kiyim",
    "settings.tab.privacy": "Xotira",
    "settings.tab.general": "Umumiy",
    "settings.tab.voice": "Ovoz",
    "ai.claude_key": "Claude kaliti",
    "ai.gemini_key": "Gemini kaliti",
    "ai.openrouter_key": "OpenRouter kaliti",
    "ai.openrouter_model": "OpenRouter modeli",
    "ai.openrouter.hint": (
        "OpenRouter — qo'shimcha bulut model. So'rovlar faqat ma'lumotni o'qitishga "
        "ishlatmaydigan provayderlarga yuboriladi."
    ),
    "ai.group.source": "Ishlash rejimi",
    "ai.group.keys": "Kalitlar",
    "ai.group.model": "Model",
    "ai.group.cost": "Xarajat",
    "ai.source.online": "Online",
    "ai.source.offline": "Offline",
    "ai.source.hint": (
        "Online — bulutdagi AI (Claude, Gemini, OpenRouter). Offline — faqat kompyuterdagi "
        "Ollama modeli: gaplaringiz, tarjima va xotira xulosasi ham tashqariga chiqmaydi."
    ),
    "ai.get_openrouter": "Kalit olish: openrouter.ai",
    "ai.key.placeholder.saved": "Saqlangan (o'zgartirish uchun yangisini kiriting)",
    "ai.key.placeholder.empty": "Kalitni shu yerga qo'ying",
    "ai.key.remove": "Kalitni o'chirish",
    "ai.get_claude": "Kalit olish: platform.claude.com",
    "ai.get_gemini": "Kalit olish: aistudio.google.com",
    "ai.gemini_paid": "Gemini kalitim pullik (hisob-kitob ulangan)",
    "ai.gemini_paid.hint": (
        "Bepul Gemini'da Google so'rovlarni modelni yaxshilash uchun ishlatishi va odamlar ko'rib "
        "chiqishi mumkin. Shuning uchun bepul Gemini'ga sog'liq daftari, shaxsiy faktlar va "
        "xotira yuborilmaydi."
    ),
    "ai.primary": "Asosiy provayder",
    "ai.primary.claude": "Claude",
    "ai.primary.gemini": "Gemini",
    "ai.primary.openrouter": "OpenRouter",
    "ai.mode": "Rejim",
    "ai.mode.fast": "Tez (Haiku)",
    "ai.mode.smart": "Aqlliroq (Sonnet)",
    "ai.budget": "Kunlik xarajat chegarasi",
    "ai.budget.off": "o'chirilgan",
    "ai.budget.hint": "Faqat ogohlantiradi — Yue javob berishda davom etadi.",
    "ai.today": "Bugun: {requests} ta so'rov, taxminan ${cost}",
    "ai.check.running": "Tekshirilyapti…",
    "ai.check.ok": "Ishlayapti ✓ ({model})",
    "ai.check.no_key": "Avval kalitni kiriting.",
    "ai.check.auth": "Kalit noto'g'ri yoki ruxsati yo'q.",
    "ai.check.billing": "Kalit to'g'ri, lekin hisobda mablag' yo'q.",
    "ai.check.network": "Internetga ulanib bo'lmadi.",
    "ai.check.busy": "Kalit ishlayapti, lekin server hozir band. Birozdan keyin qayta tekshiring.",
    "ai.check.daily": "Kalit ishlayapti, bugungi bepul so'rovlar tugagan (ertaga yangilanadi).",
    "ai.check.other": "Javob olinmadi. Kalit va internetni tekshiring.",
    "ai.check.prompt": "Salom! Bitta qisqa gap bilan o'zbekcha javob ber.",
    "yue.size": "O'lchami",
    "yue.walk_windows": "Oynalar ustida yurishi mumkin",
    "yue.hide_fullscreen": "To'liq ekranli dasturlarda yashirinsin",
    "yue.chatter": "O'zi gap boshlashi",
    "yue.chatter.every": "har {n} daqiqada",
    "yue.chatter.off": "hech qachon",
    "yue.sleep_after": "Siz shuncha vaqt jim tursangiz, uxlaydi",
    "yue.humor": "Hazil darajasi",
    "yue.humor.low": "kam",
    "yue.humor.medium": "o'rtacha",
    "yue.humor.high": "ko'p",
    "minutes": "{n} daqiqa",
    "minutes.suffix": " daqiqa",
    "rem.tasks_every": "Ochiq vazifalarni eslatish",
    "rem.break": "Tanaffus eslatmasi (uzluksiz ishlagandan keyin)",
    "rem.battery": "Batareya kamayganda ogohlantirish",
    "rem.off": "o'chirilgan",
    "wardrobe.mode": "Kiyim tanlash",
    "wardrobe.auto": "Avtomatik — kun vaqtiga qarab",
    "wardrobe.manual": "Qo'lda",
    "wardrobe.outfit": "Kiyim",
    "wardrobe.glasses": "Ko'zoynak",
    "wardrobe.phones": "Quloqchin",
    "wardrobe.hood": "Kapyushon (xudida yurganda)",
    "choice.auto": "Avtomatik",
    "choice.on": "Har doim",
    "choice.off": "Hech qachon",
    "outfit.tee": "Oq futbolka",
    "outfit.hoodie_black": "Qora xudi",
    "outfit.hoodie_silver": "Kumushrang xudi",
    "phones.head": "Boshda",
    "phones.neck": "Bo'yinda",
    "phones.none": "Yo'q",
    "privacy.status": (
        "Suhbatlar, faktlar, sog'liq daftari va vazifalar kompyuteringizda AES-256-GCM bilan "
        "shifrlangan. Shifr kaliti va API kalitlari Windows DPAPI bilan himoyalangan — ularni "
        "faqat sizning Windows hisobingiz ocha oladi."
    ),
    "privacy.location": "Ma'lumotlar papkasi: {path}",
    "privacy.open_memory": "Xotiramni ko'rish…",
    "privacy.open_folder": "Papkani ochish",
    "general.autostart": "Windows bilan birga ishga tushsin",
    "general.hotkey": "Ko'rsatish/yashirish tugmasi",
    "general.hotkey.ok": "{combo} — Yueni ko'rsatish/yashirish",
    "general.hotkey.busy": "Bu birikma band, boshqasini tanlang.",
    "general.hotkey.invalid": (
        "Bu birikma ishlamaydi: Ctrl, Alt yoki Win bilan birga harf, raqam yoki F1–F24 tanlang."
    ),
    "general.shortcut": "Ish stolida yorliq yaratish",
    "general.shortcut.done": "Yorliq yaratildi.",
    "general.shortcut.fail": "Yorliq yaratilmadi.",
    "general.name": "Ismingiz (Yue sizga shunday murojaat qiladi)",
    # --- Birinchi ochilish ------------------------------------------------------------------
    "welcome.title": "Yue bilan tanishuv",
    "welcome.hello": "Salom! Men Yueman.",
    "welcome.intro": (
        "Ish stolingizda yashayman: oynalar ustida yuraman, vazifalaringizni eslab qolaman va "
        "o'z vaqtida eslataman, tanaffus qilishni aytaman. Men bilan o'zbek tilida "
        "gaplashishingiz mumkin."
    ),
    "welcome.name": "Sizni qanday chaqiray?",
    "welcome.name.placeholder": "Ismingiz",
    "welcome.keys": "Men o'ylashim uchun AI kaliti kerak",
    "welcome.keys.intro": (
        "Kamida bittasini kiriting. Claude — asosiy (tez va maxfiy), Gemini — zaxira. Kalitlar "
        "faqat shu kompyuterda, Windows himoyasi ostida saqlanadi."
    ),
    "welcome.gemini_warning": (
        "Diqqat: bepul Gemini tarifida Google so'rovlarni o'z modellarini yaxshilash uchun "
        "ishlatishi mumkin, ularni odamlar ham ko'rib chiqadi; Google shaxsiy ma'lumot "
        "yubormaslikni so'raydi. Shuning uchun bepul Gemini'ga sog'liq daftari va shaxsiy "
        "faktlaringizni yubormayman. API'dan foydalanish uchun 18 yoshdan katta bo'lish kerak."
    ),
    "welcome.later": "Kalitlarni keyinroq Sozlamalar → AI bo'limida ham ulash mumkin.",
    "welcome.start": "Oxirgi qadam",
    "welcome.autostart": "Kompyuter yoqilganda meni ham ishga tushiring",
    "welcome.shortcut": "Ish stolida yorliq yarating",
    "welcome.hotkey": "Meni {combo} bilan istalgan vaqtda yashirish yoki chaqirish mumkin.",
    # --- Xotira oynasi ----------------------------------------------------------------------
    "memory.title": "Yue — xotiram",
    "memory.summary": "Suhbatlar xulosasi",
    "memory.summary.empty": "Hali xulosa yo'q.",
    "memory.facts": "Siz haqingizda",
    "memory.health": "Sog'liq daftari",
    "memory.tasks": "Vazifalar",
    "memory.empty": "Bo'sh",
    "memory.clear": "Xotirani tozalash…",
    "memory.clear.confirm": (
        "Suhbatlar, xulosa, faktlar va sog'liq daftari butunlay o'chiriladi. Vazifalar qoladi. "
        "Davom etamizmi?"
    ),
    "memory.export": "Eksport (JSON)…",
    "memory.export.warn": (
        "Eksport fayli SHIFRLANMAGAN bo'ladi: unda suhbatlar, faktlar va sog'liq daftari ochiq "
        "matnda saqlanadi. Faylni xavfsiz joyda saqlang va kerak bo'lmasa o'chiring. "
        "Davom etamizmi?"
    ),
    "memory.export.file": "yue-xotira.json",
    "memory.export.filter": "JSON fayl (*.json)",
    "memory.export.done": "Saqlandi: {path}",
    "memory.export.fail": "Faylni saqlab bo'lmadi.",
    "memory.reset": "Oldingi xotirani ochib bo'lmadi, shuning uchun yangidan boshladim.",
    # --- Dastur haqida ---------------------------------------------------------------------
    "about.title": "Yue haqida",
    "about.text": (
        "Yue {version}\n\nWindows uchun ish stoli hamrohi va o'zbek tilida gaplashadigan AI "
        "yordamchi.\n\nAI: Claude (Anthropic), Gemini (Google), OpenRouter.\nMa'lumotlaringiz shu "
        "kompyuterda shifrlangan holda saqlanadi.\n\nMa'lumotlar papkasi:\n{path}"
    ),
    # --- Bildirishnomalar -------------------------------------------------------------------
    "notify.task_title": "Yue — eslatma",
    "notify.answer_title": "Yue javob berdi",
    "notify.claude_key": "Claude kaliti ishlamayapti — Sozlamalar → AI",
    "notify.gemini_key": "Gemini kaliti ishlamayapti — Sozlamalar → AI",
    "notify.openrouter_key": "OpenRouter kaliti ishlamayapti — Sozlamalar → AI",
    "notify.claude_billing": "Claude hisobida mablag' tugagan — Sozlamalar → AI",
    "notify.gemini_billing": "Gemini hisobida mablag' tugagan — Sozlamalar → AI",
    "notify.openrouter_billing": "OpenRouter hisobida mablag' tugagan — Sozlamalar → AI",
    "notify.running": "Yue shu yerda. Ko'rsatish yoki yashirish: {combo}.",
    # --- Xatolar ---------------------------------------------------------------------------
    "error.pack": "Yuening rasmlari topilmadi yoki buzilgan. Dasturni qayta o'rnating.",
    "error.title": "Yue — xato",
    "error.unexpected": "Kutilmagan muammo yuz berdi. Yue ishlashda davom etadi.",
    # --- Buyruq qatori ---------------------------------------------------------------------
    "cli.description": "Yue - ish stoli hamrohi.",
    "cli.help": "Yordamni ko'rsatish.",
    "cli.version": "Versiyani ko'rsatish.",
    "cli.toggle": "Ishlab turgan Yueni ko'rsatish/yashirish.",
    "cli.autostart": "Windows bilan ishga tushganda (biroz kechikib) ochilish.",
    "cli.bad_arg": "yue: noto'g'ri parametr. Yordam: python -m yue --help",
    # --- AI manbasi (Online/Offline) va Offline model -----------------------------------------
    "menu.online": "Online",
    "menu.offline": "Offline",
    "notify.local_missing": "Offline model tanlanmagan — Sozlamalar → Offline",
    "settings.tab.local": "Offline",
    "local.intro": (
        "Offline rejimda Yue kompyuteringizning o'zidagi modelda ishlaydi (Ollama): internet "
        "bo'lmasa ham javob beradi, gaplaringiz hech qayerga ketmaydi. Bulutdagidan sekinroq va "
        "soddaroq. Rejimni AI bo'limida tanlang."
    ),
    "local.model": "Model",
    "local.refresh": "Yangilash",
    "local.checking": "Ollama tekshirilmoqda…",
    "local.found": "Ollama ishlayapti, o'rnatilgan modellar: {count} ta.",
    "local.no_models": (
        "Ollama ishlayapti, lekin model o'rnatilmagan. Terminalda: ollama pull <model>"
    ),
    "local.missing": (
        "Ollama ishlamayapti. Ollama'ni ollama.com dan o'rnating, keyin terminalda: "
        "ollama pull <model>"
    ),
    "local.install": (
        "O'rnatish: ollama.com dan Ollama'ni yuklab o'rnating, terminalda «ollama pull <model>» "
        "buyrug'ini bering (masalan, 3–4 mlrd parametrli model), so'ng «Yangilash» ni bosing."
    ),
    # --- Ovoz (ElevenLabs) --------------------------------------------------------------------
    "menu.voice": "Ovoz",
    "general.hotkey.voice": "{combo} — ovozni jim o'chirish/yoqish (Sozlamalar → Ovoz)",
    "general.hotkey.voice.busy": (
        "{combo} boshqa dastur tomonidan band — Sozlamalar → Ovoz'da boshqa birikma tanlang yoki "
        "menyudagi «Ovoz» katakchasidan foydalaning."
    ),
    "voice.hotkey": "Jim qilish tugmasi",
    "voice.hotkey.ok": "{combo} — ovozni jim o'chirish/yoqish",
    "voice.hotkey.busy": "Bu birikma band, boshqasini tanlang.",
    "voice.hotkey.invalid": (
        "Bu birikma ishlamaydi: Ctrl, Alt yoki Win bilan birga harf, raqam yoki F1–F24 tanlang."
    ),
    "voice.voice_id.key": (
        "Bu API kalitga o'xshaydi. Kalit yuqoridagi maydonga yoziladi, Ovoz ID bo'sh qolsin — "
        "«Tekshirish» o'zi topadi."
    ),
    "voice.voice_id.bad": (
        "Ovoz ID noto'g'ri: u faqat lotin harf va raqamlardan iborat (odatda 20 ta). Bo'sh "
        "qoldirsangiz, «Tekshirish» o'zi topadi."
    ),
    "voice.check.perm": (
        "Kalitda ruxsat yetishmayapti. ElevenLabs → Developers → API Keys → ⋯ → Edit: "
        "Text to Speech → Access, Voices → Read, User → Access."
    ),
    "voice.perm.name": "(Yetishmayotgan ruxsat: {perm}.)",
    "voice.group.main": "Ovoz",
    "voice.enabled": "Ovozni yoqish",
    "voice.volume": "Balandlik",
    "voice.key": "ElevenLabs kaliti",
    "voice.link": "Kalitni olish (ElevenLabs)",
    "voice.voice_id": "Ovoz ID (voice_id)",
    "voice.voice_id.placeholder": "Bo'sh qolsa — «Tekshirish»da «Yue» ovozi topiladi",
    "voice.model": "Model",
    "voice.model.standard": "Standart — Eleven v4 (eng sifatli)",
    "voice.model.fast": "Tez — Eleven v4 Turbo (jonli o'qish uchun)",
    "voice.read_ai": "AI javoblarini ham ovozda o'qish",
    "voice.daily": "Kunlik chegara",
    "voice.daily.suffix": " harf",
    "voice.daily.off": "Cheklovsiz",
    "voice.daily.used": "Bugun ishlatildi: {used} harf",
    "voice.daily.off_today": "Bugungi chegara tugagan — ovoz ertaga yana yoqiladi.",
    "voice.note": (
        "Ovoz uchun matn ElevenLabs'ga yuboriladi. Offline rejimda ovoz ishlamaydi (oldindan "
        "tayyorlangan iboralar keshdan o'ynaydi, yangi so'rov yuborilmaydi)."
    ),
    "voice.check.running": "Tekshirilmoqda…",
    "voice.check.ok": "Kalit ishlayapti. Qolgan kredit: {left} / {total}",
    "voice.check.found": "«{name}» ovozi topildi va tanlandi.",
    "voice.check.no_voice": "«Yue» nomli ovoz topilmadi — Ovoz ID ni qo'lda yozing.",
    "voice.check.no_key": "Avval kalitni kiriting.",
    "voice.check.auth": "Kalit noto'g'ri yoki bekor qilingan.",
    "voice.check.credits": "Kredit tugagan.",
    "voice.check.network": "Internetga ulanib bo'lmadi.",
    "voice.check.rate": "ElevenLabs hozir band — birozdan keyin qayta urinib ko'ring.",
    "voice.check.bad": "Tekshirib bo'lmadi.",
    "voice.group.stages": "Iboralarni oldindan tayyorlash",
    "voice.stages.intro": (
        "Tayyor iboralar bir marta ovozlashtirilib kompyuterda saqlanadi — keyin kredit "
        "sarflanmaydi. Avval eng ko'p ishlatiladiganlari (1-bosqich)."
    ),
    "voice.stage.btn": "{n}-bosqichni tayyorlash",
    "voice.stage.stop": "To'xtatish",
    "voice.stage.confirm.title": "Ovoz — {n}-bosqich",
    "voice.stage.confirm": (
        "{count} ta gap, {chars} harf (≈ {chars} kredit) ElevenLabs'ga yuboriladi.\n"
        "Qolgan kredit: {left}.\n\nDavom etamizmi?"
    ),
    "voice.stage.unknown": "noma'lum («Tekshirish» tugmasini bosing)",
    "voice.stage.nothing": "{n}-bosqichdagi hamma gap allaqachon tayyor.",
    "voice.stage.progress": "{n}-bosqich: {done} / {total}",
    "voice.stage.done": "{n}-bosqich tayyor.",
    "voice.stage.stopped": "To'xtatildi: {done} / {total}. Keyin shu joydan davom etadi.",
    "voice.stage.error": "To'xtadi: {reason}",
    "voice.prep.offline": "Offline rejimda ovoz tayyorlanmaydi — AI manbasini Online qiling.",
    "voice.prep.no_key": "ElevenLabs kaliti kiritilmagan.",
    "voice.prep.no_voice": "Ovoz ID kiritilmagan.",
    "voice.notify.title": "Yue — ovoz",
    "voice.notify.auth": "ElevenLabs kaliti noto'g'ri. Yue hozircha faqat yozib gapiradi.",
    "voice.notify.credits": "ElevenLabs krediti tugadi. Yue hozircha faqat yozib gapiradi.",
    "voice.notify.perm": (
        "Kalitda ruxsat yetishmayapti. ElevenLabs → Developers → API Keys → ⋯ → Edit: "
        "Text to Speech → Access, Voices → Read, User → Access."
    ),
}


def t(key: str, **kwargs: object) -> str:
    text = STRINGS.get(key, key)
    return text.format(**kwargs) if kwargs else text
