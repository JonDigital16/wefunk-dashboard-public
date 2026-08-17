"""Analyze why WEFUNK tracks failed to match the local music library.

This script is read-only. It does not modify the database, matching cache,
library files, or tags.

Outputs:
    $WEFUNK_EXPORT_DIR/wefunk_unmatched_analysis.csv
    $WEFUNK_EXPORT_DIR/wefunk_unmatched_summary.csv
"""

import csv
import sqlite3
from collections import Counter, defaultdict
import os
from pathlib import Path

from rapidfuzz import fuzz, process

from engine.matcher import (
    extract_version_words,
    versions_are_compatible,
)

DB_FILE = Path(os.environ.get("WEFUNK_DATA_DIR", Path.home() / ".local" / "share" / "wefunk")).expanduser().resolve() / "db" / 'wefunk.db'
EXPORT_DIR = Path(os.environ.get("WEFUNK_EXPORT_DIR", Path(os.environ.get("WEFUNK_DATA_DIR", Path.home() / ".local" / "share" / "wefunk")) / "exports")).expanduser().resolve()

ANALYSIS_CSV = EXPORT_DIR / "wefunk_unmatched_analysis.csv"
SUMMARY_CSV = EXPORT_DIR / "wefunk_unmatched_summary.csv"

MATCHER_VERSION = "tags-v2.2"

VERSION_WORDS = {
    "remix",
    "mix",
    "edit",
    "version",
    "instrumental",
    "acapella",
    "a",
    "cappella",
    "live",
    "demo",
    "radio",
    "extended",
    "dub",
    "remaster",
    "remastered",
    "mono",
    "stereo",
    "original",
    "alternate",
    "bonus",
}


def remove_version_words(value):
    """Remove common version markers for diagnostic comparison only."""
    words = str(value or "").split()
    cleaned = [word for word in words if word not in VERSION_WORDS]
    return " ".join(cleaned).strip()


def classify_same_artist(
    track,
    track_norm,
    best_title,
    best_title_norm,
    same_artist_score,
    same_artist_title_score,
):
    """Classify a miss when the normalized artist exists locally.

    Normalized titles are used for similarity scoring. Original display
    titles are used for recording-version compatibility so markers such as
    remix, instrumental, blend, live, and edit are preserved.
    """
    stripped_query = remove_version_words(track_norm)
    stripped_candidate = remove_version_words(best_title_norm)

    stripped_score = 0

    if stripped_query and stripped_candidate:
        stripped_score = int(
            title_comparison(
                stripped_query,
                stripped_candidate,
            )
        )

    query_versions = extract_version_words(track)
    candidate_versions = extract_version_words(best_title)

    version_words_present = bool(
        query_versions or candidate_versions
    )

    version_compatible = versions_are_compatible(
        track,
        best_title,
    )

    if same_artist_title_score >= 88 and not version_compatible:
        category = "alternate_version_correctly_rejected"
    elif same_artist_title_score >= 88 and version_compatible:
        category = "possible_true_matcher_miss"
    elif stripped_score >= 88 and version_words_present:
        category = "version_or_remix_difference"
    elif same_artist_score >= 80:
        category = "close_title_same_artist"
    elif same_artist_score >= 65:
        category = "moderate_title_difference_same_artist"
    else:
        category = "title_not_found_for_known_artist"

    return category, stripped_score


ARTIST_STOP_WORDS = {
    "and",
    "the",
    "of",
    "a",
    "an",
    "with",
    "presents",
    "present",
}


def collapse_initials(value):
    """Collapse punctuated initials such as D.J. and U.M.C.'s."""
    words = str(value or "").split()
    collapsed = []
    initials = []

    def flush_initials():
        if initials:
            collapsed.append("".join(initials))
            initials.clear()

    for word in words:
        if len(word) == 1:
            initials.append(word)
        else:
            flush_initials()
            collapsed.append(word)

    flush_initials()
    return " ".join(collapsed)


def meaningful_artist_tokens(value):
    """Return useful artist tokens while ignoring joining words."""
    return {
        token
        for token in collapse_initials(value).split()
        if token not in ARTIST_STOP_WORDS
    }


