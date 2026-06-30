from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class SourceTrack:
    id: str
    title: str
    artists: tuple[str, ...]
    album: str | None = None
    duration_ms: int | None = None

    @property
    def primary_artist(self) -> str:
        return self.artists[0] if self.artists else ""

    @property
    def artists_text(self) -> str:
        return ", ".join(self.artists)

    @property
    def search_query(self) -> str:
        parts = [self.title, self.primary_artist]
        return " ".join(part for part in parts if part).strip()

    def to_report(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "artists": list(self.artists),
            "album": self.album,
            "duration_ms": self.duration_ms,
        }


@dataclass(frozen=True)
class DestinationSong:
    id: str
    title: str
    artist_name: str
    album: str | None = None
    duration_ms: int | None = None
    url: str | None = None
    raw: dict[str, Any] | None = None

    def to_report(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "artist": self.artist_name,
            "album": self.album,
            "duration_ms": self.duration_ms,
            "url": self.url,
        }


AppleSong = DestinationSong

MatchStatus = Literal["matched", "not_found", "ambiguous", "rejected"]


@dataclass(frozen=True)
class MatchDecision:
    status: MatchStatus
    song: DestinationSong | None
    score: float
    reason: str
    candidates: tuple[DestinationSong, ...] = ()
