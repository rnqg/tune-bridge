import tempfile
import unittest
from pathlib import Path

from ym_to_apple.reporting import build_report, write_reports
from ym_to_apple.spotify import _map_spotify_track, _spotify_track_id
from ym_to_apple.youtube_music import _map_youtube_music_song


class DestinationMappingTests(unittest.TestCase):
    def test_maps_spotify_track(self) -> None:
        song = _map_spotify_track(
            {
                "id": "spotify-id",
                "name": "Blinding Lights",
                "artists": [{"name": "The Weeknd"}],
                "album": {"name": "After Hours"},
                "duration_ms": 200040,
                "external_urls": {"spotify": "https://open.spotify.com/track/spotify-id"},
            }
        )
        self.assertIsNotNone(song)
        assert song is not None
        self.assertEqual(song.id, "spotify-id")
        self.assertEqual(song.artist_name, "The Weeknd")
        self.assertEqual(song.album, "After Hours")

    def test_strips_spotify_uri(self) -> None:
        self.assertEqual(_spotify_track_id("spotify:track:abc"), "abc")
        self.assertEqual(_spotify_track_id("abc"), "abc")

    def test_maps_youtube_music_song(self) -> None:
        song = _map_youtube_music_song(
            {
                "videoId": "youtube-id",
                "title": "Blinding Lights",
                "artists": [{"name": "The Weeknd"}],
                "album": {"name": "After Hours"},
                "duration": "3:20",
            }
        )
        self.assertIsNotNone(song)
        assert song is not None
        self.assertEqual(song.id, "youtube-id")
        self.assertEqual(song.duration_ms, 200000)
        self.assertEqual(song.url, "https://music.youtube.com/watch?v=youtube-id")


class ReportingTests(unittest.TestCase):
    def test_spotify_report_names_are_prefixed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = build_report([], dry_run=True, destination="spotify")
            paths = write_reports(report, Path(directory))
            self.assertEqual(paths["main"].name, "spotify-dry-run.json")
            self.assertEqual(paths["unmatched"].name, "spotify-unmatched.csv")


if __name__ == "__main__":
    unittest.main()
