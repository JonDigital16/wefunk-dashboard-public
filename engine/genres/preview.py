"""Read-only preparation of genre normalization transactions.

This module validates proposed genre changes against current file metadata and
creates a prepared transaction manifest. It never modifies media files.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from engine.media import MediaReaderError, MutagenMediaReader

from .models import (
    GenreChange,
    GenreTransaction,
    TransactionStatus,
)


REPORT_SEPARATOR = " | "


@dataclass(frozen=True, slots=True)
class PreviewError:
    """One file that could not safely be prepared."""

    path: Path
    error: str
    expected_before: tuple[str, ...] = ()
    current_genres: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, str]:
        return {
            "path": str(self.path),
            "error": self.error,
            "expected_before": REPORT_SEPARATOR.join(
                self.expected_before
            ),
            "current_genres": REPORT_SEPARATOR.join(
                self.current_genres
            ),
        }


@dataclass(frozen=True, slots=True)
class GenrePreview:
    """Result of validating proposed normalization changes."""

    transaction: GenreTransaction | None
    source_rows: int
    errors: tuple[PreviewError, ...]

    @property
    def prepared_count(self) -> int:
        if self.transaction is None:
            return 0

        return self.transaction.change_count

    @property
    def valid(self) -> bool:
        return (
            self.transaction is not None
            and not self.errors
            and self.prepared_count == self.source_rows
        )


class GenrePreviewBuilder:
    """Build a validated, read-only genre transaction preview."""

    def __init__(
        self,
        reader: MutagenMediaReader | None = None,
    ):
        self.reader = (
            reader
            if reader is not None
            else MutagenMediaReader()
        )

    def build_from_audit_csv(
        self,
        normalize_csv: Path,
        library_root: Path,
    ) -> GenrePreview:
        """Validate audit rows and build a prepared transaction."""

        normalize_csv = Path(normalize_csv).expanduser()
        library_root = Path(library_root).expanduser()

        if not normalize_csv.exists():
            raise FileNotFoundError(
                f"Normalize report not found: {normalize_csv}"
            )

        rows = self._load_rows(normalize_csv)
        changes: list[GenreChange] = []
        errors: list[PreviewError] = []
        seen_paths: set[Path] = set()

        for row in rows:
            raw_path = (row.get("path") or "").strip()

            if not raw_path:
                errors.append(
                    PreviewError(
                        path=Path("(missing path)"),
                        error="Audit row has no file path",
                    )
                )
                continue

            path = Path(raw_path).expanduser()

            before = self._split_values(
                row.get("before", "")
            )
            after = self._split_values(
                row.get("after", "")
            )

            if path in seen_paths:
                errors.append(
                    PreviewError(
                        path=path,
                        error="Duplicate file path in normalize report",
                        expected_before=before,
                    )
                )
                continue

            seen_paths.add(path)

            if not before:
                errors.append(
                    PreviewError(
                        path=path,
                        error="Normalize row has no original genres",
                    )
                )
                continue

            if not after:
                errors.append(
                    PreviewError(
                        path=path,
                        error="Normalize row has no resulting genres",
                        expected_before=before,
                    )
                )
                continue

            if before == after:
                errors.append(
                    PreviewError(
                        path=path,
                        error=(
                            "Normalize row does not contain an "
                            "actual genre change"
                        ),
                        expected_before=before,
                        current_genres=before,
                    )
                )
                continue

            try:
                current_item = self.reader.read(path)
            except MediaReaderError as exc:
                errors.append(
                    PreviewError(
                        path=path,
                        error=str(exc),
                        expected_before=before,
                    )
                )
                continue
            except Exception as exc:
                errors.append(
                    PreviewError(
                        path=path,
                        error=f"{type(exc).__name__}: {exc}",
                        expected_before=before,
                    )
                )
                continue

            if current_item.genres != before:
                errors.append(
                    PreviewError(
                        path=path,
                        error=(
                            "Current genres no longer match the "
                            "latest audit"
                        ),
                        expected_before=before,
                        current_genres=current_item.genres,
                    )
                )
                continue

            try:
                path.relative_to(library_root)
            except ValueError:
                errors.append(
                    PreviewError(
                        path=path,
                        error=(
                            "File is outside the configured "
                            "music library root"
                        ),
                        expected_before=before,
                        current_genres=current_item.genres,
                    )
                )
                continue

            changes.append(
                GenreChange(
                    path=path,
                    before=before,
                    after=after,
                )
            )

        transaction: GenreTransaction | None = None

        if not errors and len(changes) == len(rows):
            transaction = GenreTransaction(
                transaction_id=self._transaction_id(),
                library_root=library_root,
                changes=tuple(changes),
                status=TransactionStatus.PREPARED,
            )

        return GenrePreview(
            transaction=transaction,
            source_rows=len(rows),
            errors=tuple(errors),
        )

    @staticmethod
    def write_transaction(
        path: Path,
        transaction: GenreTransaction,
    ) -> None:
        """Write a prepared transaction manifest as JSON."""

        path = Path(path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)

        with path.open("w", encoding="utf-8") as handle:
            json.dump(
                transaction.to_dict(),
                handle,
                indent=2,
                ensure_ascii=False,
            )
            handle.write("\n")

    @staticmethod
    def write_changes_csv(
        path: Path,
        transaction: GenreTransaction,
    ) -> None:
        """Write a human-readable preview of prepared changes."""

        path = Path(path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)

        with path.open(
            "w",
            encoding="utf-8",
            newline="",
        ) as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "path",
                    "before",
                    "after",
                ],
            )
            writer.writeheader()

            for change in transaction.changes:
                writer.writerow({
                    "path": str(change.path),
                    "before": REPORT_SEPARATOR.join(
                        change.before
                    ),
                    "after": REPORT_SEPARATOR.join(
                        change.after
                    ),
                })

    @staticmethod
    def write_errors_csv(
        path: Path,
        errors: tuple[PreviewError, ...],
    ) -> None:
        """Write preview validation errors."""

        path = Path(path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)

        with path.open(
            "w",
            encoding="utf-8",
            newline="",
        ) as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "path",
                    "error",
                    "expected_before",
                    "current_genres",
                ],
            )
            writer.writeheader()

            for error in errors:
                writer.writerow(error.to_dict())

    @staticmethod
    def _load_rows(
        path: Path,
    ) -> list[dict[str, str]]:
        with path.open(
            encoding="utf-8",
            newline="",
        ) as handle:
            return list(csv.DictReader(handle))

    @staticmethod
    def _split_values(value: str) -> tuple[str, ...]:
        if not value:
            return ()

        return tuple(
            part.strip()
            for part in value.split("|")
            if part.strip()
        )

    @staticmethod
    def _transaction_id() -> str:
        timestamp = datetime.now(UTC).strftime(
            "%Y%m%dT%H%M%SZ"
        )
        suffix = uuid4().hex[:8]

        return f"genre-{timestamp}-{suffix}"
