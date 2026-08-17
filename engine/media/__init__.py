"""Shared media models and services."""

from .discovery import DiscoveryStats, FilesystemDiscovery
from .models import MediaItem
from .reader import (
    MediaFileNotFoundError,
    MediaReaderError,
    MetadataReadError,
    MutagenMediaReader,
    UnsupportedMediaError,
)
from .repository import FilesystemRepository

__all__ = [
    "DiscoveryStats",
    "FilesystemDiscovery",
    "FilesystemRepository",
    "MediaFileNotFoundError",
    "MediaItem",
    "MediaReaderError",
    "MetadataReadError",
    "MutagenMediaReader",
    "UnsupportedMediaError",
]