def artist_comparison(query, candidate):
    """Score artist names without rewarding arbitrary containment.

    Returns:
        comparison score,
        comparison reason,
        meaningful token overlap,
        query-contained-in-candidate flag.
    """
    query_c = collapse_initials(query)
    candidate_c = collapse_initials(candidate)

    query_compact = query_c.replace(" ", "")
    candidate_compact = candidate_c.replace(" ", "")

    query_tokens = meaningful_artist_tokens(query_c)
    candidate_tokens = meaningful_artist_tokens(candidate_c)

    shared = query_tokens & candidate_tokens
    union = query_tokens | candidate_tokens

    overlap = len(shared) / len(union) if union else 0.0

    # A multiword credit may contain a shorter credited artist.
    query_is_credit_subset = len(query_tokens) >= 2 and query_tokens < candidate_tokens

    candidate_is_credit_subset = (
        len(candidate_tokens) >= 2 and candidate_tokens < query_tokens
    )

    # Also permit a distinctive single-token artist such as GZA within
    # "Genius GZA". Short generic tokens such as DJ, MC, M, or the are
    # intentionally excluded.
    distinctive_single_query_subset = (
        len(query_tokens) == 1
        and query_tokens < candidate_tokens
        and len(next(iter(query_tokens), "")) >= 3
    )

    distinctive_single_candidate_subset = (
        len(candidate_tokens) == 1
        and candidate_tokens < query_tokens
        and len(next(iter(candidate_tokens), "")) >= 3
    )

    credit_subset = (
        query_is_credit_subset
        or candidate_is_credit_subset
        or distinctive_single_query_subset
        or distinctive_single_candidate_subset
    )

    if query_compact and len(query_compact) >= 4 and query_compact == candidate_compact:
        return 100, "compact_exact", overlap, credit_subset

    ratio_score = int(fuzz.ratio(query_c, candidate_c))
    sort_score = int(fuzz.token_sort_ratio(query_c, candidate_c))

    score = max(ratio_score, sort_score)

    if credit_subset:
        score = max(score, 94)

    reason = "credit_subset" if credit_subset else "whole_name_similarity"

    return score, reason, overlap, credit_subset


def title_comparison(query, candidate):
    """Compare complete titles without rewarding arbitrary containment.

    token_set_ratio can report 100 for unrelated pairs such as:
        "stop" vs "don't stop the feeling"
        "go" vs "does disc go with d.a.t."

    This comparison instead rewards full-string similarity, reordered
    words, and punctuation/acronym differences.
    """
    query_c = collapse_initials(str(query or ""))
    candidate_c = collapse_initials(str(candidate or ""))

    query_compact = query_c.replace(" ", "")
    candidate_compact = candidate_c.replace(" ", "")

    if query_compact and len(query_compact) >= 2 and query_compact == candidate_compact:
        return 100

    ratio_score = int(fuzz.ratio(query_c, candidate_c))
    sort_score = int(fuzz.token_sort_ratio(query_c, candidate_c))

    return max(ratio_score, sort_score)


def classify_missing_artist(
    artist_similarity,
    artist_reason,
    token_overlap,
    credit_subset,
    closest_artist_title_score,
):
    """Classify a miss using both artist and title evidence.

    Artist-name similarity alone is not enough to call something a likely
    credit or alias difference. The proposed artist must also contain a
    reasonably similar title.
    """
    title_score = int(closest_artist_title_score or 0)

    if artist_reason == "compact_exact":
        if title_score >= 88:
            return "likely_artist_punctuation_and_title_match"

        if title_score >= 75:
            return "possible_artist_punctuation_difference"

        return "artist_punctuation_match_but_title_not_found"

    if credit_subset and artist_similarity >= 94:
        # Small token subsets such as "DJ Rap" inside
        # "Kool G Rap and DJ Polo" are often accidental.
        if token_overlap < 0.50:
            return "accidental_artist_token_subset"

        if title_score >= 88:
            return "likely_artist_credit_and_title_match"

        if title_score >= 75:
            return "possible_artist_credit_difference"

        return "artist_credit_similarity_but_title_not_found"

    if artist_similarity >= 90 and token_overlap >= 0.60:
        if title_score >= 88:
            return "likely_artist_alias_and_title_match"

        if title_score >= 75:
            return "possible_artist_alias_or_spelling_difference"

        return "artist_name_similarity_but_title_not_found"

    if artist_similarity >= 80 and token_overlap >= 0.40:
        if title_score >= 88:
            return "possible_artist_alias_with_title_match"

        return "possible_artist_name_similarity_only"

    return "artist_not_in_library"


