import os
import sqlite3
import sys

import pytest

from yue.config import Config
from yue.memory.crypto import Cipher, CryptoError, SecretStore, load_or_create_data_key
from yue.memory.store import Store
from yue.platform import NullPlatform, get_platform


class FakeDpapi(NullPlatform):
    """DPAPI o'rnini bosuvchi (Windows bo'lmagan muhit va xato holatlari uchun)."""

    def __init__(self, broken=False):
        self.broken = broken

    def protect(self, data):
        return b"P" + bytes(reversed(data))

    def unprotect(self, blob):
        if self.broken or not blob.startswith(b"P"):
            raise OSError("DPAPI")
        return bytes(reversed(blob[1:]))


def test_encrypt_decrypt_roundtrip():
    c = Cipher(os.urandom(32))
    blob = c.encrypt("Penitsillinga allergiya — maxfiy", "health:text")
    assert b"allergiya" not in blob and blob[:1] == b"\x01"
    assert c.decrypt(blob, "health:text") == "Penitsillinga allergiya — maxfiy"


def test_fresh_nonce_every_time():
    c = Cipher(os.urandom(32))
    a, b = c.encrypt("bir xil", "t:text"), c.encrypt("bir xil", "t:text")
    assert a != b and a[1:13] != b[1:13]


def test_wrong_key_fails():
    blob = Cipher(os.urandom(32)).encrypt("sir", "facts:text")
    with pytest.raises(CryptoError):
        Cipher(os.urandom(32)).decrypt(blob, "facts:text")


def test_wrong_aad_fails():
    c = Cipher(os.urandom(32))
    blob = c.encrypt("sir", "facts:text")
    with pytest.raises(CryptoError):
        c.decrypt(blob, "health:text")


def test_tampered_fails():
    c = Cipher(os.urandom(32))
    blob = bytearray(c.encrypt("sir", "facts:text"))
    blob[-1] ^= 1
    with pytest.raises(CryptoError):
        c.decrypt(bytes(blob), "facts:text")
    with pytest.raises(CryptoError):
        c.decrypt(b"", "facts:text")


def test_bad_key_length():
    with pytest.raises(ValueError):
        Cipher(b"short")


@pytest.mark.skipif(sys.platform != "win32", reason="DPAPI faqat Windows'da")
def test_dpapi_roundtrip_windows():
    p = get_platform()
    blob = p.protect(b"maxfiy kalit")
    assert blob != b"maxfiy kalit" and b"maxfiy" not in blob
    assert p.unprotect(blob) == b"maxfiy kalit"
    with pytest.raises(OSError):
        p.unprotect(b"buzilgan" + blob[8:])


def test_data_key_created_once_and_stored_protected(tmp_path):
    cfg = Config(path=tmp_path / "config.json")
    secrets = SecretStore(cfg, FakeDpapi())
    key, new = load_or_create_data_key(secrets)
    assert new and len(key) == 32
    raw = (tmp_path / "config.json").read_text(encoding="utf-8")
    assert "data_key" in raw and key.hex() not in raw
    cfg2 = Config.load(tmp_path / "config.json")
    key2, new2 = load_or_create_data_key(SecretStore(cfg2, FakeDpapi()))
    assert key2 == key and not new2


def test_data_key_unreadable_raises(tmp_path):
    cfg = Config(path=tmp_path / "config.json")
    load_or_create_data_key(SecretStore(cfg, FakeDpapi()))
    with pytest.raises(CryptoError):
        load_or_create_data_key(SecretStore(cfg, FakeDpapi(broken=True)))


def test_api_keys_never_plaintext_in_config(tmp_path):
    cfg = Config(path=tmp_path / "config.json")
    s = SecretStore(cfg, FakeDpapi())
    s.set("claude_key", "sk-ant-api03-SIRLI-KALIT")
    raw = (tmp_path / "config.json").read_text(encoding="utf-8")
    assert "SIRLI" not in raw and "sk-ant" not in raw
    assert s.get("claude_key") == "sk-ant-api03-SIRLI-KALIT"
    s.set("claude_key", None)
    assert not s.has("claude_key") and s.get("claude_key") is None


def test_db_unreadable_in_plain_sqlite(tmp_path):
    """Mezon: yue.db ni oddiy SQLite ko'ruvchida ochsa, matnlar o'qib bo'lmaydi."""
    path = tmp_path / "yue.db"
    st = Store(path, Cipher(os.urandom(32)))
    secrets = [
        "Boshim og'riyapti, kecha ham shunday edi",
        "Ismim Aziz, Toshkentda ishlayman",
        "Penitsillinga allergiyam bor",
        "Ertaga ertalab dori ichish",
        "Xulosa: foydalanuvchi stressda",
        "Navbatdagi savol",
    ]
    st.add_message("user", secrets[0])
    st.add_fact(secrets[1])
    st.add_health(secrets[2])
    st.add_task(secrets[3], "2026-10-14 09:00")
    st.set_summary(secrets[4])
    st.queue_add(secrets[5], 1.0)
    st.close()

    raw = b"".join(p.read_bytes() for p in tmp_path.iterdir())
    for s in secrets:
        for word in s.split()[:3]:
            assert word.encode() not in raw, word
    db = sqlite3.connect(path)
    for table in ("messages", "facts", "health", "tasks", "summary", "queue"):
        for (blob,) in db.execute(f"SELECT text FROM {table}"):
            assert isinstance(blob, bytes) and blob[:1] == b"\x01"
    db.close()


def test_store_with_wrong_key_detected(tmp_path):
    path = tmp_path / "yue.db"
    Store(path, Cipher(os.urandom(32))).add_fact("fakt")
    assert Store(path, Cipher(os.urandom(32))).verify_key() is False
