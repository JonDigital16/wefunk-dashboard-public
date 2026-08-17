"""Guarded and restart-safe genre metadata updater.

Every file is:

1. Revalidated before writing.
2. Written using Mutagen.
3. Re-read and verified after writing.
4. Recorded immediately in an atomic execution log.

An interrupted transaction can safely resume from its execution log.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from mutagen import File as MutagenFile

from engine.media import MutagenMediaReader

from .models import (
    GenreChange,
    GenreTransaction,
    TransactionStatus,
)


class GenreUpdateError(Exception):
    """Raised when a genre update cannot be completed safely."""


@dataclass(frozen=True, slots=True)
class GenreApplyResult:
    """Summary of one transaction execution or resumed execution."""

    transaction: GenreTransaction
    planned_count: int
    already_completed_count: int
    updated_count: int
    elapsed_seconds: float

    @property
    def remaining_count(self) -> int:
        """Return the number of planned files not completed."""

        return max(
            self.planned_count
            - self.already_completed_count
            - self.updated_count,
            0,
        )

    @property
    def resumed(self) -> bool:
        """Return True when prior completed work was reused."""

        return self.already_completed_count > 0


class GenreMetadataWriter:
    """Write and verify genre metadata using Mutagen."""

    def __init__(
        self,
        reader: MutagenMediaReader | None = None,
    ):
        self.reader = reader or MutagenMediaReader()

    def write(
        self,
        path: Path,
        genres: tuple[str, ...],
    ) -> None:
        """Write genre values to one supported audio file."""

        path = Path(path).expanduser()

        audio = MutagenFile(path, easy=True)

        if audio is None:
            raise GenreUpdateError(
                f"Mutagen could not open: {path}"
            )

        if audio.tags is None:
            audio.add_tags()

        audio["genre"] = list(genres)
        audio.save()

    def read_genres(
        self,
        path: Path,
    ) -> tuple[str, ...]:
        """Read the current genres from one file."""

        return self.reader.read(path).genres

    def verify(
        self,
        path: Path,
        expected: tuple[str, ...],
    ) -> None:
        """Confirm the file contains the expected genres."""

        actual = self.read_genres(path)

        if actual != expected:
            raise GenreUpdateError(
                f"Genre verification failed for {path}: "
                f"expected {expected}, found {actual}"
            )


class GenreTransactionUpdater:
    """Apply or resume a prepared genre transaction safely."""

    def __init__(
        self,
        writer: GenreMetadataWriter | None = None,
    ):
        self.writer = writer or GenreMetadataWriter()

    def apply(
        self,
        transaction: GenreTransaction,
        execution_log: Path,
    ) -> GenreApplyResult:
        """Apply or resume a prepared transaction.

        The supplied transaction must be the complete prepared manifest.
        The execution log records only successfully completed changes.
        """

        if transaction.status is not TransactionStatus.PREPARED:
            raise GenreUpdateError(
                "Only prepared transactions may be applied"
            )

        execution_log = Path(execution_log).expanduser()
        started = perf_counter()

        completed = self._load_resume_state(
            transaction=transaction,
            execution_log=execution_log,
        )

        already_completed_count = len(completed)
        completed_paths = {
            change.path
            for change in completed
        }

        remaining = [
            change
            for change in transaction.changes
            if change.path not in completed_paths
        ]

        running = replace(
            transaction,
            changes=tuple(completed),
            status=TransactionStatus.PARTIAL,
            completed_at=None,
            errors=(),
        )
        self.write_transaction(execution_log, running)

        if completed:
            print(
                f"Resuming with {len(completed):,} "
                "previously completed file(s)."
            )
            print(
                f"Remaining files: {len(remaining):,}"
            )
            print()

        updated_count = 0

        for planned in remaining:
            overall_index = len(completed) + 1
            path = planned.path

            try:
                self.writer.verify(path, planned.before)
                self.writer.write(path, planned.after)
                self.writer.verify(path, planned.after)

                completed_change = GenreChange(
                    path=path,
                    before=planned.before,
                    after=planned.after,
                )

                completed.append(completed_change)
                updated_count += 1

                running = replace(
                    transaction,
                    changes=tuple(completed),
                    status=TransactionStatus.PARTIAL,
                    completed_at=None,
                    errors=(),
                )

                self.write_transaction(
                    execution_log,
                    running,
                )

                print(
                    f"[{overall_index:,}/"
                    f"{transaction.change_count:,}] "
                    f"Updated: {path}"
                )

            except Exception as exc:
                error = (
                    f"{path}: {type(exc).__name__}: {exc}"
                )

                restore_errors: list[str] = []

                try:
                    current = self.writer.read_genres(path)

                    if current != planned.before:
                        self.writer.write(
                            path,
                            planned.before,
                        )
                        self.writer.verify(
                            path,
                            planned.before,
                        )

                except Exception as restore_exc:
                    restore_errors.append(
                        f"{path}: automatic restore failed: "
                        f"{type(restore_exc).__name__}: "
                        f"{restore_exc}"
                    )

                errors = (error, *restore_errors)

                failed = replace(
                    transaction,
                    changes=tuple(completed),
                    status=(
                        TransactionStatus.PARTIAL
                        if completed
                        else TransactionStatus.FAILED
                    ),
                    completed_at=datetime.now(UTC),
                    errors=errors,
                )

                self.write_transaction(
                    execution_log,
                    failed,
                )

                raise GenreUpdateError(
                    "\n".join(errors)
                ) from exc

        completed_transaction = replace(
            transaction,
            changes=tuple(completed),
            status=TransactionStatus.COMPLETED,
            completed_at=datetime.now(UTC),
            errors=(),
        )

        self.write_transaction(
            execution_log,
            completed_transaction,
        )

        return GenreApplyResult(
            transaction=completed_transaction,
            planned_count=transaction.change_count,
            already_completed_count=already_completed_count,
            updated_count=updated_count,
            elapsed_seconds=perf_counter() - started,
        )

    def _load_resume_state(
        self,
        transaction: GenreTransaction,
        execution_log: Path,
    ) -> list[GenreChange]:
        """Load and validate previously completed changes."""

        if not execution_log.exists():
            return []

        previous = self.load_transaction(execution_log)

        if previous.transaction_id != transaction.transaction_id:
            raise GenreUpdateError(
                "Execution log transaction ID does not match "
                "the prepared manifest"
            )

        if (
            previous.library_root.resolve()
            != transaction.library_root.resolve()
        ):
            raise GenreUpdateError(
                "Execution log library root does not match "
                "the prepared manifest"
            )

        if previous.status is TransactionStatus.ROLLED_BACK:
            raise GenreUpdateError(
                "This execution log represents a rolled-back "
                "transaction and cannot be resumed"
            )

        planned_by_path = {
            change.path: change
            for change in transaction.changes
        }

        completed: list[GenreChange] = []
        seen_paths: set[Path] = set()

        for recorded in previous.changes:
            if recorded.path in seen_paths:
                raise GenreUpdateError(
                    "Execution log contains a duplicate path: "
                    f"{recorded.path}"
                )

            seen_paths.add(recorded.path)

            planned = planned_by_path.get(recorded.path)

            if planned is None:
                raise GenreUpdateError(
                    "Execution log contains a file not present "
                    f"in the prepared manifest: {recorded.path}"
                )

            if (
                recorded.before != planned.before
                or recorded.after != planned.after
            ):
                raise GenreUpdateError(
                    "Execution log change does not match the "
                    f"prepared manifest: {recorded.path}"
                )

            current = self.writer.read_genres(recorded.path)

            if current != planned.after:
                raise GenreUpdateError(
                    "Previously completed file no longer contains "
                    f"its expected normalized genres: {recorded.path}. "
                    f"Expected {planned.after}, found {current}"
                )

            completed.append(recorded)

        if (
            previous.status is TransactionStatus.COMPLETED
            and len(completed) != transaction.change_count
        ):
            raise GenreUpdateError(
                "Execution log is marked completed but does not "
                "contain every planned change"
            )

        return completed

    @staticmethod
    def load_transaction(
        path: Path,
    ) -> GenreTransaction:
        """Load a transaction JSON file."""

        path = Path(path).expanduser()

        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)

        return GenreTransaction.from_dict(data)

    @staticmethod
    def write_transaction(
        path: Path,
        transaction: GenreTransaction,
    ) -> None:
        """Atomically replace a transaction log on disk."""

        path = Path(path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)

        temporary = path.with_suffix(
            path.suffix + ".tmp"
        )

        with temporary.open(
            "w",
            encoding="utf-8",
        ) as handle:
            json.dump(
                transaction.to_dict(),
                handle,
                indent=2,
                ensure_ascii=False,
            )
            handle.write("\n")

        temporary.replace(path)