def build_unmatched_reason(
    category,
    track,
    same_artist_best_title,
    same_artist_title_score,
    closest_artist,
    closest_artist_best_title,
    closest_artist_score,
    closest_artist_title_score,
):
    """Return a concise, human-readable explanation for an unmatched track."""
    title_score = int(same_artist_title_score or 0)
    artist_score = int(closest_artist_score or 0)
    closest_title_score = int(closest_artist_title_score or 0)

    if category == "alternate_version_correctly_rejected":
        return (
            f'The artist and base title are present, but "{track}" and '
            f'"{same_artist_best_title}" are different recording versions '
            f'(for example remix, instrumental, edit, live, blend, or original).'
        )

    if category == "version_or_remix_difference":
        return (
            f'The closest library title is "{same_artist_best_title}", but '
            f'version wording differs and the pure title score was {title_score}.'
        )

    if category == "possible_true_matcher_miss":
        return (
            f'The exact artist exists and "{same_artist_best_title}" scored '
            f'{title_score}, meeting the expected title threshold. This should '
            f'be reviewed as a likely matcher miss.'
        )

    if category == "close_title_same_artist":
        return (
            f'The exact artist exists, but the closest title '
            f'"{same_artist_best_title}" scored {title_score}, just below '
            f'the match threshold.'
        )

    if category == "moderate_title_difference_same_artist":
        return (
            f'The exact artist exists, but the closest title '
            f'"{same_artist_best_title}" scored only {title_score}.'
        )

    if category == "title_not_found_for_known_artist":
        return (
            "The artist exists in the library, but no sufficiently similar "
            "title was found under that artist."
        )

    if category == "likely_artist_credit_and_title_match":
        return (
            f'The closest artist credit is "{closest_artist}" and the title '
            f'"{closest_artist_best_title}" scored {closest_title_score}. '
            f'The mismatch is probably caused by featured-artist or '
            f'collaboration credits.'
        )

    if category == "possible_artist_credit_difference":
        return (
            f'The artist credit resembles "{closest_artist}", but the closest '
            f'title scored only {closest_title_score}.'
        )

    if category == "artist_credit_similarity_but_title_not_found":
        return (
            f'The artist credit resembles "{closest_artist}", but that artist '
            f'does not contain a sufficiently similar title.'
        )

    if category == "likely_artist_punctuation_and_title_match":
        return (
            f'The artist appears to be the same as "{closest_artist}" after '
            f'punctuation and spacing are removed, and the title scored '
            f'{closest_title_score}.'
        )

    if category == "possible_artist_punctuation_difference":
        return (
            f'The artist resembles "{closest_artist}" after punctuation '
            f'normalization, but the title scored only {closest_title_score}.'
        )

    if category == "artist_punctuation_match_but_title_not_found":
        return (
            f'The artist appears to match "{closest_artist}" after punctuation '
            f'normalization, but no similar title was found.'
        )

    if category == "likely_artist_alias_and_title_match":
        return (
            f'The title "{closest_artist_best_title}" scored '
            f'{closest_title_score}, and "{closest_artist}" may be an alias '
            f'or alternate artist spelling.'
        )

    if category == "possible_artist_alias_with_title_match":
        return (
            f'The title strongly resembles "{closest_artist_best_title}", but '
            f'the relationship to artist "{closest_artist}" is uncertain.'
        )

    if category == "possible_artist_alias_or_spelling_difference":
        return (
            f'The artist may be a spelling variation or alias of '
            f'"{closest_artist}", but the title evidence is not conclusive.'
        )

    if category == "artist_name_similarity_but_title_not_found":
        return (
            f'The artist name resembles "{closest_artist}" with an artist '
            f'score of {artist_score}, but no matching title was found.'
        )

    if category == "possible_artist_name_similarity_only":
        return (
            f'The artist name has moderate similarity to "{closest_artist}", '
            f'but the title evidence is weak.'
        )

    if category == "accidental_artist_token_subset":
        return (
            f'Part of the artist credit overlaps with "{closest_artist}", but '
            f'the overlap is likely coincidental.'
        )

    if category == "artist_not_in_library":
        return (
            "No sufficiently similar artist credit was found in the indexed "
            "music library."
        )

    return "The track did not meet the current artist, title, or version rules."

