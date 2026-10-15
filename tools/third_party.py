"""THIRD_PARTY_LICENSES.txt ni yasaydi: exe ichidagi har bir paket — nomi, versiyasi, litsenziyasi
va litsenziya matni. Faqat standart kutubxona (importlib.metadata), yangi paket kerak emas.

    .venv\\Scripts\\python tools\\third_party.py [dist\\Yue]

Paketlar ro'yxati: ilovaning to'g'ridan-to'g'ri bog'liqliklari (pyproject.toml) va ularning
bog'liqliklari (extras'siz), hamda yig'ilgan papkada (`dist\\Yue\\_internal`) topilgan boshqa
paketlar. Python'ning o'z litsenziyasi ham qo'shiladi (exe ichida Python runtime bor).
"""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "THIRD_PARTY_LICENSES.txt"
DEFAULT_DIST = ROOT / "dist" / "Yue"
LICENSE_FILE = re.compile(r"(^|/)(licen[cs]e|copying|notice|authors)[^/]*$", re.I)
SEP = "=" * 78

QT_NOTE = """\
Qt (PySide6, shiboken6) — GNU LGPL v3 litsenziyasi ostida.
Qt kutubxonalari dastur ichida alohida DLL fayllar sifatida turadi (Yue o'rnatilgan papkadagi
_internal\\PySide6 va _internal\\shiboken6). LGPL v3 talabiga ko'ra foydalanuvchi ularni o'zi
yig'gan yoki boshqa mos versiyadagi Qt kutubxonalari bilan almashtirishi mumkin. Qt manba kodi:
https://download.qt.io/official_releases/qt/ , PySide6: https://code.qt.io/cgit/pyside/pyside-setup.git/

Qt Multimedia ovozni o'ynatish uchun FFmpeg kutubxonalaridan foydalanadi (avcodec, avformat,
avutil, swresample, swscale — _internal\\PySide6 ichida alohida DLL fayllar). FFmpeg — GNU LGPL
v2.1 yoki undan keyingi versiya ostida; bu DLL fayllarni ham foydalanuvchi almashtirishi mumkin.
FFmpeg manba kodi: https://ffmpeg.org/download.html
"""


def _name(req: str) -> str:
    return re.split(r"[\s;<>=!~\[(]", req.strip(), maxsplit=1)[0]


def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def app_packages() -> set[str]:
    """pyproject.toml dagi bog'liqliklar va ularning bog'liqliklari (extras'siz)."""
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    todo = [_name(r) for r in data["project"]["dependencies"]]
    todo.append("PySide6-Addons")  # QtMultimedia (ovoz) shu paketda
    seen: set[str] = set()
    while todo:
        name = _norm(todo.pop())
        if name in seen:
            continue
        try:
            dist = metadata.distribution(name)
        except metadata.PackageNotFoundError:
            continue
        seen.add(name)
        for req in dist.requires or []:
            if "extra ==" not in req:
                todo.append(_name(req))
    return seen


def bundled_packages(dist_dir: Path) -> set[str]:
    """Yig'ilgan papkadagi top-level modullar → ularni beradigan paketlar."""
    internal = dist_dir / "_internal"
    if not internal.is_dir():
        return set()
    owners = metadata.packages_distributions()
    found: set[str] = set()
    for item in internal.iterdir():
        top = item.name.split(".")[0]
        for dist in owners.get(top, []):
            found.add(_norm(dist))
    return found


def license_of(dist: metadata.Distribution) -> str:
    meta = dist.metadata
    expr = meta.get("License-Expression")
    if expr:
        return expr
    lic = (meta.get("License") or "").strip()
    if lic and len(lic) < 120 and "\n" not in lic:
        return lic
    classifiers = [
        c.split("::")[-1].strip()
        for c in meta.get_all("Classifier") or []
        if c.startswith("License")
    ]
    return ", ".join(classifiers) or (lic.splitlines()[0] if lic else "noma'lum")


def license_texts(dist: metadata.Distribution) -> list[tuple[str, str]]:
    out = []
    for f in dist.files or []:
        if LICENSE_FILE.search(str(f).replace("\\", "/")) and ".dist-info" in str(f):
            try:
                out.append((str(f), Path(dist.locate_file(f)).read_text(encoding="utf-8")))
            except (OSError, UnicodeDecodeError):
                continue
    if not out:
        lic = dist.metadata.get("License") or ""
        if len(lic) >= 120 or "\n" in lic:
            out.append(("METADATA: License", lic))
    return out


def python_license() -> str:
    path = Path(sys.base_prefix) / "LICENSE.txt"
    return path.read_text(encoding="utf-8") if path.is_file() else "PSF-2.0"


def build(dist_dir: Path = DEFAULT_DIST) -> str:
    names = sorted(app_packages() | bundled_packages(dist_dir))
    parts = [
        "Yue — uchinchi tomon kutubxonalari litsenziyalari",
        "",
        "Yue quyidagi ochiq kodli kutubxonalardan foydalanadi. Har biri o'z litsenziyasi ostida.",
        "",
        QT_NOTE,
        SEP,
        f"Python {sys.version.split()[0]} (runtime) — PSF-2.0",
        SEP,
        python_license(),
    ]
    for name in names:
        dist = metadata.distribution(name)
        parts += [
            SEP,
            f"{dist.metadata['Name']} {dist.version} — {license_of(dist)}",
            f"Sahifa: {dist.metadata.get('Home-page') or _project_url(dist)}",
            SEP,
        ]
        texts = license_texts(dist)
        if not texts:
            parts.append("(Litsenziya matni paketda yo'q — yuqoridagi litsenziya nomiga qarang.)")
        for fname, text in texts:
            parts += [f"--- {Path(fname).name} ---", text.strip(), ""]
    return "\n".join(parts).rstrip() + "\n"


def _project_url(dist: metadata.Distribution) -> str:
    for url in dist.metadata.get_all("Project-URL") or []:
        return url.split(",", 1)[-1].strip()
    return "-"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="THIRD_PARTY_LICENSES.txt yasash")
    parser.add_argument("dist", nargs="?", type=Path, default=DEFAULT_DIST)
    args = parser.parse_args(argv)
    text = build(args.dist)
    OUT.write_text(text, encoding="utf-8", newline="\n")
    count = text.count(SEP) // 2
    print(f"{OUT.name}: {count} ta bo'lim, {len(text)} belgi")
    return 0


if __name__ == "__main__":
    sys.exit(main())
