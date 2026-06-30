import unittest

from ym_to_apple.normalization import (
    artist_similarity,
    duration_similarity,
    extract_variant_flags,
    normalize_text,
    split_artists,
)


class NormalizationTests(unittest.TestCase):
    def test_normalize_text(self) -> None:
        self.assertEqual(normalize_text("  Ёлка — Прованс! "), "елка прованс")

    def test_split_artists(self) -> None:
        self.assertEqual(split_artists("Artist feat. Guest & Other"), ("artist", "guest", "other"))

    def test_split_artists_keeps_slash_names(self) -> None:
        self.assertEqual(split_artists("AC/DC"), ("ac dc",))

    def test_artist_similarity(self) -> None:
        score = artist_similarity(("The Weeknd",), "The Weeknd & Ariana Grande")
        self.assertGreaterEqual(score, 0.9)

    def test_duration_similarity(self) -> None:
        self.assertEqual(duration_similarity(200000, 202000), 1.0)
        self.assertEqual(duration_similarity(200000, 230000), 0.0)

    def test_variant_flags(self) -> None:
        self.assertEqual(extract_variant_flags("Song - Live", None), frozenset({"live"}))


if __name__ == "__main__":
    unittest.main()
