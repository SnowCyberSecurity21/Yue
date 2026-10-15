"""Nora'ning tayyor rasm to'plamini Yue'ga ko'chiradi.

Rasmlar manbasi Nora'da qoladi. Nora'da yangi rasm qo'shilgach, shu skriptni qayta ishga tushiring:

    .venv\\Scripts\\python tools\\sync_pack.py [manba_papka]

Standart manba: C:\\nora\\assets\\packs\\nora_ai. Natija: assets\\packs\\yue (har safar to'liq
yangilanadi). Manbaga hech narsa yozilmaydi.

Nima o'zgaradi:
- nora.ico → yue.ico (icon.png nomi o'zgarmaydi);
- pack.json: Yue'da ishlatilmaydigan ifodalar (UNUSED_EXPRESSIONS) chaqiriladigan
  ro'yxatlardan (expression_map) chiqariladi. Kadrlar varaqda qoladi, faqat nomi "_" bilan
  boshlanadi — kadr tartibi buzilmaydi va hech qaysi teg ularga tushmaydi.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = Path(r"C:\nora\assets\packs\nora_ai")
TARGET = ROOT / "assets" / "packs" / "yue"

# Yue'da yo'q ifodalar (romantika)
UNUSED_EXPRESSIONS = frozenset({"love"})
ICON_RENAME = {"nora.ico": "yue.ico"}


def transform_pack(data: dict) -> dict:
    """pack.json'ni Yue uchun moslaydi (asl lug'at o'zgarmaydi)."""
    data = json.loads(json.dumps(data))
    emap = data.get("expression_map", {})
    for tag in list(emap):
        if tag in UNUSED_EXPRESSIONS:
            del emap[tag]
            continue
        emap[tag] = [n for n in emap[tag] if n not in UNUSED_EXPRESSIONS]

    for info in data.get("slots", {}).values():
        for variant in info.get("variants", {}).values():
            sheets = variant.get("sheets", [variant])
            for sheet in sheets:
                if "names" in sheet:
                    sheet["names"] = [
                        f"_{n}" if n in UNUSED_EXPRESSIONS else n for n in sheet["names"]
                    ]
        fb = info.get("fallback")
        if isinstance(fb, str) and fb.split(":", 1)[-1] in UNUSED_EXPRESSIONS:
            info["fallback"] = "expressions:happy"
    return data


def sync(source: Path, target: Path = TARGET) -> list[str]:
    source = source.resolve()
    if not (source / "pack.json").is_file():
        raise SystemExit(f"pack.json topilmadi: {source}")
    if target.resolve() == source or source in target.resolve().parents:
        raise SystemExit("Manba va natija bir xil bo'lishi mumkin emas")

    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)

    copied: list[str] = []
    for path in sorted(source.rglob("*")):
        if path.is_dir() or path.name == "pack.json":
            continue
        rel = path.relative_to(source)
        rel = rel.with_name(ICON_RENAME.get(rel.name, rel.name))
        dst = target / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dst)
        copied.append(rel.as_posix())

    data = json.loads((source / "pack.json").read_text(encoding="utf-8"))
    (target / "pack.json").write_text(
        json.dumps(transform_pack(data), ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    copied.append("pack.json")
    return copied


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Nora rasm to'plamini Yue'ga ko'chirish")
    parser.add_argument("source", nargs="?", type=Path, default=DEFAULT_SOURCE)
    args = parser.parse_args(argv)
    files = sync(args.source)
    print(f"{len(files)} ta fayl -> {TARGET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
