from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher


_ARTIST_SPLIT_RE = re.compile(
    r"\s+(?:feat\.?|ft\.?|featuring|with|x|vs\.?)\s+|[,;&]+|\s+\+\s+",
    re.IGNORECASE,
)
_NON_WORD_RE = re.compile(r"[^0-9a-zа-яё]+", re.IGNORECASE)
_SPACE_RE = re.compile(r"\s+")

_VARIANT_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "live": (re.compile(r"\blive\b", re.IGNORECASE), re.compile(r"\bconcert\b", re.IGNORECASE)),
    "remix": (re.compile(r"\bremix(?:ed)?\b", re.IGNORECASE), re.compile(r"\bmix\b", re.IGNORECASE)),
    "acoustic": (re.compile(r"\bacoustic\b", re.IGNORECASE),),
    "instrumental": (re.compile(r"\binstrumental\b", re.IGNORECASE),),
    "karaoke": (re.compile(r"\bkaraoke\b", re.IGNORECASE),),
    "slowed": (re.compile(r"\bslowed\b", re.IGNORECASE), re.compile(r"\bslowed\s+reverb\b", re.IGNORECASE)),
    "sped": (re.compile(r"\bsped\s+up\b", re.IGNORECASE),),
    "remaster": (re.compile(r"\bremaster(?:ed)?\b", re.IGNORECASE),),
    "edit": (re.compile(r"\bradio\s+edit\b", re.IGNORECASE), re.compile(r"\bsingle\s+edit\b", re.IGNORECASE)),
}


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFKC", value).casefold()
    text = text.replace("&", " and ")
    text = text.replace("ё", "е")
    text = _NON_WORD_RE.sub(" ", text)
    return _SPACE_RE.sub(" ", text).strip()


def similarity(left: str | None, right: str | None) -> float:
    normalized_left = normalize_text(left)
    normalized_right = normalize_text(right)
    if not normalized_left or not normalized_right:
        return 0.0
    if normalized_left == normalized_right:
        return 1.0
    return SequenceMatcher(None, normalized_left, normalized_right).ratio()


def split_artists(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    parts = [normalize_text(part) for part in _ARTIST_SPLIT_RE.split(value)]
    return tuple(part for part in parts if part)


def artist_similarity(source_artists: tuple[str, ...], candidate_artist: str | None) -> float:
    source = tuple(normalize_text(artist) for artist in source_artists if normalize_text(artist))
    candidate_parts = split_artists(candidate_artist)
    if not source or not candidate_parts:
        return 0.0
    best_scores = []
    for source_artist in source:
        best_scores.append(max(similarity(source_artist, candidate_artist_part) for candidate_artist_part in candidate_parts))
    primary_score = best_scores[0] if best_scores else 0.0
    coverage = sum(1 for score in best_scores if score >= 0.86) / len(best_scores)
    return max(primary_score * 0.82 + coverage * 0.18, primary_score)


def duration_similarity(source_ms: int | None, candidate_ms: int | None) -> float:
    if not source_ms or not candidate_ms:
        return 0.5
    diff = abs(source_ms - candidate_ms)
    if diff <= 3000:
        return 1.0
    if diff <= 7000:
        return 0.85
    if diff <= 12000:
        return 0.55
    if diff <= 20000:
        return 0.25
    return 0.0


def extract_variant_flags(*values: str | None) -> frozenset[str]:
    text = " ".join(value for value in values if value)
    flags: set[str] = set()
    for flag, patterns in _VARIANT_PATTERNS.items():
        if any(pattern.search(text) for pattern in patterns):
            flags.add(flag)
    return frozenset(flags)
