"""Rollback completed genre transactions."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from .models import (
    GenreChange,
    GenreTransaction,
    TransactionStatus,
)
from .updater import (
    GenreMetadataWriter,
    GenreTransactionUpdater,
    GenreUpdateError,
)


class GenreTransactionRollback:
    """Restore original genres from a transaction execution log."""

    def __init__(
        self,
        writer: GenreMetadataWriter | None = None,
    ):
        self.writer = writer or GenreMetadataWriter()

    def rollback(
        self,
        transaction: GenreTransaction,
        rollback_log: Path,
    ) -> GenreTransaction:
        """Rollback completed changes in reverse order."""

        if transaction.status not in {
            TransactionStatus.COMPLETED,
            TransactionStatus.PARTIAL,
        }:
            raise GenreUpdateError(
                "Only completed or partial transactions "
                "may be rolled back"
            )

        restored: list[GenreChange] = []
        errors: list[str] = []

        for index, change in enumerate(
            reversed(transaction.changes),
            start=1,
        ):
            try:
                self.writer.verify(
                    change.path,
                    change.after,
                )
                self.writer.write(
                    change.path,
                    change.before,
                )
                self.writer.verify(
                    change.path,
                    change.before,
                )

                restored.append(change.reversed())

                print(
                    f"[{index:,}/{transaction.change_count:,}] "
                    f"Restored: {change.path}"
                )

            except Exception as exc:
                errors.append(
                    f"{change.path}: "
                    f"{type(exc).__name__}: {exc}"
                )

                failed = replace(
                    transaction,
                    changes=tuple(restored),
                    status=TransactionStatus.FAILED,
                    completed_at=datetime.now(UTC),
                    errors=tuple(errors),
                )

                GenreTransactionUpdater.write_transaction(
                    rollback_log,
                    failed,
                )

                raise GenreUpdateError(errors[-1]) from exc

        result = replace(
            transaction,
            changes=tuple(restored),
            status=TransactionStatus.ROLLED_BACK,
            completed_at=datetime.now(UTC),
            errors=(),
        )

        GenreTransactionUpdater.write_transaction(
            rollback_log,
            result,
        )

        return result
