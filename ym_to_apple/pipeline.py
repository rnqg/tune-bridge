from __future__ import annotations

from pathlib import Path
from typing import Any

from .apple import AppleMusicClient, generate_developer_token
from .config import AppConfig
from .destinations import Destination, DestinationError
from .matcher import TrackMatcher
from .models import MatchDecision, SourceTrack
from .reporting import build_report, write_reports
from .spotify import SpotifyClient, load_spotify_access_token
from .youtube_music import YouTubeMusicClient
from .yandex import YandexMusicClient


def run_migration(
    config: AppConfig,
    dry_run: bool,
    limit: int | None,
    report_dir: str | Path,
    destination: str = "apple",
) -> dict[str, Any]:
    source_tracks = YandexMusicClient(config.require_yandex()).liked_tracks(limit=limit)
    target = _build_destination(config, destination, dry_run)
    matcher = TrackMatcher()

    items: list[dict[str, Any]] = []
    matched_ids: list[str] = []
    matched_indexes: dict[str, list[int]] = {}

    for source in source_tracks:
        candidates = target.client.search_songs(source.search_query)
        decision = matcher.choose(source, candidates)
        item = _decision_to_item(source, decision, target.result_key)
        if decision.status == "matched" and decision.song:
            destination_id = decision.song.id
            if destination_id in matched_indexes:
                item["status"] = "duplicate_match"
                item["reason"] = target.duplicate_reason
            elif dry_run:
                matched_ids.append(destination_id)
                matched_indexes[destination_id] = [len(items)]
            else:
                matched_ids.append(destination_id)
                matched_indexes[destination_id] = [len(items)]
        items.append(item)

    if not dry_run:
        _apply_library_adds(target, matched_ids, items, matched_indexes)

    report = build_report(items, dry_run=dry_run, destination=target.name)
    paths = write_reports(report, report_dir)
    report["paths"] = {key: str(value) for key, value in paths.items()}
    return report


def _decision_to_item(source: SourceTrack, decision: MatchDecision, result_key: str) -> dict[str, Any]:
    destination_report = decision.song.to_report() if decision.song else None
    item: dict[str, Any] = {
        "source": source.to_report(),
        "status": decision.status,
        "reason": decision.reason,
        "score": round(decision.score, 4),
        result_key: destination_report,
        "destination": destination_report,
        "candidates": [candidate.to_report() for candidate in decision.candidates],
    }
    return item


def _apply_library_adds(
    destination: Destination,
    matched_ids: list[str],
    items: list[dict[str, Any]],
    matched_indexes: dict[str, list[int]],
) -> None:
    try:
        destination.client.add_songs_to_library(matched_ids)
        for destination_id in matched_ids:
            for index in matched_indexes.get(destination_id, []):
                items[index]["status"] = "added"
                items[index]["reason"] = destination.add_reason
        return
    except DestinationError:
        pass

    for destination_id in matched_ids:
        indexes = matched_indexes.get(destination_id, [])
        try:
            destination.client.add_songs_to_library([destination_id])
            for index in indexes:
                items[index]["status"] = "added"
                items[index]["reason"] = destination.add_reason
        except DestinationError as exc:
            for index in indexes:
                items[index]["status"] = "failed"
                items[index]["reason"] = str(exc)


def _build_destination(config: AppConfig, destination: str, dry_run: bool) -> Destination:
    normalized = destination.strip().lower()
    if normalized == "apple":
        team_id, key_id, private_key_path = config.require_apple_signing()
        developer_token = generate_developer_token(team_id, key_id, private_key_path)
        user_token = None if dry_run else config.read_music_user_token()
        return Destination(
            name="apple",
            result_key="apple",
            duplicate_reason="same_apple_track_already_matched",
            add_reason="apple_library_add_requested",
            client=AppleMusicClient(developer_token, user_token, storefront=config.apple_storefront),
        )
    if normalized == "spotify":
        access_token = load_spotify_access_token(config, require_user=not dry_run)
        return Destination(
            name="spotify",
            result_key="spotify",
            duplicate_reason="same_spotify_track_already_matched",
            add_reason="spotify_library_add_requested",
            client=SpotifyClient(access_token, market=config.spotify_market),
        )
    if normalized in {"youtube-music", "ytmusic", "youtube"}:
        auth_path = None if dry_run else config.require_youtube_music_oauth_path()
        client_id = None
        client_secret = None
        if not dry_run:
            client_id, client_secret = config.require_youtube_music_oauth_credentials()
        return Destination(
            name="youtube-music",
            result_key="youtube_music",
            duplicate_reason="same_youtube_music_track_already_matched",
            add_reason="youtube_music_like_requested",
            client=YouTubeMusicClient(
                auth_path=auth_path,
                client_id=client_id,
                client_secret=client_secret,
                user=config.youtube_music_user,
                language=config.youtube_music_language,
                location=config.youtube_music_location,
            ),
        )
    raise ValueError(f"Unsupported destination: {destination}")
