"""Reusable genre-review report generation.

This module converts a track-level manual-review CSV into album-centric
cleanup reports. It does not read or modify media files.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AlbumGenreReview:
    """One album requiring manual genre cleanup."""

    unknown_genre: str
    artist: str
    album_artist: str
    album: str
    track_count: int
    genre_values: tuple[str, ...]
    folder: str
    files: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GenreReviewSummary:
    """Aggregate totals for one unknown genre value."""

    unknown_genre: str
    album_count: int
    track_count: int


class GenreReviewReporter:
    """Generate album-centric reports from manual-review audit rows."""

    ALBUM_FIELDNAMES = (
        "status",
        "unknown_genre",
        "artist",
        "album_artist",
        "album",
        "tracks",
        "genre_values",
        "folder",
        "files",
    )

    SUMMARY_FIELDNAMES = (
        "unknown_genre",
        "albums",
        "tracks",
    )

    def load_manual_review(
        self,
        input_path: Path,
    ) -> list[dict[str, str]]:
        """Load a manual-review CSV."""

        input_path = Path(input_path)

        if not input_path.exists():
            raise FileNotFoundError(
                f"Manual-review report not found: {input_path}"
            )

        with input_path.open(
            encoding="utf-8",
            newline="",
        ) as handle:
            return list(csv.DictReader(handle))

    def build_album_reviews(
        self,
        rows: list[dict[str, str]],
    ) -> tuple[AlbumGenreReview, ...]:
        """Group manual-review rows by unknown genre and album."""

        grouped: dict[
            tuple[str, str, str, str, str],
            dict[str, object],
        ] = {}

        for row in rows:
            path = self._first_value(
                row,
                "path",
                "file",
                "filepath",
            )

            artist = self._first_value(
                row,
                "artist",
                "track_artist",
            )

            album_artist = self._first_value(
                row,
                "album_artist",
                "albumartist",
            )

            album = self._first_value(
                row,
                "album",
                "album_name",
            )

            before = self._first_value(
                row,
                "before",
                "genres",
                "genre_values",
                "current_genres",
            )

            unknown_field = self._first_value(
                row,
                "unknown_genres",
                "unknown_genre",
                "unknown",
            )

            unknown_values = self._split_report_values(
                unknown_field
            )

            if not unknown_values:
                unknown_values = self._extract_unknowns_from_reason(
                    self._first_value(row, "reason")
                )

            if not unknown_values:
                unknown_values = ("Unknown",)

            genre_values = self._split_report_values(before)

            if not genre_values and before:
                genre_values = (before,)

            folder = (
                str(Path(path).parent)
                if path
                else ""
            )

            album_key = album or folder or "(Unknown Album)"
            artist_key = (
                album_artist
                or artist
                or "(Unknown Artist)"
            )

            for unknown_genre in unknown_values:
                key = (
                    unknown_genre.casefold(),
                    artist_key.casefold(),
                    album_key.casefold(),
                    folder.casefold(),
                    album_artist.casefold(),
                )

                if key not in grouped:
                    grouped[key] = {
                        "unknown_genre": unknown_genre,
                        "artists": set(),
                        "album_artist": album_artist,
                        "album": album or "(Unknown Album)",
                        "genre_values": set(),
                        "folder": folder,
                        "files": set(),
                    }

                record = grouped[key]

                if artist:
                    record["artists"].add(artist)

                for genre in genre_values:
                    record["genre_values"].add(genre)

                if path:
                    record["files"].add(path)

        reviews: list[AlbumGenreReview] = []

        for record in grouped.values():
            artists = sorted(
                record["artists"],
                key=str.casefold,
            )

            files = sorted(
                record["files"],
                key=str.casefold,
            )

            genre_values = sorted(
                record["genre_values"],
                key=str.casefold,
            )

            reviews.append(
                AlbumGenreReview(
                    unknown_genre=str(
                        record["unknown_genre"]
                    ),
                    artist="; ".join(artists),
                    album_artist=str(
                        record["album_artist"]
                    ),
                    album=str(record["album"]),
                    track_count=len(files),
                    genre_values=tuple(genre_values),
                    folder=str(record["folder"]),
                    files=tuple(files),
                )
            )

        reviews.sort(
            key=lambda review: (
                review.unknown_genre.casefold(),
                (
                    review.album_artist
                    or review.artist
                ).casefold(),
                review.album.casefold(),
                review.folder.casefold(),
            )
        )

        return tuple(reviews)

    def build_genre_summary(
        self,
        reviews: tuple[AlbumGenreReview, ...],
    ) -> tuple[GenreReviewSummary, ...]:
        """Aggregate album and track totals by unknown genre."""

        albums_by_genre: dict[str, int] = defaultdict(int)
        tracks_by_genre: dict[str, int] = defaultdict(int)
        display_names: dict[str, str] = {}

        for review in reviews:
            key = review.unknown_genre.casefold()

            display_names.setdefault(
                key,
                review.unknown_genre,
            )

            albums_by_genre[key] += 1
            tracks_by_genre[key] += review.track_count

        summaries = [
            GenreReviewSummary(
                unknown_genre=display_names[key],
                album_count=albums_by_genre[key],
                track_count=tracks_by_genre[key],
            )
            for key in display_names
        ]

        summaries.sort(
            key=lambda summary: (
                -summary.track_count,
                -summary.album_count,
                summary.unknown_genre.casefold(),
            )
        )

        return tuple(summaries)

    def write_album_review_csv(
        self,
        output_path: Path,
        reviews: tuple[AlbumGenreReview, ...],
    ) -> None:
        """Write the album-centric working report."""

        output_path = Path(output_path)
        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with output_path.open(
            "w",
            encoding="utf-8",
            newline="",
        ) as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=self.ALBUM_FIELDNAMES,
            )
            writer.writeheader()

            for review in reviews:
                writer.writerow({
                    "status": "",
                    "unknown_genre": review.unknown_genre,
                    "artist": review.artist,
                    "album_artist": review.album_artist,
                    "album": review.album,
                    "tracks": review.track_count,
                    "genre_values": " | ".join(
                        review.genre_values
                    ),
                    "folder": review.folder,
                    "files": " | ".join(review.files),
                })

    def write_genre_summary_csv(
        self,
        output_path: Path,
        summaries: tuple[GenreReviewSummary, ...],
    ) -> None:
        """Write the unknown-genre summary report."""

        output_path = Path(output_path)
        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with output_path.open(
            "w",
            encoding="utf-8",
            newline="",
        ) as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=self.SUMMARY_FIELDNAMES,
            )
            writer.writeheader()

            for summary in summaries:
                writer.writerow({
                    "unknown_genre": summary.unknown_genre,
                    "albums": summary.album_count,
                    "tracks": summary.track_count,
                })

    @staticmethod
    def _first_value(
        row: dict[str, str],
        *keys: str,
    ) -> str:
        """Return the first populated field from a row."""

        for key in keys:
            value = row.get(key)

            if value is not None and value.strip():
                return value.strip()

        return ""

    @staticmethod
    def _split_report_values(
        value: str,
    ) -> tuple[str, ...]:
        """Split values written by audit reports.

        Audit report list values use a vertical bar delimiter. Commas
        and slashes are intentionally preserved because they may be part
        of the unknown genre string itself.
        """

        if not value:
            return ()

        values = [
            part.strip()
            for part in value.split("|")
            if part.strip()
        ]

        return tuple(values)

    @staticmethod
    def _extract_unknowns_from_reason(
        reason: str,
    ) -> tuple[str, ...]:
        """Extract unknown values from an analyzer reason."""

        prefix = "Unknown genre values:"

        if not reason.startswith(prefix):
            return ()

        value = reason[len(prefix):].strip()

        if not value:
            return ()

        return (value,)
