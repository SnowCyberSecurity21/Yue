# -*- mode: python ; coding: utf-8 -*-
# Yue — PyInstaller (onedir). Yig'ish:  .venv\Scripts\pyinstaller build\yue.spec --noconfirm
# Natija: dist\Yue\Yue.exe  (resurslar dist\Yue\_internal\ ichida)

from pathlib import Path

ROOT = Path(SPECPATH).parent  # noqa: F821 — PyInstaller beradi

datas = [
    # Faqat Yue to'plami (tools/sync_pack.py yasaydi); tools/ kirmaydi.
    (str(ROOT / "assets" / "packs" / "yue"), "assets/packs/yue"),
    (str(ROOT / "assets" / "ui"), "assets/ui"),
    (str(ROOT / "persona"), "persona"),
]

# Yue ishlatmaydigan Qt va Python modullari — hajmni kamaytirish uchun
EXCLUDES = [
    "tkinter", "unittest", "pydoc", "doctest", "lib2to3", "test",
    "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuickWidgets", "PySide6.QtQuickControls2",
    "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtMultimediaWidgets",
    "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets", "PySide6.QtSql", "PySide6.QtTest",
    "PySide6.QtXml", "PySide6.QtConcurrent", "PySide6.QtDBus", "PySide6.QtDesigner",
    "PySide6.QtHelp", "PySide6.QtPrintSupport", "PySide6.QtUiTools", "PySide6.QtSvgWidgets",
    "PySide6.QtStateMachine", "PySide6.QtSpatialAudio", "PySide6.QtTextToSpeech",
    "PySide6.QtWebSockets", "PySide6.QtWebChannel", "PySide6.QtWebEngineCore",
    "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtGraphs", "PySide6.Qt3DCore",
    "pytest", "pytestqt", "PyInstaller", "pip_audit", "ruff", "pip",
]

a = Analysis(  # noqa: F821
    [str(ROOT / "yue.pyw")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "anthropic", "httpx2", "yue.ui.settings", "yue.ui.welcome", "yue.ui.memory_view",
        # Ovoz: QtMultimedia birinchi o'ynatishda yuklanadi (ffmpeg plagini mp3 ni o'qiydi)
        "PySide6.QtMultimedia", "yue.voice.player",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
    optimize=1,
)

# Keraksiz Qt fayllari: tarjimalar (o'zbekchasi yo'q, inglizcha matn chiqmasin) va qo'shimcha plaginlar.
# Qt6Multimedia va plugins/multimedia (ffmpeg) qoladi — Yue ovozi uchun kerak.
DROP = (
    "translations",
    "qml",
    "Qt6Quick", "Qt6Qml", "Qt6Pdf", "Qt6OpenGL", "opengl32sw", "Qt6VirtualKeyboard",
    "qtvirtualkeyboard", "Qt6MultimediaQuick", "Qt6MultimediaWidgets", "Qt6ShaderTools",
)


def keep(entry):
    path = entry[0].replace("\\", "/")
    return not any(f"/{d}" in "/" + path or path.startswith(d) for d in DROP)


a.binaries = [b for b in a.binaries if keep(b)]
a.datas = [d for d in a.datas if keep(d)]

pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Yue",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=True,
    icon=str(ROOT / "assets" / "packs" / "yue" / "yue.ico"),
    version=str(ROOT / "build" / "version_info.txt"),
)

coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Yue",
)
