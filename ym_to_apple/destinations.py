from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .models import DestinationSong


class DestinationError(RuntimeError):
    pass


class DestinationClient(Protocol):
    def search_songs(self, term: str, limit: int = 10) -> list[DestinationSong]:
        ...

    def add_songs_to_library(self, song_ids: list[str]) -> None:
        ...


@dataclass(frozen=True)
class Destination:
    name: str
    result_key: str
    duplicate_reason: str
    add_reason: str
    client: DestinationClient
