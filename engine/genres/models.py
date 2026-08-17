"""Core data models for the WEFUNK genre subsystem.

This module contains data structures only. It does not read music files,
load YAML configuration, decide normalization rules, or modify metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Iterable, Mapping

from engine.media import MediaItem


class GenreAction(StrEnum):
    """Possible outcomes from genre analysis."""

    KEEP = "keep"
    NORMALIZE = "normalize"
    MANUAL_REVIEW = "manual-review"
    SKIP = "skip"


class GenreMatchType(StrEnum):
    """How a raw genre value matched the catalog."""

    CANONICAL = "canonical"
    ALIAS = "alias"
    UNKNOWN = "unknown"


class TransactionStatus(StrEnum):
    """Current state of a genre-normalization transaction."""

    PREPARED = "prepared"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    ROLLED_BACK = "rolled-back"


def _clean_text(value: str, field_name: str) -> str:
    """Strip and validate a required text value."""

    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")

    cleaned = value.strip()

    if not cleaned:
        raise ValueError(f"{field_name} cannot be empty")

    return cleaned


def _clean_optional_text(value: str | None) -> str | None:
    """Strip an optional text value."""

    if value is None:
        return None

    if not isinstance(value, str):
        raise TypeError("Optional text values must be strings or None")

    cleaned = value.strip()
    return cleaned or None


def _clean_genres(values: Iterable[str]) -> tuple[str, ...]:
    """Clean genre values while preserving order and removing duplicates."""

    cleaned: list[str] = []
    seen: set[str] = set()

    for value in values:
        genre = _clean_text(value, "genre")

        if genre not in seen:
            seen.add(genre)
            cleaned.append(genre)

    return tuple(cleaned)


@dataclass(frozen=True, slots=True)
class Genre:
    """One canonical genre from the WEFUNK catalog.

    Example:
        Genre(
            canonical="Jazz Rap",
            family="Hip-Hop",
            aliases=("Jazz-Rap",),
        )
    """

    canonical: str
    family: str
    aliases: tuple[str, ...] = ()
    description: str | None = None

    def __post_init__(self) -> None:
        canonical = _clean_text(self.canonical, "canonical")
        family = _clean_text(self.family, "family")
        aliases = _clean_genres(self.aliases)
        description = _clean_optional_text(self.description)

        aliases = tuple(
            alias
            for alias in aliases
            if alias.casefold() != canonical.casefold()
        )

        object.__setattr__(self, "canonical", canonical)
        object.__setattr__(self, "family", family)
        object.__setattr__(self, "aliases", aliases)
        object.__setattr__(self, "description", description)

    @property
    def all_names(self) -> tuple[str, ...]:
        """Return the canonical name followed by all approved aliases."""

        return (self.canonical, *self.aliases)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""

        result: dict[str, Any] = {
            "canonical": self.canonical,
            "family": self.family,
            "aliases": list(self.aliases),
        }

        if self.description is not None:
            result["description"] = self.description

        return result


@dataclass(frozen=True, slots=True)
class GenreResolution:
    """Result of looking up one raw genre value in the catalog."""

    raw: str
    canonical: str | None
    family: str | None
    match_type: GenreMatchType
    confidence: int

    def __post_init__(self) -> None:
        raw = _clean_text(self.raw, "raw")
        canonical = _clean_optional_text(self.canonical)
        family = _clean_optional_text(self.family)

        if not 0 <= self.confidence <= 100:
            raise ValueError("confidence must be between 0 and 100")

        if self.match_type is GenreMatchType.UNKNOWN:
            if canonical is not None:
                raise ValueError(
                    "Unknown genre resolutions cannot have a canonical genre"
                )
        elif canonical is None:
            raise ValueError(
                "Canonical and alias resolutions require a canonical genre"
            )

        object.__setattr__(self, "raw", raw)
        object.__setattr__(self, "canonical", canonical)
        object.__setattr__(self, "family", family)

    @property
    def matched(self) -> bool:
        """Return True when the raw value matched a catalog entry."""

        return self.match_type is not GenreMatchType.UNKNOWN

    @property
    def changed(self) -> bool:
        """Return True when normalization changes the raw spelling."""

        return (
            self.canonical is not None
            and self.raw != self.canonical
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""

        return {
            "raw": self.raw,
            "canonical": self.canonical,
            "family": self.family,
            "match_type": self.match_type.value,
            "confidence": self.confidence,
            "matched": self.matched,
            "changed": self.changed,
        }


# Temporary backward-compatible name.
#
# Older scripts currently import TrackGenreInfo from the genre subsystem.
# Keeping this alias allows those scripts to continue working while new code
# imports MediaItem from engine.media directly.
TrackGenreInfo = MediaItem


@dataclass(frozen=True, slots=True)
class NormalizationDecision:
    """The analyzer's decision for one audio file.

    This object describes what should happen. It does not modify the file.
    """

    track: MediaItem
    action: GenreAction
    before: tuple[str, ...]
    after: tuple[str, ...]
    confidence: int
    reason: str
    resolutions: tuple[GenreResolution, ...] = ()

    def __post_init__(self) -> None:
        before = _clean_genres(self.before)
        after = _clean_genres(self.after)
        reason = _clean_text(self.reason, "reason")

        if not 0 <= self.confidence <= 100:
            raise ValueError("confidence must be between 0 and 100")

        if before != self.track.genres:
            raise ValueError(
                "Decision 'before' genres must match the track genres"
            )

        if self.action is GenreAction.NORMALIZE:
            if before == after:
                raise ValueError(
                    "A normalize decision must change the genre values"
                )

            if not after:
                raise ValueError(
                    "A normalize decision cannot remove every genre"
                )

        if self.action is GenreAction.KEEP and before != after:
            raise ValueError(
                "A keep decision cannot change the genre values"
            )

        object.__setattr__(self, "before", before)
        object.__setattr__(self, "after", after)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(
            self,
            "resolutions",
            tuple(self.resolutions),
        )

    @property
    def changes_file(self) -> bool:
        """Return True when this decision requires a metadata update."""

        return (
            self.action is GenreAction.NORMALIZE
            and self.before != self.after
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""

        return {
            "track": self.track.to_dict(),
            "action": self.action.value,
            "before": list(self.before),
            "after": list(self.after),
            "confidence": self.confidence,
            "reason": self.reason,
            "changes_file": self.changes_file,
            "resolutions": [
                resolution.to_dict()
                for resolution in self.resolutions
            ],
        }


@dataclass(frozen=True, slots=True)
class GenreChange:
    """One successfully applied metadata change."""

    path: Path
    before: tuple[str, ...]
    after: tuple[str, ...]
    changed_at: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )

    def __post_init__(self) -> None:
        path = Path(self.path).expanduser()
        before = _clean_genres(self.before)
        after = _clean_genres(self.after)

        if before == after:
            raise ValueError(
                "A GenreChange must contain different before and after values"
            )

        changed_at = self.changed_at

        if changed_at.tzinfo is None:
            changed_at = changed_at.replace(tzinfo=UTC)
        else:
            changed_at = changed_at.astimezone(UTC)

        object.__setattr__(self, "path", path)
        object.__setattr__(self, "before", before)
        object.__setattr__(self, "after", after)
        object.__setattr__(self, "changed_at", changed_at)

    def reversed(self) -> GenreChange:
        """Return the inverse change for rollback operations."""

        return GenreChange(
            path=self.path,
            before=self.after,
            after=self.before,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""

        return {
            "path": str(self.path),
            "before": list(self.before),
            "after": list(self.after),
            "changed_at": self.changed_at.isoformat(),
        }

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
    ) -> GenreChange:
        """Create a change from transaction-log data."""

        return cls(
            path=Path(str(data["path"])),
            before=tuple(str(value) for value in data["before"]),
            after=tuple(str(value) for value in data["after"]),
            changed_at=datetime.fromisoformat(
                str(data["changed_at"])
            ),
        )


@dataclass(frozen=True, slots=True)
class GenreTransaction:
    """A collection of changes made during one apply operation."""

    transaction_id: str
    library_root: Path
    changes: tuple[GenreChange, ...]
    status: TransactionStatus = TransactionStatus.PREPARED
    created_at: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )
    completed_at: datetime | None = None
    errors: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        transaction_id = _clean_text(
            self.transaction_id,
            "transaction_id",
        )
        library_root = Path(self.library_root).expanduser()
        changes = tuple(self.changes)
        errors = tuple(
            _clean_text(error, "error")
            for error in self.errors
        )

        created_at = self.created_at

        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        else:
            created_at = created_at.astimezone(UTC)

        completed_at = self.completed_at

        if completed_at is not None:
            if completed_at.tzinfo is None:
                completed_at = completed_at.replace(tzinfo=UTC)
            else:
                completed_at = completed_at.astimezone(UTC)

        object.__setattr__(
            self,
            "transaction_id",
            transaction_id,
        )
        object.__setattr__(
            self,
            "library_root",
            library_root,
        )
        object.__setattr__(self, "changes", changes)
        object.__setattr__(self, "errors", errors)
        object.__setattr__(self, "created_at", created_at)
        object.__setattr__(self, "completed_at", completed_at)

    @property
    def change_count(self) -> int:
        """Return the number of recorded file changes."""

        return len(self.changes)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable transaction record."""

        return {
            "transaction_id": self.transaction_id,
            "library_root": str(self.library_root),
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat()
                if self.completed_at is not None
                else None
            ),
            "change_count": self.change_count,
            "errors": list(self.errors),
            "changes": [
                change.to_dict()
                for change in self.changes
            ],
        }

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
    ) -> GenreTransaction:
        """Create a transaction from a JSON-compatible mapping."""

        completed_value = data.get("completed_at")

        return cls(
            transaction_id=str(data["transaction_id"]),
            library_root=Path(str(data["library_root"])),
            status=TransactionStatus(str(data["status"])),
            created_at=datetime.fromisoformat(
                str(data["created_at"])
            ),
            completed_at=(
                datetime.fromisoformat(str(completed_value))
                if completed_value
                else None
            ),
            errors=tuple(
                str(error)
                for error in data.get("errors", [])
            ),
            changes=tuple(
                GenreChange.from_dict(change)
                for change in data.get("changes", [])
            ),
        )
