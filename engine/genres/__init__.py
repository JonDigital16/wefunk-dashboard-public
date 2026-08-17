"""WEFUNK genre normalization subsystem."""

from engine.media import MediaItem
from .analyzer import GenreAnalyzer

from .catalog import (
    DEFAULT_CATALOG_PATH,
    GenreCatalog,
    GenreCatalogError,
    GenreCatalogFileError,
    GenreCatalogValidationError,
    normalize_genre_lookup,
)
from .preview import (
    GenrePreview,
    GenrePreviewBuilder,
    PreviewError,
)

from .updater import (
    GenreApplyResult,
    GenreMetadataWriter,
    GenreTransactionUpdater,
    GenreUpdateError,
)
from .rollback import GenreTransactionRollback

from .models import (
    Genre,
    GenreAction,
    GenreChange,
    GenreMatchType,
    GenreResolution,
    GenreTransaction,
    NormalizationDecision,
    TrackGenreInfo,
    TransactionStatus,
)

__all__ = [
    "DEFAULT_CATALOG_PATH",
    "Genre",
    "GenreAction",
    "GenreCatalog",
    "GenreCatalogError",
    "GenreCatalogFileError",
    "GenreCatalogValidationError",
    "GenreChange",
    "GenreAnalyzer",
    "GenreMatchType",
    "GenreResolution",
    "GenreTransaction",
    "GenreUpdateError",
    "GenreTransactionRollback",
    "GenreTransactionUpdater",
    "GenreApplyResult",
    "GenreMetadataWriter",
    "MediaItem",
    "NormalizationDecision",
    "PreviewError",
    "GenrePreviewBuilder",
    "GenrePreview",
    "TrackGenreInfo",
    "TransactionStatus",
    "normalize_genre_lookup",
]
