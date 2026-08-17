"""Metadata readers for local WEFUNK media files.

This module converts one local audio file into a MediaItem.

It does not discover files, resolve genres, or modify metadata.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

from mutagen import File as MutagenFile
from mutagen import MutagenError

from .models import MediaItem


GENRE_SEPARATOR_PATTERN = re.compile(r"\x00|\s*[;|]\s*")


class MediaReaderError(Exception):
    """Base exception for media-reader failures."""


class MediaFileNotFoundError(MediaReaderError):
    """Raised when the requested media file does not exist."""


class UnsupportedMediaError(MediaReaderError):
    """Raised when Mutagen cannot recognize a media file."""


class MetadataReadError(MediaReaderError):
    """Raised when metadata cannot be read from a media file."""


def _clean_optional_value(value: Any) -> str | None:
    """Convert one metadata value to clean optional text."""

    if value is None:
        return None

    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")

    cleaned = str(value).strip()
    return cleaned or None


def _flatten_tag_values(value: Any) -> tuple[Any, ...]:
    """Return one tag value as a flat tuple."""

    if value is None:
        return ()

    if isinstance(value, (str, bytes)):
        return (value,)

    if isinstance(value, Iterable):
        flattened: list[Any] = []

        for item in value:
            if isinstance(item, (list, tuple, set)):
                flattened.extend(item)
            else:
                flattened.append(item)

        return tuple(flattened)

    return (value,)


def _first_tag(tags: Any, *names: str) -> str | None:
    """Return the first non-empty value for the requested tag names."""

    if tags is None:
        return None

    for name in names:
        try:
            raw_value = tags.get(name)
        except (AttributeError, KeyError, TypeError):
            continue

        for value in _flatten_tag_values(raw_value):
            cleaned = _clean_optional_value(value)

            if cleaned:
                return cleaned

    return None


def _genre_values(tags: Any) -> tuple[str, ...]:
    """Extract genre values while preserving their original spelling.

    Mutagen may expose genres as multiple values or as one string containing
    semicolon, pipe, or null separators. Slashes are intentionally preserved
    because values such as ``Rap/Hip Hop`` may be approved aliases.
    """

    if tags is None:
        return ()

    raw_values: list[Any] = []

    for name in ("genre", "genres"):
        try:
            value = tags.get(name)
        except (AttributeError, KeyError, TypeError):
            continue

        raw_values.extend(_flatten_tag_values(value))

    genres: list[str] = []
    seen: set[str] = set()

    for raw_value in raw_values:
        cleaned = _clean_optional_value(raw_value)

        if not cleaned:
            continue

        parts = GENRE_SEPARATOR_PATTERN.split(cleaned)

        for part in parts:
            genre = part.strip()

            if not genre or genre in seen:
                continue

            seen.add(genre)
            genres.append(genre)

    return tuple(genres)


def _technical_metadata(audio: Any, path: Path) -> dict[str, Any]:
    """Build JSON-compatible technical metadata for a media file."""

    metadata: dict[str, Any] = {
        "file_extension": path.suffix.casefold().lstrip(".") or None,
    }

    try:
        stat = path.stat()
    except OSError:
        stat = None

    if stat is not None:
        metadata["file_size_bytes"] = stat.st_size
        metadata["modified_time"] = stat.st_mtime

    info = getattr(audio, "info", None)

    if info is None:
        return metadata

    fields = {
        "length": "duration_seconds",
        "bitrate": "bitrate",
        "sample_rate": "sample_rate",
        "channels": "channels",
        "bits_per_sample": "bits_per_sample",
    }

    for attribute, metadata_name in fields.items():
        value = getattr(info, attribute, None)

        if value is None:
            continue

        if metadata_name == "duration_seconds":
            try:
                metadata[metadata_name] = round(float(value), 3)
            except (TypeError, ValueError):
                continue
        elif isinstance(value, (str, int, float, bool)):
            metadata[metadata_name] = value
        else:
            metadata[metadata_name] = str(value)

    return metadata


class MutagenMediaReader:
    """Read one local audio file using Mutagen."""

    source_name = "music-file"

    def read(self, path: str | Path) -> MediaItem:
        """Read a local audio file and return a MediaItem."""

        media_path = Path(path).expanduser()

        if not media_path.exists():
            raise MediaFileNotFoundError(
                f"Media file does not exist: {media_path}"
            )

        if not media_path.is_file():
            raise MediaReaderError(
                f"Media path is not a file: {media_path}"
            )

        try:
            audio = MutagenFile(media_path, easy=True)
        except (MutagenError, OSError, ValueError) as exc:
            raise MetadataReadError(
                f"Could not read metadata from {media_path}: {exc}"
            ) from exc

        if audio is None:
            raise UnsupportedMediaError(
                f"Unsupported or unrecognized media file: {media_path}"
            )

        tags = getattr(audio, "tags", None)

        artist = _first_tag(
            tags,
            "artist",
            "albumartist",
            "album artist",
        )
        album = _first_tag(tags, "album")
        title = _first_tag(tags, "title")
        genres = _genre_values(tags)

        metadata = _technical_metadata(audio, media_path)

        album_artist = _first_tag(
            tags,
            "albumartist",
            "album artist",
        )
        date = _first_tag(tags, "date", "year")
        track_number = _first_tag(
            tags,
            "tracknumber",
            "track",
        )
        disc_number = _first_tag(
            tags,
            "discnumber",
            "disc",
        )
        composer = _first_tag(tags, "composer")

        optional_metadata = {
            "album_artist": album_artist,
            "date": date,
            "track_number": track_number,
            "disc_number": disc_number,
            "composer": composer,
        }

        metadata.update(
            {
                key: value
                for key, value in optional_metadata.items()
                if value is not None
            }
        )

        return MediaItem(
            source=self.source_name,
            path=media_path,
            artist=artist,
            album=album,
            title=title,
            genres=genres,
            metadata=metadata,
        )

    def __call__(self, path: str | Path) -> MediaItem:
        """Allow the reader instance to be called like a function."""

        return self.read(path)
