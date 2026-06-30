import unittest

from ym_to_apple.matcher import TrackMatcher
from ym_to_apple.models import AppleSong, SourceTrack


class MatcherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.matcher = TrackMatcher()

    def test_exact_match(self) -> None:
        source = SourceTrack("1", "Blinding Lights", ("The Weeknd",), "After Hours", 200040)
        candidate = AppleSong("a", "Blinding Lights", "The Weeknd", "After Hours", 200000)
        decision = self.matcher.choose(source, [candidate])
        self.assertEqual(decision.status, "matched")
        self.assertEqual(decision.song, candidate)

    def test_rejects_variant_mismatch(self) -> None:
        source = SourceTrack("1", "Song", ("Artist",), None, 180000)
        candidate = AppleSong("a", "Song - Live", "Artist", None, 180000)
        decision = self.matcher.choose(source, [candidate])
        self.assertEqual(decision.status, "rejected")
        self.assertEqual(decision.reason, "variant_mismatch")

    def test_ambiguous_close_matches(self) -> None:
        source = SourceTrack("1", "Song", ("Artist",), None, 180000)
        first = AppleSong("a", "Song", "Artist", "Album A", 180000)
        second = AppleSong("b", "Song", "Artist", "Album B", 180000)
        decision = self.matcher.choose(source, [first, second])
        self.assertEqual(decision.status, "ambiguous")


if __name__ == "__main__":
    unittest.main()
