"""Media repositories.

Repositories provide MediaItem objects from various sources while hiding the
details of discovery and metadata reading.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path

from .discovery import FilesystemDiscovery
from .models import MediaItem
from .reader import MutagenMediaReader


class FilesystemRepository(Iterable[MediaItem]):
    """Repository backed by a local filesystem."""

    def __init__(
        self,
        root: str | Path,
        *,
        discovery: FilesystemDiscovery | None = None,
        reader: MutagenMediaReader | None = None,
    ):
        self.root = Path(root).expanduser()

        self.discovery = (
            discovery
            if discovery is not None
            else FilesystemDiscovery(self.root)
        )

        self.reader = (
            reader
            if reader is not None
            else MutagenMediaReader()
        )

    def __iter__(self) -> Iterator[MediaItem]:
        for path in self.discovery:
            yield self.reader.read(path)

    def paths(self):
        """Yield discovered file paths."""
        yield from self.discovery

    @property
    def stats(self):
        """Discovery statistics."""
        return self.discovery.stats

    def count(self) -> int:
        """Return number of discovered media files."""
        return self.discovery.count()
