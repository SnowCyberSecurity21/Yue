"""O'rnatuvchi uchun hujjatlar: README.html (+ docs/yue.png), LICENSE.txt, THIRD_PARTY_LICENSES.txt.

    .venv\\Scripts\\python tools\\make_docs.py      → build\\docs_out\\

.md va kengaytmasiz fayllar ba'zi kompyuterlarda hech qaysi dasturga bog'lanmagan bo'ladi —
shuning uchun foydalanuvchiga .html va .txt beriladi. Konvertor: `yue.docs` (Qt, yangi paket yo'q).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from yue import docs  # noqa: E402

OUT = ROOT / "build" / "docs_out"


def main() -> int:
    made = docs.build(OUT, ROOT)
    for p in made:
        print(p.relative_to(ROOT))
    return 0 if len(made) == 4 else 1


if __name__ == "__main__":
    sys.exit(main())
