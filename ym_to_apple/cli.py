from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .auth_server import AuthServerError, run_apple_auth
from .config import AppConfig, ConfigError
from .destinations import DestinationError
from .pipeline import run_migration
from .reporting import load_latest_report
from .spotify_auth import SpotifyAuthError, run_spotify_auth
from .yandex import YandexMusicError
from .youtube_music import YouTubeMusicError, run_youtube_music_auth


DESTINATIONS = ("apple", "spotify", "youtube-music")
DESTINATION_NAMES = {
    "apple": "Apple Music",
    "spotify": "Spotify",
    "youtube-music": "YouTube Music",
}
STATUS_NAMES = {
    "added": "добавлено",
    "ambiguous": "неоднозначно",
    "duplicate_match": "дубликаты",
    "failed": "ошибки",
    "matched": "найдено",
    "not_found": "не найдено",
    "rejected": "отклонено",
}


class RussianArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args: object, **kwargs: object) -> None:
        add_help = bool(kwargs.pop("add_help", True))
        super().__init__(*args, add_help=False, **kwargs)
        self._positionals.title = "аргументы"
        self._optionals.title = "параметры"
        if add_help:
            self.add_argument("-h", "--help", action="help", default=argparse.SUPPRESS, help="Показать справку и выйти")

    def format_usage(self) -> str:
        return super().format_usage().replace("usage:", "использование:", 1)

    def format_help(self) -> str:
        return super().format_help().replace("usage:", "использование:", 1)

    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: ошибка: {message}\n")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "auth-apple":
            return _cmd_auth_apple(args)
        if args.command == "auth-spotify":
            return _cmd_auth_spotify(args)
        if args.command == "auth-youtube-music":
            return _cmd_auth_youtube_music(args)
        if args.command == "dry-run":
            return _cmd_dry_run(args)
        if args.command == "transfer":
            return _cmd_transfer(args)
        if args.command == "report":
            return _cmd_report(args)
        parser.print_help()
        return 1
    except (AuthServerError, ConfigError, DestinationError, FileNotFoundError, SpotifyAuthError, YandexMusicError, YouTubeMusicError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Прервано", file=sys.stderr)
        return 130


def _build_parser() -> argparse.ArgumentParser:
    parser = RussianArgumentParser(prog="tune-bridge", description="Перенос лайкнутых треков из Яндекс Музыки.")
    parser.add_argument("--env", default=".env", metavar="ПУТЬ", help="Необязательный путь к .env файлу")
    subparsers = parser.add_subparsers(dest="command", title="команды", metavar="КОМАНДА", parser_class=RussianArgumentParser)

    auth_apple = subparsers.add_parser("auth-apple", help="Авторизоваться в Apple Music и сохранить пользовательский токен")
    auth_apple.add_argument("--port", type=int, default=8765, metavar="ПОРТ", help="Порт локальной страницы авторизации")
    auth_apple.add_argument("--no-open-browser", action="store_true", help="Не открывать браузер автоматически")

    auth_spotify = subparsers.add_parser("auth-spotify", help="Авторизоваться в Spotify и сохранить OAuth-токен")
    auth_spotify.add_argument("--no-open-browser", action="store_true", help="Не открывать браузер автоматически")

    auth_youtube_music = subparsers.add_parser("auth-youtube-music", help="Авторизоваться в YouTube Music и сохранить OAuth-токен")
    auth_youtube_music.add_argument("--no-open-browser", action="store_true", help="Не открывать браузер автоматически")

    dry_run = subparsers.add_parser("dry-run", help="Найти совпадения без добавления треков")
    dry_run.add_argument("--destination", choices=DESTINATIONS, default="apple", metavar="СЕРВИС", help="Куда переносить треки")
    dry_run.add_argument("--limit", type=int, metavar="ЧИСЛО", help="Ограничить количество треков из Яндекс Музыки")
    dry_run.add_argument("--report-dir", default="reports", metavar="ПАПКА", help="Папка для отчетов")

    transfer = subparsers.add_parser("transfer", help="Добавить найденные треки в выбранный сервис")
    transfer.add_argument("--destination", choices=DESTINATIONS, default="apple", metavar="СЕРВИС", help="Куда переносить треки")
    transfer.add_argument("--limit", type=int, metavar="ЧИСЛО", help="Ограничить количество треков из Яндекс Музыки")
    transfer.add_argument("--report-dir", default="reports", metavar="ПАПКА", help="Папка для отчетов")
    transfer.add_argument("--yes", action="store_true", help="Запустить перенос без ручного подтверждения")

    report = subparsers.add_parser("report", help="Показать сводку последнего отчета")
    report.add_argument("--destination", choices=DESTINATIONS, default="apple", metavar="СЕРВИС", help="Для какого сервиса показать отчет")
    report.add_argument("--report-dir", default="reports", metavar="ПАПКА", help="Папка с отчетами")
    report.add_argument("--json", action="store_true", help="Вывести полный отчет в JSON")

    return parser


def _config(args: argparse.Namespace) -> AppConfig:
    return AppConfig.load(args.env)


def _cmd_auth_apple(args: argparse.Namespace) -> int:
    path = run_apple_auth(_config(args), port=args.port, open_browser=not args.no_open_browser)
    print(f"Токен Apple Music сохранен: {path}")
    return 0


def _cmd_auth_spotify(args: argparse.Namespace) -> int:
    path = run_spotify_auth(_config(args), open_browser=not args.no_open_browser)
    print(f"Токен Spotify сохранен: {path}")
    return 0


def _cmd_auth_youtube_music(args: argparse.Namespace) -> int:
    path = run_youtube_music_auth(_config(args), open_browser=not args.no_open_browser)
    print(f"OAuth-токен YouTube Music сохранен: {path}")
    return 0


def _cmd_dry_run(args: argparse.Namespace) -> int:
    report = run_migration(
        _config(args),
        dry_run=True,
        limit=args.limit,
        report_dir=args.report_dir,
        destination=args.destination,
    )
    _print_summary(report)
    return 0


def _cmd_transfer(args: argparse.Namespace) -> int:
    if not args.yes:
        if not sys.stdin.isatty():
            print("Для неинтерактивного запуска переноса добавь --yes", file=sys.stderr)
            return 2
        answer = input(f"Сейчас найденные треки будут добавлены в {_destination_name(args.destination)}. Введи ДА для продолжения: ")
        if answer.strip().upper() not in {"ДА", "YES"}:
            print("Перенос отменен")
            return 1
    report = run_migration(
        _config(args),
        dry_run=False,
        limit=args.limit,
        report_dir=args.report_dir,
        destination=args.destination,
    )
    _print_summary(report)
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    path, report = load_latest_report(Path(args.report_dir), destination=args.destination)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Отчет: {path}")
        _print_summary(report)
    return 0


def _print_summary(report: dict[str, object]) -> None:
    summary = report.get("summary", {})
    print("Сводка:")
    if isinstance(summary, dict):
        for key, value in sorted(summary.items()):
            label = STATUS_NAMES.get(str(key), str(key))
            print(f"  {label} ({key}): {value}")
    paths = report.get("paths")
    if isinstance(paths, dict):
        print("Файлы отчетов:")
        for key, value in sorted(paths.items()):
            print(f"  {key}: {value}")


def _destination_name(value: str) -> str:
    return DESTINATION_NAMES.get(value, value)
