import subprocess
import sys

import pytest

import yue
from yue import paths
from yue.__main__ import main


def test_version_flag(capsys):
    assert main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == f"Yue {yue.__version__}"


def test_module_runs_as_subprocess():
    out = subprocess.run(
        [sys.executable, "-m", "yue", "--version"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert out.stdout.strip() == f"Yue {yue.__version__}"


def test_help_and_errors_are_uzbek(capsys):
    with pytest.raises(SystemExit):
        main(["--help"])
    out = capsys.readouterr().out
    assert "Foydalanish:" in out and "Parametrlar:" in out
    assert "usage" not in out and "options" not in out

    with pytest.raises(SystemExit) as exc:
        main(["--nimadir"])
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "noto'g'ri parametr" in err and "error" not in err


def test_resources_exist():
    assert (paths.PERSONA_DIR / "persona_uz.txt").is_file()
    assert (paths.DEFAULT_PACK / "pack.json").is_file()
    # Ikonka — yangi to'plamdan (ilova, tray, yorliq, exe va o'rnatuvchi)
    assert paths.DEFAULT_PACK.name == "yue"
    assert paths.ICON == paths.DEFAULT_PACK / "yue.ico" and paths.ICON.is_file()
    assert paths.ICON_PNG.is_file()
    build = paths.RES / "build"
    spec = (build / "yue.spec").read_text(encoding="utf-8")
    assert '"yue" / "yue.ico"' in spec
    datas = [ln for ln in spec.splitlines() if ln.strip().startswith("(str(ROOT")]
    assert any('"assets/packs/yue"' in ln for ln in datas)
    for ln in datas:  # vositalar dist ga kirmaydi
        assert "art_src" not in ln and "tools" not in ln
    assert r"packs\yue\yue.ico" in (build / "yue.iss").read_text(encoding="utf-8")


def test_data_dir_override(monkeypatch, tmp_path):
    monkeypatch.setenv("YUE_DATA", str(tmp_path))
    assert paths.db_path() == tmp_path / "yue.db"
    assert paths.config_path() == tmp_path / "config.json"


def test_config_starts_at_version_1():
    """Yue sozlamalari o'z sxemasidan boshlanadi: Nora migratsiyalari va munosabat yo'q."""
    from yue.config import DEFAULTS, Config

    cfg = Config()
    assert cfg.get("version") == 1 and cfg.get("pet.walk_speed") == 50.0
    assert "munosabat" not in DEFAULTS
    assert cfg.get("pet.hotkey") == "Ctrl+Alt+Y" and cfg.get("voice.hotkey") == "Ctrl+Alt+Shift+U"
    old = Config({"version": 4, "pet": {"walk_speed": 30.0}})  # migratsiya qilinmaydi
    assert old.get("pet.walk_speed") == 30.0
