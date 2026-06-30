from __future__ import annotations

import inspect
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

from .config import AppConfig
from .destinations import DestinationError
from .models import DestinationSong


class YouTubeMusicError(DestinationError):
    pass


class YouTubeMusicClient:
    def __init__(
        self,
        auth_path: Path | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        user: str | None = None,
        language: str = "en",
        location: str = "US",
    ) -> None:
        self.auth_path = auth_path
        self.client = _build_ytmusic(auth_path, client_id, client_secret, user, language, location)

    def search_songs(self, term: str, limit: int = 10) -> list[DestinationSong]:
        try:
            results = self.client.search(term, filter="songs", limit=limit)
        except Exception as exc:
            raise YouTubeMusicError(f"Поиск в YouTube Music не удался: {exc}") from exc
        songs: list[DestinationSong] = []
        for item in results:
            song = _map_youtube_music_song(item)
            if song:
                songs.append(song)
        return songs

    def add_songs_to_library(self, song_ids: Iterable[str]) -> None:
        if not self.auth_path:
            raise YouTubeMusicError("Для изменения лайкнутых треков нужен OAuth-файл YouTube Music")
        for song_id in dict.fromkeys(str(song_id) for song_id in song_ids if song_id):
            try:
                self.client.rate_song(song_id, "LIKE")
            except Exception as exc:
                raise YouTubeMusicError(f"Не удалось добавить трек YouTube Music {song_id}: {exc}") from exc


def run_youtube_music_auth(config: AppConfig, open_browser: bool = True) -> str:
    client_id, client_secret = config.require_youtube_music_oauth_credentials()
    path = config.youtube_music_oauth_path
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        setup_oauth, credentials = _load_oauth_setup(client_id, client_secret)
        result = _call_setup_oauth(setup_oauth, path, credentials, open_browser)
        if isinstance(result, dict) and not path.exists():
            path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except ImportError as exc:
        raise YouTubeMusicError("Сначала установи ytmusicapi") from exc
    except TypeError:
        _run_ytmusicapi_cli(path)

    if path.exists():
        return str(path)
    raise YouTubeMusicError(f"OAuth-файл YouTube Music не был создан: {path}")


def _build_ytmusic(
    auth_path: Path | None,
    client_id: str | None,
    client_secret: str | None,
    user: str | None,
    language: str,
    location: str,
) -> Any:
    try:
        from ytmusicapi import OAuthCredentials, YTMusic
    except ImportError as exc:
        raise YouTubeMusicError("Сначала установи ytmusicapi") from exc

    kwargs: dict[str, Any] = {"language": language, "location": location}
    if auth_path:
        kwargs["auth"] = str(auth_path)
    if user:
        kwargs["user"] = user
    if client_id and client_secret:
        kwargs["oauth_credentials"] = OAuthCredentials(client_id=client_id, client_secret=client_secret)
    return YTMusic(**kwargs)


def _load_oauth_setup(client_id: str, client_secret: str) -> tuple[Any, Any]:
    try:
        from ytmusicapi import OAuthCredentials, setup_oauth
    except ImportError:
        from ytmusicapi import OAuthCredentials
        from ytmusicapi.setup import setup_oauth
    return setup_oauth, OAuthCredentials(client_id=client_id, client_secret=client_secret)


def _call_setup_oauth(setup_oauth: Any, path: Path, credentials: Any, open_browser: bool) -> Any:
    parameters = inspect.signature(setup_oauth).parameters
    kwargs: dict[str, Any] = {}
    if "filepath" in parameters:
        kwargs["filepath"] = str(path)
    elif "path" in parameters:
        kwargs["path"] = str(path)
    elif "filename" in parameters:
        kwargs["filename"] = str(path)
    if "oauth_credentials" in parameters:
        kwargs["oauth_credentials"] = credentials
    if "open_browser" in parameters:
        kwargs["open_browser"] = open_browser
    if kwargs:
        return setup_oauth(**kwargs)
    return setup_oauth(str(path), credentials)


def _run_ytmusicapi_cli(path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "ytmusicapi", "oauth"],
        cwd=str(path.parent),
        check=False,
    )
    if result.returncode != 0:
        raise YouTubeMusicError(f"ytmusicapi oauth завершился с кодом {result.returncode}")
    generated = path.parent / "oauth.json"
    if generated.exists() and generated != path and not path.exists():
        generated.rename(path)


def _map_youtube_music_song(item: dict[str, Any]) -> DestinationSong | None:
    song_id = item.get("videoId")
    title = item.get("title")
    if not song_id or not title:
        return None
    artists = item.get("artists") or []
    artist_names = [str(artist.get("name")) for artist in artists if isinstance(artist, dict) and artist.get("name")]
    album_value = item.get("album")
    if isinstance(album_value, dict):
        album = str(album_value.get("name")) if album_value.get("name") else None
    elif album_value:
        album = str(album_value)
    else:
        album = None
    return DestinationSong(
        id=str(song_id),
        title=str(title),
        artist_name=", ".join(artist_names),
        album=album,
        duration_ms=_duration_ms(item),
        url=f"https://music.youtube.com/watch?v={song_id}",
        raw=item,
    )


def _duration_ms(item: dict[str, Any]) -> int | None:
    seconds = item.get("duration_seconds")
    if seconds is not None:
        try:
            return int(seconds) * 1000
        except (TypeError, ValueError):
            return None
    duration = item.get("duration")
    if not duration:
        return None
    parts = str(duration).split(":")
    try:
        total = 0
        for part in parts:
            total = total * 60 + int(part)
        return total * 1000
    except ValueError:
        return None
