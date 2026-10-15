"""Kirish nuqtasi: `python -m yue [--version] [--toggle] [--autostart]`."""

from __future__ import annotations

import argparse
import sys

from yue import APP_NAME, __version__
from yue.i18n import t


class _Parser(argparse.ArgumentParser):
    """argparse'ning inglizcha xizmat satrlarini o'zbekchaga almashtiradi."""

    def format_usage(self) -> str:
        return super().format_usage().replace("usage:", "Foydalanish:", 1)

    def format_help(self) -> str:
        text = super().format_help().replace("usage:", "Foydalanish:", 1)
        return text.replace("options:", "Parametrlar:", 1)

    def error(self, message: str) -> None:  # type: ignore[override]
        self.exit(2, t("cli.bad_arg") + "\n")


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="yue", description=t("cli.description"), add_help=False)
    parser.add_argument("-h", "--help", action="help", help=t("cli.help"))
    parser.add_argument("-v", "--version", action="store_true", help=t("cli.version"))
    parser.add_argument("--toggle", action="store_true", help=t("cli.toggle"))
    parser.add_argument("--autostart", action="store_true", help=t("cli.autostart"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.version:
        print(f"{APP_NAME} {__version__}")
        return 0
    from yue.app import run

    return run(toggle=args.toggle, autostart=args.autostart)


if __name__ == "__main__":
    sys.exit(main())
