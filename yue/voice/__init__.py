"""Yue ovozi (ElevenLabs): matnni ovozga tayyorlash, provayder, kesh, bosqichlar, o'ynatish.

- `text` — ovoz matni: *harakatlar* olib tashlanadi, talaffuz lug'ati, raqamlar so'z bilan;
- `eleven` — ElevenLabs REST (httpx), kalit faqat `xi-api-key` sarlavhasida;
- `cache` — tayyor iboralar keshi (`%APPDATA%\\Yue\\voice\\<voice_id>\\`);
- `stages` — iboralarni bosqichma-bosqich oldindan ovozlashtirish;
- `player` — QtMultimedia (QMediaPlayer + QAudioOutput);
- `service` — qachon, nimani va qanday o'ynatish (UI oqimi bloklanmaydi).
"""
