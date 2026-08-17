"""Core media models shared across the WEFUNK engine.

MediaItem is the common representation of a piece of music or media metadata.

It may represent:

- a local audio file,
- a WEFUNK playlist entry,
- a database record,
- an imported API result,
- another music-related source.

This module contains data structures only. It does not scan files, query
databases, resolve genres, or modify metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping


def _clean_optional_text(
    value: str | None,
    field_name: str,
) -> str | None:
    """Strip an optional text value."""

    if value is None:
        return None

    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string or None")

    cleaned = value.strip()
    return cleaned or None


def _clean_required_text(
    value: str,
    field_name: str,
) -> str:
    """Strip and validate a required text value."""

    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")

    cleaned = value.strip()

    if not cleaned:
        raise ValueError(f"{field_name} cannot be empty")

    return cleaned


def _clean_values(values: Iterable[str]) -> tuple[str, ...]:
    """Clean text values while preserving order and removing duplicates."""

    cleaned: list[str] = []
    seen: set[str] = set()

    for value in values:
        item = _clean_required_text(value, "media value")

        if item not in seen:
            seen.add(item)
            cleaned.append(item)

    return tuple(cleaned)


def _freeze_metadata(
    metadata: Mapping[str, Any],
) -> Mapping[str, Any]:
    """Copy metadata into a read-only mapping."""

    if not isinstance(metadata, Mapping):
        raise TypeError("metadata must be a mapping")

    cleaned: dict[str, Any] = {}

    for key, value in metadata.items():
        if not isinstance(key, str):
            raise TypeError("metadata keys must be strings")

        cleaned_key = key.strip()

        if not cleaned_key:
            raise ValueError("metadata keys cannot be empty")

        cleaned[cleaned_key] = value

    return MappingProxyType(cleaned)


@dataclass(frozen=True, slots=True)
class MediaItem:
    """A source-independent representation of one media item.

    A MediaItem may describe a local audio file or an item that exists only
    in an external source, such as a WEFUNK playlist entry.

    The structured fields contain values commonly used throughout WEFUNK.
    Less common source-specific values belong in ``metadata``.
    """

    source: str
    genres: tuple[str, ...] = ()

    path: Path | None = None
    artist: str | None = None
    album: str | None = None
    title: str | None = None

    source_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        source = _clean_required_text(self.source, "source")
        genres = _clean_values(self.genres)

        path = self.path

        if path is not None:
            path = Path(path).expanduser()

        artist = _clean_optional_text(self.artist, "artist")
        album = _clean_optional_text(self.album, "album")
        title = _clean_optional_text(self.title, "title")
        source_id = _clean_optional_text(self.source_id, "source_id")
        metadata = _freeze_metadata(self.metadata)

        object.__setattr__(self, "source", source)
        object.__setattr__(self, "genres", genres)
        object.__setattr__(self, "path", path)
        object.__setattr__(self, "artist", artist)
        object.__setattr__(self, "album", album)
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "source_id", source_id)
        object.__setattr__(self, "metadata", metadata)

    @property
    def has_genres(self) -> bool:
        """Return True when at least one genre value is present."""

        return bool(self.genres)

    @property
    def primary_genre(self) -> str | None:
        """Return the first genre, or None if no genres are present."""

        return self.genres[0] if self.genres else None

    @property
    def is_local_file(self) -> bool:
        """Return True when this item is backed by a local path."""

        return self.path is not None

    @property
    def filename(self) -> str | None:
        """Return the local filename when this item has a path."""

        if self.path is None:
            return None

        return self.path.name

    @property
    def file_extension(self) -> str | None:
        """Return the lowercase file extension without a leading period."""

        if self.path is None:
            return None

        suffix = self.path.suffix.casefold().lstrip(".")
        return suffix or None

    @property
    def display_name(self) -> str:
        """Return a readable description for reports and logs."""

        artist_title = " — ".join(value for value in (self.artist, self.title) if value)

        if artist_title:
            return artist_title

        if self.album:
            return self.album

        if self.path is not None:
            return self.path.name

        if self.source_id:
            return self.source_id

        return f"Unnamed {self.source} item"

    def with_genres(
        self,
        genres: Iterable[str],
    ) -> MediaItem:
        """Return a copy of this item with different genre values."""

        return MediaItem(
            source=self.source,
            genres=tuple(genres),
            path=self.path,
            artist=self.artist,
            album=self.album,
            title=self.title,
            source_id=self.source_id,
            metadata=self.metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""

        return {
            "source": self.source,
            "source_id": self.source_id,
            "path": (str(self.path) if self.path is not None else None),
            "artist": self.artist,
            "album": self.album,
            "title": self.title,
            "genres": list(self.genres),
            "metadata": dict(self.metadata),
        }
