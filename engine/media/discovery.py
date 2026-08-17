"""Filesystem discovery for the WEFUNK media engine.

This module discovers candidate media files only. It does not read metadata
or inspect file contents.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Iterator


DEFAULT_MEDIA_EXTENSIONS = frozenset({
    ".mp3",
    ".flac",
    ".m4a",
    ".aac",
    ".ogg",
    ".opus",
    ".wav",
})


@dataclass(slots=True)
class DiscoveryStats:
    directories_scanned: int = 0
    files_seen: int = 0
    files_discovered: int = 0
    files_skipped: int = 0
    hidden_skipped: int = 0
    extension_skipped: int = 0
    symlink_skipped: int = 0
    elapsed_seconds: float = 0.0


class FilesystemDiscovery:
    """Discover supported media files beneath a root directory."""

    def __init__(
        self,
        root: str | Path,
        *,
        extensions=DEFAULT_MEDIA_EXTENSIONS,
        follow_symlinks: bool = False,
        include_hidden: bool = False,
        sort_entries: bool = True,
    ):
        self.root = Path(root).expanduser()

        if not self.root.exists():
            raise FileNotFoundError(
                f"Media root does not exist: {self.root}"
            )

        if not self.root.is_dir():
            raise NotADirectoryError(
                f"Media root is not a directory: {self.root}"
            )

        self.extensions = frozenset(
            ext.casefold() if ext.startswith(".")
            else f".{ext.casefold()}"
            for ext in extensions
        )

        self.follow_symlinks = follow_symlinks
        self.include_hidden = include_hidden
        self.sort_entries = sort_entries
        self._stats = DiscoveryStats()

    @property
    def stats(self) -> DiscoveryStats:
        return self._stats

    def discover(self) -> Iterator[Path]:
        """Yield supported media file paths."""

        self._stats = DiscoveryStats()
        started = perf_counter()

        try:
            for directory, dirnames, filenames in os.walk(
                self.root,
                followlinks=self.follow_symlinks,
            ):
                self._stats.directories_scanned += 1

                if not self.include_hidden:
                    hidden_directories = [
                        name for name in dirnames
                        if name.startswith(".")
                    ]

                    self._stats.hidden_skipped += len(hidden_directories)
                    self._stats.files_skipped += len(hidden_directories)

                    dirnames[:] = [
                        name for name in dirnames
                        if not name.startswith(".")
                    ]

                if self.sort_entries:
                    dirnames.sort(key=str.casefold)
                    filenames.sort(key=str.casefold)

                directory_path = Path(directory)

                for filename in filenames:
                    self._stats.files_seen += 1
                    path = directory_path / filename

                    if not self.include_hidden and filename.startswith("."):
                        self._stats.hidden_skipped += 1
                        self._stats.files_skipped += 1
                        continue

                    if path.is_symlink() and not self.follow_symlinks:
                        self._stats.symlink_skipped += 1
                        self._stats.files_skipped += 1
                        continue

                    if path.suffix.casefold() not in self.extensions:
                        self._stats.extension_skipped += 1
                        self._stats.files_skipped += 1
                        continue

                    self._stats.files_discovered += 1
                    yield path
        finally:
            self._stats.elapsed_seconds = perf_counter() - started

    def count(self) -> int:
        """Return the number of discovered media files."""

        return sum(1 for _ in self.discover())

    def __iter__(self) -> Iterator[Path]:
        return self.discover()
