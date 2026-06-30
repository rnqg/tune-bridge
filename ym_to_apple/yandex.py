from __future__ import annotations

from typing import Any

from .models import SourceTrack


class YandexMusicError(RuntimeError):
    pass


class YandexMusicClient:
    def __init__(self, token: str) -> None:
        self.token = token

    def liked_tracks(self, limit: int | None = None) -> list[SourceTrack]:
        try:
            from yandex_music import Client
        except ImportError as exc:
            raise YandexMusicError("Сначала установи пакет yandex-music") from exc

        try:
            client = Client(self.token).init()
            liked = client.users_likes_tracks()
            tracks = liked.fetch_tracks()
        except Exception as exc:
            raise YandexMusicError(f"Не удалось получить лайкнутые треки из Яндекс Музыки: {exc}") from exc

        result: list[SourceTrack] = []
        for track in tracks:
            mapped = _map_track(track)
            if mapped:
                result.append(mapped)
                if limit is not None and len(result) >= limit:
                    break
        return result


def _map_track(track: Any) -> SourceTrack | None:
    title = _string_attr(track, "title")
    if not title:
        return None

    artists = tuple(name for name in (_string_attr(artist, "name") for artist in _list_attr(track, "artists")) if name)
    album = None
    albums = _list_attr(track, "albums")
    if albums:
        album = _string_attr(albums[0], "title")

    track_id = _string_attr(track, "id") or _string_attr(track, "real_id") or f"{title}:{','.join(artists)}"
    duration = _int_attr(track, "duration_ms")
    if duration is None:
        duration = _int_attr(track, "durationMs")

    return SourceTrack(
        id=track_id,
        title=title,
        artists=artists,
        album=album,
        duration_ms=duration,
    )


def _attr(value: Any, name: str) -> Any:
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _string_attr(value: Any, name: str) -> str:
    raw = _attr(value, name)
    if raw is None:
        return ""
    return str(raw)


def _int_attr(value: Any, name: str) -> int | None:
    raw = _attr(value, name)
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _list_attr(value: Any, name: str) -> list[Any]:
    raw = _attr(value, name)
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    return list(raw)