def classify_global_candidate(score):
    """Describe the fallback result without using it as the main category."""
    score = int(score or 0)

    if score >= 88:
        return "above_match_threshold"

    if score >= 80:
        return "strong_below_threshold"

    if score >= 60:
        return "weak"

    if score > 0:
        return "very_weak"

    return "none"


def main():
    if not DB_FILE.exists():
        raise FileNotFoundError(f"Database not found: {DB_FILE}")

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row

    try:
        library_rows = conn.execute("""
            SELECT
                file_path,
                artist,
                title,
                artist_norm,
                title_norm
            FROM library_index
            WHERE artist_norm <> ''
              AND title_norm <> ''
            ORDER BY file_path
            """).fetchall()

        unmatched_rows = conn.execute(
            """
            SELECT
                wefunk_track_id,
                show_id,
                artist,
                track,
                artist_norm,
                track_norm,
                score,
                best_candidate_path
            FROM track_matches
            WHERE matched = 0
              AND matcher_version = ?
            ORDER BY artist_norm, track_norm, show_id
            """,
            (MATCHER_VERSION,),
        ).fetchall()

    finally:
        conn.close()

    if not library_rows:
        raise RuntimeError("The library_index table is empty.")

    if not unmatched_rows:
        print(f"No unmatched rows found for matcher version " f"{MATCHER_VERSION}.")
        return

    library_by_artist = defaultdict(list)
    library_by_path = {}
    artist_display = {}

    for row in library_rows:
        item = dict(row)
        artist_norm = item["artist_norm"]

        library_by_artist[artist_norm].append(item)
        library_by_path[item["file_path"]] = item
        artist_display.setdefault(artist_norm, item["artist"])

    artist_norms = sorted(library_by_artist)

    # Group repeated WEFUNK plays of the same normalized artist/title.
    grouped = {}

    for row in unmatched_rows:
        key = (row["artist_norm"], row["track_norm"])

        if key not in grouped:
            grouped[key] = {
                "artist": row["artist"],
                "track": row["track"],
                "artist_norm": row["artist_norm"],
                "track_norm": row["track_norm"],
                "occurrences": 0,
                "show_ids": set(),
                "database_best_score": row["score"] or 0,
                "database_best_candidate_path": (row["best_candidate_path"] or ""),
            }

        group = grouped[key]
        group["occurrences"] += 1

        if row["show_id"]:
            group["show_ids"].add(str(row["show_id"]))

        if (row["score"] or 0) > group["database_best_score"]:
            group["database_best_score"] = row["score"] or 0
            group["database_best_candidate_path"] = row["best_candidate_path"] or ""

    analysis_rows = []
    category_counts_unique = Counter()
    category_counts_occurrences = Counter()

    total = len(grouped)

    for index, group in enumerate(grouped.values(), start=1):
        artist_norm = group["artist_norm"]
        track_norm = group["track_norm"]
        global_path = group["database_best_candidate_path"]
        global_item = library_by_path.get(global_path)

        exact_artist_exists = artist_norm in library_by_artist

        same_artist_best_title = ""
        same_artist_best_title_norm = ""
        same_artist_best_path = ""
        same_artist_score = 0
        same_artist_title_score = 0
        stripped_title_score = 0

        closest_artist_norm = ""
        closest_artist = ""
        closest_artist_score = 0
        closest_artist_best_title = ""
        closest_artist_best_title_norm = ""
        closest_artist_best_path = ""
        closest_artist_title_score = 0

        if exact_artist_exists:
            for item in library_by_artist[artist_norm]:
                pure_title_score = int(
                    title_comparison(
                        track_norm,
                        item["title_norm"],
                    )
                )

                combined_score = int(
                    title_comparison(
                        f"{artist_norm} {track_norm}",
                        f"{item['artist_norm']} {item['title_norm']}",
                    )
                )

                score = max(
                    pure_title_score,
                    combined_score,
                )

                candidate_rank = (
                    pure_title_score,
                    score,
                )

                current_rank = (
                    same_artist_title_score,
                    same_artist_score,
                )

                if candidate_rank > current_rank:
                    same_artist_score = score
                    same_artist_title_score = pure_title_score
                    same_artist_best_title = item["title"]
                    same_artist_best_title_norm = item["title_norm"]
                    same_artist_best_path = item["file_path"]

            category, stripped_title_score = classify_same_artist(
                group["track"],
                track_norm,
                same_artist_best_title,
                same_artist_best_title_norm,
                same_artist_score,
                same_artist_title_score,
            )
        else:
            closest_artist_reason = ""
            closest_artist_overlap = 0.0
            closest_artist_credit_subset = False
            best_pair_rank = None

            # Rank artist and title evidence together. Picking an artist
            # solely by name can overlook a slightly less similar artist
            # that contains the exact requested title.
            for candidate_artist_norm in artist_norms:
                (
                    candidate_artist_score,
                    candidate_reason,
                    candidate_overlap,
                    candidate_credit_subset,
                ) = artist_comparison(
                    artist_norm,
                    candidate_artist_norm,
                )

                candidate_best_title = ""
                candidate_best_title_norm = ""
                candidate_best_path = ""
                candidate_best_title_score = 0

                for item in library_by_artist[candidate_artist_norm]:
                    title_score = int(
                        title_comparison(
                            track_norm,
                            item["title_norm"],
                        )
                    )

                    if title_score > candidate_best_title_score:
                        candidate_best_title_score = title_score
                        candidate_best_title = item["title"]
                        candidate_best_title_norm = item["title_norm"]
                        candidate_best_path = item["file_path"]

                # Exact or near-exact titles deserve substantial weight, but
                # artist evidence still prevents arbitrary title collisions.
                combined_pair_score = (
                    candidate_artist_score * 0.55 + candidate_best_title_score * 0.45
                )

                title_match_tier = (
                    3
                    if candidate_best_title_score >= 95
                    else (
                        2
                        if candidate_best_title_score >= 88
                        else 1 if candidate_best_title_score >= 75 else 0
                    )
                )

                artist_match_tier = (
                    3
                    if candidate_artist_score >= 94
                    else (
                        2
                        if candidate_artist_score >= 85
                        else 1 if candidate_artist_score >= 65 else 0
                    )
                )

                # Sorting first by combined evidence avoids selecting a
                # collaboration with a 94 artist score and a completely
                # unrelated title over a shorter credit with an exact title.
                pair_rank = (
                    round(combined_pair_score, 4),
                    title_match_tier,
                    artist_match_tier,
                    candidate_best_title_score,
                    candidate_artist_score,
                )

                if best_pair_rank is None or pair_rank > best_pair_rank:
                    best_pair_rank = pair_rank
                    closest_artist_norm = candidate_artist_norm
                    closest_artist_score = candidate_artist_score
                    closest_artist_reason = candidate_reason
                    closest_artist_overlap = candidate_overlap
                    closest_artist_credit_subset = candidate_credit_subset
                    closest_artist_title_score = candidate_best_title_score
                    closest_artist_best_title = candidate_best_title
                    closest_artist_best_title_norm = candidate_best_title_norm
                    closest_artist_best_path = candidate_best_path

            if closest_artist_norm:
                closest_artist = artist_display.get(
                    closest_artist_norm,
                    closest_artist_norm,
                )

            category = classify_missing_artist(
                closest_artist_score,
                closest_artist_reason,
                closest_artist_overlap,
                closest_artist_credit_subset,
                closest_artist_title_score,
            )

        unmatched_reason = build_unmatched_reason(
            category=category,
            track=group["track"],
            same_artist_best_title=same_artist_best_title,
            same_artist_title_score=same_artist_title_score,
            closest_artist=closest_artist,
            closest_artist_best_title=closest_artist_best_title,
            closest_artist_score=closest_artist_score,
            closest_artist_title_score=closest_artist_title_score,
        )

        category_counts_unique[category] += 1
        category_counts_occurrences[category] += group["occurrences"]

        analysis_rows.append(
            {
                "category": category,
                "unmatched_reason": unmatched_reason,
                "occurrences": group["occurrences"],
                "show_ids": "|".join(
                    sorted(
                        group["show_ids"],
                        key=lambda value: (int(value) if value.isdigit() else value),
                    )
                ),
                "artist": group["artist"],
                "track": group["track"],
                "artist_norm": artist_norm,
                "track_norm": track_norm,
                "exact_artist_exists": int(exact_artist_exists),
                "same_artist_best_score": same_artist_score,
                "same_artist_title_score": same_artist_title_score,
                "same_artist_best_title": same_artist_best_title,
                "same_artist_best_path": same_artist_best_path,
                "version_stripped_score": stripped_title_score,
                "closest_library_artist": closest_artist,
                "closest_artist_score": closest_artist_score,
                "closest_artist_best_title": (closest_artist_best_title),
                "closest_artist_title_score": (closest_artist_title_score),
                "closest_artist_best_path": (closest_artist_best_path),
                "global_candidate_strength": classify_global_candidate(
                    group["database_best_score"]
                ),
                "database_best_score": group["database_best_score"],
                "database_best_candidate_artist": (
                    global_item["artist"] if global_item else ""
                ),
                "database_best_candidate_title": (
                    global_item["title"] if global_item else ""
                ),
                "database_best_candidate_path": global_path,
            }
        )

        if index % 1000 == 0 or index == total:
            print(f"Analyzed {index:,} of {total:,} " f"unique unmatched tracks")

    analysis_rows.sort(
        key=lambda row: (
            -row["occurrences"],
            row["category"],
            row["artist_norm"],
            row["track_norm"],
        )
    )

    fieldnames = [
        "category",
        "unmatched_reason",
        "occurrences",
        "show_ids",
        "artist",
        "track",
        "artist_norm",
        "track_norm",
        "exact_artist_exists",
        "same_artist_best_score",
        "same_artist_title_score",
        "same_artist_best_title",
        "same_artist_best_path",
        "version_stripped_score",
        "closest_library_artist",
        "closest_artist_score",
        "closest_artist_best_title",
        "closest_artist_title_score",
        "closest_artist_best_path",
        "global_candidate_strength",
        "database_best_score",
        "database_best_candidate_artist",
        "database_best_candidate_title",
        "database_best_candidate_path",
    ]

    with ANALYSIS_CSV.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(analysis_rows)

    summary_rows = []

    for category, unique_count in category_counts_unique.most_common():
        occurrence_count = category_counts_occurrences[category]

        summary_rows.append(
            {
                "category": category,
                "unique_tracks": unique_count,
                "wefunk_occurrences": occurrence_count,
                "percent_of_unique_tracks": round(
                    unique_count / len(grouped) * 100,
                    2,
                ),
                "percent_of_occurrences": round(
                    occurrence_count / len(unmatched_rows) * 100,
                    2,
                ),
            }
        )

    with SUMMARY_CSV.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "category",
                "unique_tracks",
                "wefunk_occurrences",
                "percent_of_unique_tracks",
                "percent_of_occurrences",
            ],
        )
        writer.writeheader()
        writer.writerows(summary_rows)

    print()
    print("Unmatched analysis complete")
    print(f"Matcher version: {MATCHER_VERSION}")
    print(f"Unmatched database rows: {len(unmatched_rows):,}")
    print(f"Unique unmatched tracks: {len(grouped):,}")
    print()

    print(f"{'Category':45} " f"{'Unique':>9} " f"{'Occurrences':>12}")
    print("-" * 70)

    for row in summary_rows:
        print(
            f"{row['category'][:45]:45} "
            f"{row['unique_tracks']:>9,} "
            f"{row['wefunk_occurrences']:>12,}"
        )

    print()
    print(f"Detailed analysis: {ANALYSIS_CSV}")
    print(f"Category summary: {SUMMARY_CSV}")


if __name__ == "__main__":
    main()
