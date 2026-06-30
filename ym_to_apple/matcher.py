from __future__ import annotations

from dataclasses import dataclass

from .models import AppleSong, MatchDecision, SourceTrack
from .normalization import artist_similarity, duration_similarity, extract_variant_flags, similarity


@dataclass(frozen=True)
class CandidateScore:
    song: AppleSong
    score: float
    title_score: float
    artist_score: float
    duration_score: float
    rejected: bool
    reason: str


class TrackMatcher:
    def __init__(
        self,
        score_threshold: float = 0.91,
        title_threshold: float = 0.9,
        artist_threshold: float = 0.82,
        ambiguity_gap: float = 0.04,
    ) -> None:
        self.score_threshold = score_threshold
        self.title_threshold = title_threshold
        self.artist_threshold = artist_threshold
        self.ambiguity_gap = ambiguity_gap

    def choose(self, source: SourceTrack, candidates: list[AppleSong]) -> MatchDecision:
        if not candidates:
            return MatchDecision("not_found", None, 0.0, "apple_search_empty")

        scored = [self.score(source, candidate) for candidate in candidates]
        acceptable = [item for item in scored if not item.rejected and item.score >= self.score_threshold]
        acceptable.sort(key=lambda item: item.score, reverse=True)

        if not acceptable:
            best = max(scored, key=lambda item: item.score)
            return MatchDecision("rejected", None, best.score, best.reason, tuple(item.song for item in scored[:5]))

        best = acceptable[0]
        if len(acceptable) > 1 and best.score - acceptable[1].score < self.ambiguity_gap:
            return MatchDecision("ambiguous", None, best.score, "multiple_close_matches", tuple(item.song for item in acceptable[:5]))

        return MatchDecision("matched", best.song, best.score, best.reason, tuple(item.song for item in acceptable[:5]))

    def score(self, source: SourceTrack, candidate: AppleSong) -> CandidateScore:
        title_score = similarity(source.title, candidate.title)
        artist_score = artist_similarity(source.artists, candidate.artist_name)
        duration_score = duration_similarity(source.duration_ms, candidate.duration_ms)
        score = title_score * 0.56 + artist_score * 0.34 + duration_score * 0.10

        source_flags = extract_variant_flags(source.title, source.album)
        candidate_flags = extract_variant_flags(candidate.title, candidate.album)
        flag_mismatch = source_flags.symmetric_difference(candidate_flags)

        if flag_mismatch:
            return CandidateScore(candidate, score, title_score, artist_score, duration_score, True, "variant_mismatch")
        if title_score < self.title_threshold:
            return CandidateScore(candidate, score, title_score, artist_score, duration_score, True, "title_too_different")
        if artist_score < self.artist_threshold:
            return CandidateScore(candidate, score, title_score, artist_score, duration_score, True, "artist_too_different")
        if source.duration_ms and candidate.duration_ms and abs(source.duration_ms - candidate.duration_ms) > 12000:
            return CandidateScore(candidate, score, title_score, artist_score, duration_score, True, "duration_too_different")

        return CandidateScore(candidate, score, title_score, artist_score, duration_score, False, "high_confidence")
