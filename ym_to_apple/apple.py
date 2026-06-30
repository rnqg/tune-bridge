from __future__ import annotations

import time
from pathlib import Path
from typing import Iterable

import jwt
import requests

from .destinations import DestinationError
from .models import DestinationSong


class AppleMusicError(DestinationError):
    pass


def generate_developer_token(team_id: str, key_id: str, private_key_path: Path, ttl_days: int = 150) -> str:
    now = int(time.time())
    payload = {
        "iss": team_id,
        "iat": now,
        "exp": now + ttl_days * 24 * 60 * 60,
    }
    private_key = private_key_path.read_text(encoding="utf-8")
    token = jwt.encode(payload, private_key, algorithm="ES256", headers={"kid": key_id})
    return token.decode("utf-8") if isinstance(token, bytes) else token


class AppleMusicClient:
    def __init__(
        self,
        developer_token: str,
        music_user_token: str | None = None,
        storefront: str = "ru",
        base_url: str = "https://api.music.apple.com/v1",
        timeout: float = 20.0,
    ) -> None:
        self.developer_token = developer_token
        self.music_user_token = music_user_token
        self.storefront = storefront
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

    @property
    def headers(self) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self.developer_token}"}
        if self.music_user_token:
            headers["Music-User-Token"] = self.music_user_token
        return headers

    def search_songs(self, term: str, limit: int = 10) -> list[DestinationSong]:
        response = self.session.get(
            f"{self.base_url}/catalog/{self.storefront}/search",
            headers=self.headers,
            params={"term": term, "types": "songs", "limit": str(limit)},
            timeout=self.timeout,
        )
        self._raise_for_response(response)
        payload = response.json()
        data = payload.get("results", {}).get("songs", {}).get("data", [])
        songs: list[DestinationSong] = []
        for item in data:
            attributes = item.get("attributes") or {}
            song_id = item.get("id")
            if not song_id:
                continue
            songs.append(
                DestinationSong(
                    id=str(song_id),
                    title=str(attributes.get("name") or ""),
                    artist_name=str(attributes.get("artistName") or ""),
                    album=attributes.get("albumName"),
                    duration_ms=_as_int(attributes.get("durationInMillis")),
                    url=attributes.get("url"),
                    raw=item,
                )
            )
        return songs

    def add_songs_to_library(self, song_ids: Iterable[str], chunk_size: int = 100) -> None:
        if not self.music_user_token:
            raise AppleMusicError("Для изменения медиатеки нужен Apple Music User Token")
        unique_ids = list(dict.fromkeys(str(song_id) for song_id in song_ids if song_id))
        for chunk in _chunks(unique_ids, chunk_size):
            response = self.session.post(
                f"{self.base_url}/me/library",
                headers=self.headers,
                params={"ids[songs]": ",".join(chunk)},
                timeout=self.timeout,
            )
            self._raise_for_response(response)

    def _raise_for_response(self, response: requests.Response) -> None:
        if 200 <= response.status_code < 300:
            return
        body = response.text.strip()
        if len(body) > 800:
            body = body[:800]
        raise AppleMusicError(f"Ошибка Apple Music API {response.status_code}: {body}")


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
