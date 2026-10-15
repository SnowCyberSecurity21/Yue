"""Hujjatlar har qanday kompyuterda ochilsin: README.md → README.html, LICENSE → LICENSE.txt.

- O'rnatilgan dasturda fayllar exe yonida (`tools/make_docs.py` yig'ishda yasaydi, o'rnatuvchi
  ko'chiradi): README.html (+ docs/yue.png), LICENSE.txt, THIRD_PARTY_LICENSES.txt.
- Manba versiyada (yoki fayl yo'q bo'lsa) — vaqtinchalik papkada shu yerning o'zida yasaladi.

Markdown → HTML: Qt'ning `QTextDocument.setMarkdown` → `toHtml` (yangi paket kerak emas). Qt
xom HTML qatorini (README boshidagi `<img>`) to'g'ri o'qiy olmaydi — u matnni yo'qotadi, shuning
uchun xom HTML qatorlari olib tashlanadi va rasm sahifaga alohida qo'yiladi.
"""

from __future__ import annotations

import html
import re
import shutil
import tempfile
from pathlib import Path

from yue import paths

README_HTML = "README.html"
LICENSE_TXT = "LICENSE.txt"
THIRD_PARTY = "THIRD_PARTY_LICENSES.txt"
IMAGE = "docs/yue.png"

CSS = """
body { margin: 0; background: #f6f4ef; color: #22202a; }
main { max-width: 800px; margin: 0 auto; padding: 32px 28px 48px; background: #ffffff;
       font-family: 'Segoe UI', Arial, sans-serif; font-size: 16px; line-height: 1.6; }
h1 { font-size: 34px; margin: 0 0 12px; }
h2 { font-size: 24px; margin: 32px 0 8px; border-bottom: 1px solid #e6e2d8; padding-bottom: 4px; }
h3 { font-size: 19px; margin: 24px 0 6px; }
p, li { white-space: normal; }
a { color: #5b4fc4; }
img.hero { float: right; width: 180px; margin: 0 0 12px 20px; }
code, span[style*='Courier'] { font-family: Consolas, 'Courier New', monospace !important;
       background: #f1eff8; padding: 0 3px; border-radius: 3px; }
"""


def markdown_to_html(md: str, title: str = "Yue", image: str | None = IMAGE) -> str:
    """Markdown matnidan o'qishga qulay HTML sahifa (Qt kerak: QGuiApplication bo'lishi shart
    emas, QTextDocument yetadi)."""
    from PySide6.QtGui import QTextDocument

    has_image = any(line.lstrip().startswith("<img") for line in md.splitlines())
    clean = "\n".join(
        line for line in md.splitlines() if not line.lstrip().startswith(("<img", "<!--"))
    )
    doc = QTextDocument()
    doc.setMarkdown(clean, QTextDocument.MarkdownFeature.MarkdownDialectGitHub)
    raw = doc.toHtml()
    m = re.search(r"<body[^>]*>(.*)</body>", raw, re.S)
    body = m.group(1) if m else raw
    if has_image and image:
        img = f'<img class="hero" src="{html.escape(image)}" alt="{html.escape(title)}">'
        body = re.sub(r"(</h1>)", r"\1" + img, body, count=1) if "</h1>" in body else img + body
    return (
        '<!DOCTYPE html>\n<html lang="uz"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{html.escape(title)}</title><style>{CSS}</style></head>"
        f"<body><main>{body}</main></body></html>\n"
    )


def build(out: Path, root: Path | None = None) -> list[Path]:
    """README.html (+ rasm), LICENSE.txt va THIRD_PARTY_LICENSES.txt ni `out` ga yasash."""
    root = root or paths.RES
    out.mkdir(parents=True, exist_ok=True)
    made = []
    readme = root / "README.md"
    if readme.is_file():
        page = markdown_to_html(readme.read_text(encoding="utf-8"))
        (out / README_HTML).write_text(page, encoding="utf-8")
        made.append(out / README_HTML)
    if (root / IMAGE).is_file():
        (out / IMAGE).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / IMAGE, out / IMAGE)
        made.append(out / IMAGE)
    for src, name in (("LICENSE", LICENSE_TXT), (THIRD_PARTY, THIRD_PARTY)):
        if (root / src).is_file():
            shutil.copyfile(root / src, out / name)
            made.append(out / name)
    return made


def doc_file(name: str) -> Path | None:
    """Ochiladigan hujjat: o'rnatilgan bo'lsa — exe yonidagisi, aks holda vaqtinchalik papkada
    yasalgani (manba versiya)."""
    installed = paths.APP_DIR / name
    if installed.is_file():
        return installed
    temp = Path(tempfile.gettempdir()) / "yue-docs"
    try:
        build(temp)
    except OSError:
        return None
    return temp / name if (temp / name).is_file() else None
