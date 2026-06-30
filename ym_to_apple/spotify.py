from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Iterable

import requests

from .config import AppConfig, ConfigError
from .destinations import DestinationError
from .models import DestinationSong


class SpotifyError(DestinationError):
    pass


class SpotifyClient:
    def __init__(
        self,
        access_token: str,
        market: str | None = "US",
        base_url: str = "https://api.spotify.com/v1",
        timeout: float = 20.0,
    ) -> None:
        self.access_token = access_token
        self.market = market
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.access_token}"}

    def search_songs(self, term: str, limit: int = 10) -> list[DestinationSong]:
        params = {"q": term, "type": "track", "limit": str(min(limit, 50))}
        if self.market:
            params["market"] = self.market
        response = self.session.get(
            f"{self.base_url}/search",
            headers=self.headers,
            params=params,
            timeout=self.timeout,
        )
        self._raise_for_response(response)
        payload = response.json()
        data = payload.get("tracks", {}).get("items", [])
        songs: list[DestinationSong] = []
        for item in data:
            song = _map_spotify_track(item)
            if song:
                songs.append(song)
        return songs

    def add_songs_to_library(self, song_ids: Iterable[str], chunk_size: int = 50) -> None:
        unique_ids = list(dict.fromkeys(_spotify_track_id(song_id) for song_id in song_ids if song_id))
        for chunk in _chunks(unique_ids, chunk_size):
            response = self.session.put(
                f"{self.base_url}/me/tracks",
                headers=self.headers,
                params={"ids": ",".join(chunk)},
                timeout=self.timeout,
            )
            self._raise_for_response(response)

    def _raise_for_response(self, response: requests.Response) -> None:
        if 200 <= response.status_code < 300:
            return
        body = response.text.strip()
        if len(body) > 800:
            body = body[:800]
        raise SpotifyError(f"Ошибка Spotify API {response.status_code}: {body}")


def load_spotify_access_token(config: AppConfig, require_user: bool) -> str:
    if not require_user and config.spotify_token_path.exists():
        try:
            token = _valid_saved_access_token(config.spotify_token_path)
            if token:
                return token
        except SpotifyError:
            pass

    client_id, client_secret = config.require_spotify_app()
    if not require_user:
        return request_client_credentials_token(client_id, client_secret)

    token_path = config.require_spotify_user_token_path()
    token_data = _read_token(token_path)
    if not _is_expired(token_data):
        token = token_data.get("access_token")
        if token:
            return str(token)

    refresh_token = token_data.get("refresh_token")
    if not refresh_token:
        raise ConfigError(f"В файле токена Spotify нет refresh_token: {token_path}")

    refreshed = refresh_spotify_token(client_id, client_secret, str(refresh_token))
    if "refresh_token" not in refreshed:
        refreshed["refresh_token"] = refresh_token
    _write_token(token_path, refreshed)
    token = refreshed.get("access_token")
    if not token:
        raise SpotifyError("В ответе Spotify на обновление токена нет access_token")
    return str(token)


def request_client_credentials_token(client_id: str, client_secret: str) -> str:
    response = requests.post(
        "https://accounts.spotify.com/api/token",
        auth=(client_id, client_secret),
        data={"grant_type": "client_credentials"},
        timeout=20.0,
    )
    _raise_token_response(response)
    payload = response.json()
    token = payload.get("access_token")
    if not token:
        raise SpotifyError("В ответе Spotify client credentials нет access_token")
    return str(token)


def exchange_spotify_code(client_id: str, client_secret: str, code: str, redirect_uri: str) -> dict[str, Any]:
    response = requests.post(
        "https://accounts.spotify.com/api/token",
        auth=(client_id, client_secret),
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
        },
        timeout=20.0,
    )
    _raise_token_response(response)
    payload = response.json()
    payload["expires_at"] = int(time.time()) + int(payload.get("expires_in", 3600)) - 60
    return payload


def refresh_spotify_token(client_id: str, client_secret: str, refresh_token: str) -> dict[str, Any]:
    response = requests.post(
        "https://accounts.spotify.com/api/token",
        auth=(client_id, client_secret),
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=20.0,
    )
    _raise_token_response(response)
    payload = response.json()
    payload["expires_at"] = int(time.time()) + int(payload.get("expires_in", 3600)) - 60
    return payload


def save_spotify_token(path: Path, payload: dict[str, Any]) -> None:
    _write_token(path, payload)


def _valid_saved_access_token(path: Path) -> str | None:
    payload = _read_token(path)
    if _is_expired(payload):
        return None
    token = payload.get("access_token")
    return str(token) if token else None


def _read_token(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SpotifyError(f"Не удалось прочитать файл токена Spotify {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SpotifyError(f"Файл токена Spotify должен содержать JSON-объект: {path}")
    return payload


def _write_token(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _is_expired(payload: dict[str, Any]) -> bool:
    expires_at = payload.get("expires_at")
    if expires_at is None:
        return False
    try:
        return int(expires_at) <= int(time.time())
    except (TypeError, ValueError):
        return True


def _raise_token_response(response: requests.Response) -> None:
    if 200 <= response.status_code < 300:
        return
    body = response.text.strip()
    if len(body) > 800:
        body = body[:800]
    raise SpotifyError(f"Ошибка авторизации Spotify {response.status_code}: {body}")


def _map_spotify_track(item: dict[str, Any]) -> DestinationSong | None:
    song_id = item.get("id")
    title = item.get("name")
    if not song_id or not title:
        return None
    artists = item.get("artists") or []
    artist_names = [str(artist.get("name")) for artist in artists if isinstance(artist, dict) and artist.get("name")]
    album = item.get("album") if isinstance(item.get("album"), dict) else {}
    external_urls = item.get("external_urls") if isinstance(item.get("external_urls"), dict) else {}
    return DestinationSong(
        id=str(song_id),
        title=str(title),
        artist_name=", ".join(artist_names),
        album=str(album.get("name")) if album.get("name") else None,
        duration_ms=_as_int(item.get("duration_ms")),
        url=str(external_urls.get("spotify")) if external_urls.get("spotify") else None,
        raw=item,
    )


def _spotify_track_id(value: str) -> str:
    text = str(value)
    if text.startswith("spotify:track:"):
        return text.rsplit(":", 1)[-1]
    return text


def _as_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _chunks(values: list[str], size: int) -> Iterable[list[str]]:
    for index in range(0, len(values), size):
        yield values[index : index + size]
