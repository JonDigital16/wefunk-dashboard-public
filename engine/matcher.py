"""Track-matching logic for the WEFUNK matching engine."""

import re

import numpy as np
from rapidfuzz import fuzz, process

from engine.utils import clean

MATCH_THRESHOLD = 88

VERSION_WORDS = {
    "remix",
    "mix",
    "edit",
    "version",
    "instrumental",
    "acapella",
    "a cappella",
    "live",
    "demo",
    "radio",
    "extended",
    "dub",
    "remaster",
    "remastered",
    "mono",
    "stereo",
    "alternate",
    "bonus",
    "blend",
}


def extract_version_words(value):
    """Return meaningful recording-version words from an original title."""
    text = str(value or "").lower()
    found = set()

    for word in VERSION_WORDS:
        if re.search(rf"\b{re.escape(word)}\b", text):
            found.add(word)

    return found


def versions_are_compatible(query_title, candidate_title):
    """Prevent alternate versions from matching an unmarked album version."""
    query_versions = extract_version_words(query_title)
    candidate_versions = extract_version_words(candidate_title)

    if not query_versions and not candidate_versions:
        return True

    return query_versions == candidate_versions


def compact_title(value):
    """Remove spaces and punctuation for strict compact comparison."""
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def title_score(query_clean, candidate_clean):
    """Compare titles while safely handling punctuation and spacing."""
    normal_score = fuzz.token_set_ratio(
        query_clean,
        candidate_clean,
    )

    query_compact = compact_title(query_clean)
    candidate_compact = compact_title(candidate_clean)

    if len(query_compact) >= 3 and query_compact == candidate_compact:
        return 100.0

    return normal_score


def build_match_index(library):
    """Prepare ordered arrays for vectorized full-library matching."""
    return {
        "titles": [item["title_c"] for item in library],
        "artists": [item["artist_c"] for item in library],
        "combined": [item["combined_c"] for item in library],
    }


def _match_full_library_vectorized(
    artist_c,
    track_c,
    track,
    library,
    match_index,
):
    """Score one track against the complete library using RapidFuzz."""
    combined_query = f"{artist_c} {track_c}"

    title_scores = process.cdist(
        [track_c],
        match_index["titles"],
        scorer=fuzz.token_set_ratio,
        dtype=np.float64,
        workers=-1,
    )[0]

    artist_scores = process.cdist(
        [artist_c],
        match_index["artists"],
        scorer=fuzz.token_set_ratio,
        dtype=np.float64,
        workers=-1,
    )[0]

    combined_scores = process.cdist(
        [combined_query],
        match_index["combined"],
        scorer=fuzz.token_set_ratio,
        dtype=np.float64,
        workers=-1,
    )[0]

    weighted_scores = np.trunc((title_scores * 0.65) + (artist_scores * 0.35))

    final_scores = np.maximum(
        weighted_scores,
        np.trunc(combined_scores),
    )

    ranked_indexes = np.argsort(final_scores)[::-1]

    for item_index in ranked_indexes:
        item_index = int(item_index)
        item = library[item_index]

        if not item.get("artist_c") or not item.get("title_c"):
            continue

        if not versions_are_compatible(
            track,
            item.get("title", ""),
        ):
            continue

        safer_title_score = title_score(
            track_c,
            item["title_c"],
        )

        safer_weighted_score = int(
            (safer_title_score * 0.65) + (artist_scores[item_index] * 0.35)
        )

        safer_combined_score = int(
            fuzz.token_set_ratio(
                combined_query,
                item["combined_c"],
            )
        )

        candidate_score = max(
            int(final_scores[item_index]),
            safer_weighted_score,
            safer_combined_score,
        )

        return item, candidate_score

    return None, 0


def match_track(
    artist,
    track,
    library,
    library_by_artist,
    match_index=None,
):
    """Find the best library match for one WEFUNK track."""
    artist_c = clean(artist)
    track_c = clean(track)

    best = None
    best_score = 0

    # Empty normalized values contain no usable matching evidence.
    if not artist_c or not track_c:
        return None, 0

    candidate_tracks = library_by_artist.get(artist_c)

    if candidate_tracks:
        for item in candidate_tracks:
            if not versions_are_compatible(
                track,
                item.get("title", ""),
            ):
                continue

            current_title_score = title_score(
                track_c,
                item["title_c"],
            )

            combined_score = fuzz.token_set_ratio(
                f"{artist_c} {track_c}",
                item["combined_c"],
            )

            score = max(
                current_title_score,
                combined_score,
            )

            if score > best_score:
                best_score = score
                best = item

    elif match_index is not None:
        best, best_score = _match_full_library_vectorized(
            artist_c,
            track_c,
            track,
            library,
            match_index,
        )

    else:
        for item in library:
            if not item.get("artist_c") or not item.get("title_c"):
                continue

            if not versions_are_compatible(
                track,
                item.get("title", ""),
            ):
                continue

            current_title_score = title_score(
                track_c,
                item["title_c"],
            )

            artist_score = fuzz.token_set_ratio(
                artist_c,
                item["artist_c"],
            )

            combined_score = fuzz.token_set_ratio(
                f"{artist_c} {track_c}",
                item["combined_c"],
            )

            score = max(
                int((current_title_score * 0.65) + (artist_score * 0.35)),
                int(combined_score),
            )

            if score > best_score:
                best_score = score
                best = item

    return best, best_score


def is_match(best, score, threshold=MATCH_THRESHOLD):
    """Return True when the candidate meets the matching threshold."""
    return best is not None and score >= threshold
