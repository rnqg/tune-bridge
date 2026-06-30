from __future__ import annotations

import getpass
import os
import sys
from dataclasses import dataclass
from pathlib import Path


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class AppConfig:
    yandex_music_token: str | None
    apple_team_id: str | None
    apple_key_id: str | None
    apple_private_key_path: Path | None
    apple_storefront: str
    apple_music_user_token: str | None
    apple_music_user_token_path: Path
    spotify_client_id: str | None
    spotify_client_secret: str | None
    spotify_redirect_uri: str
    spotify_token_path: Path
    spotify_market: str | None
    youtube_music_oauth_path: Path
    youtube_music_client_id: str | None
    youtube_music_client_secret: str | None
    youtube_music_user: str | None
    youtube_music_language: str
    youtube_music_location: str
    interactive: bool
    env_path: Path

    @classmethod
    def load(cls, env_path: str | Path = ".env", interactive: bool = True) -> "AppConfig":
        path = Path(env_path)
        values = _read_env_file(path)

        def value(name: str, default: str | None = None) -> str | None:
            raw = os.environ.get(name)
            if raw is not None and raw != "":
                return raw
            file_value = values.get(name)
            if file_value is not None and file_value != "":
                return file_value
            return default

        private_key = value("APPLE_PRIVATE_KEY_PATH")
        user_token_path = value("APPLE_MUSIC_USER_TOKEN_PATH", ".apple_music_user_token")
        spotify_token_path = value("SPOTIFY_TOKEN_PATH", ".spotify_token.json")
        youtube_music_oauth_path = value("YOUTUBE_MUSIC_OAUTH_PATH", "oauth.json")

        return cls(
            yandex_music_token=value("YANDEX_MUSIC_TOKEN"),
            apple_team_id=value("APPLE_TEAM_ID"),
            apple_key_id=value("APPLE_KEY_ID"),
            apple_private_key_path=Path(private_key).expanduser() if private_key else None,
            apple_storefront=value("APPLE_STOREFRONT", "ru") or "ru",
            apple_music_user_token=value("APPLE_MUSIC_USER_TOKEN"),
            apple_music_user_token_path=Path(user_token_path or ".apple_music_user_token").expanduser(),
            spotify_client_id=value("SPOTIFY_CLIENT_ID"),
            spotify_client_secret=value("SPOTIFY_CLIENT_SECRET"),
            spotify_redirect_uri=value("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8766/callback")
            or "http://127.0.0.1:8766/callback",
            spotify_token_path=Path(spotify_token_path or ".spotify_token.json").expanduser(),
            spotify_market=value("SPOTIFY_MARKET", "US"),
            youtube_music_oauth_path=Path(youtube_music_oauth_path or "oauth.json").expanduser(),
            youtube_music_client_id=value("YOUTUBE_MUSIC_CLIENT_ID"),
            youtube_music_client_secret=value("YOUTUBE_MUSIC_CLIENT_SECRET"),
            youtube_music_user=value("YOUTUBE_MUSIC_USER"),
            youtube_music_language=value("YOUTUBE_MUSIC_LANGUAGE", "en") or "en",
            youtube_music_location=value("YOUTUBE_MUSIC_LOCATION", "US") or "US",
            interactive=interactive,
            env_path=path,
        )

    def require_yandex(self) -> str:
        return self.yandex_music_token or _prompt_required("Токен Яндекс Музыки", secret=True, env_name="YANDEX_MUSIC_TOKEN", interactive=self.interactive)

    def require_apple_signing(self) -> tuple[str, str, Path]:
        team_id = self.apple_team_id or _prompt_required("Apple Team ID", env_name="APPLE_TEAM_ID", interactive=self.interactive)
        key_id = self.apple_key_id or _prompt_required("Apple Key ID", env_name="APPLE_KEY_ID", interactive=self.interactive)
        private_key_path = self.apple_private_key_path or _prompt_path(
            "Путь к приватному ключу Apple .p8",
            env_name="APPLE_PRIVATE_KEY_PATH",
            interactive=self.interactive,
        )
        if not private_key_path.exists():
            raise ConfigError(f"Приватный ключ Apple не найден: {private_key_path}")
        return team_id, key_id, private_key_path

    def read_music_user_token(self) -> str:
        if self.apple_music_user_token:
            return self.apple_music_user_token
        if not self.apple_music_user_token_path.exists():
            return _prompt_required(
                "Пользовательский токен Apple Music",
                secret=True,
                env_name="APPLE_MUSIC_USER_TOKEN",
                interactive=self.interactive,
            )
        token = self.apple_music_user_token_path.read_text(encoding="utf-8").strip()
        if not token:
            raise ConfigError(f"Файл с токеном Apple Music пустой: {self.apple_music_user_token_path}")
        return token

    def require_spotify_app(self) -> tuple[str, str]:
        client_id = self.spotify_client_id or _prompt_required("Client ID Spotify", env_name="SPOTIFY_CLIENT_ID", interactive=self.interactive)
        client_secret = self.spotify_client_secret or _prompt_required(
            "Client Secret Spotify",
            secret=True,
            env_name="SPOTIFY_CLIENT_SECRET",
            interactive=self.interactive,
        )
        return client_id, client_secret

    def require_spotify_user_token_path(self) -> Path:
        path = self.spotify_token_path
        if not path.exists() and self.interactive and sys.stdin.isatty():
            path = _prompt_path("Путь к файлу токена Spotify", default=str(path), env_name="SPOTIFY_TOKEN_PATH", interactive=True)
        if not path.exists():
            raise ConfigError(f"Файл токена Spotify не найден: {path}. Сначала запусти auth-spotify.")
        return path

    def require_youtube_music_oauth_path(self) -> Path:
        path = self.youtube_music_oauth_path
        if not path.exists() and self.interactive and sys.stdin.isatty():
            path = _prompt_path("Путь к OAuth-файлу YouTube Music", default=str(path), env_name="YOUTUBE_MUSIC_OAUTH_PATH", interactive=True)
        if not path.exists():
            raise ConfigError(f"OAuth-файл YouTube Music не найден: {path}. Сначала запусти auth-youtube-music.")
        return path

    def require_youtube_music_oauth_credentials(self) -> tuple[str, str]:
        client_id = self.youtube_music_client_id or _prompt_required(
            "OAuth Client ID YouTube Music",
            env_name="YOUTUBE_MUSIC_CLIENT_ID",
            interactive=self.interactive,
        )
        client_secret = self.youtube_music_client_secret or _prompt_required(
            "OAuth Client Secret YouTube Music",
            secret=True,
            env_name="YOUTUBE_MUSIC_CLIENT_SECRET",
            interactive=self.interactive,
        )
        return client_id, client_secret


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        key = key.strip()
        value = raw_value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def _prompt_required(label: str, env_name: str, interactive: bool, secret: bool = False) -> str:
    value = _prompt_value(label, default=None, secret=secret, interactive=interactive)
    if not value:
        raise ConfigError(f"Нужно указать {env_name}")
    return value


def _prompt_path(label: str, env_name: str, interactive: bool, default: str | None = None) -> Path:
    value = _prompt_required(label, env_name=env_name, interactive=interactive) if default is None else _prompt_value(
        label,
        default=default,
        secret=False,
        interactive=interactive,
    )
    if not value:
        raise ConfigError(f"Нужно указать {env_name}")
    return Path(value).expanduser()


def _prompt_value(label: str, default: str | None, secret: bool, interactive: bool) -> str:
    if not interactive or not sys.stdin.isatty():
        raise ConfigError(f"Нужно указать: {label}. Запусти команду в интерактивном терминале или задай значение через .env/переменную окружения.")
    suffix = f" [{default}]" if default else ""
    prompt = f"{label}{suffix}: "
    try:
        if secret:
            value = getpass.getpass(prompt)
        else:
            value = input(prompt)
    except EOFError as exc:
        raise ConfigError(f"Нужно указать: {label}. Запусти команду в интерактивном терминале или задай значение через .env/переменную окружения.") from exc
    value = value.strip()
    return value or (default or "")
