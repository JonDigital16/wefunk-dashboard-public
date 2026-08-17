"""Genre normalization analysis.

This module contains pure decision logic. It does not discover files, read
metadata, write tags, or generate reports.
"""

from __future__ import annotations

from engine.media import MediaItem

from .catalog import GenreCatalog
from .compound import CompoundGenreParser
from .models import (
    GenreAction,
    GenreResolution,
    NormalizationDecision,
)


class GenreAnalyzer:
    """Determine whether a media item's genres require normalization."""

    def __init__(self, catalog: GenreCatalog):
        if not isinstance(catalog, GenreCatalog):
            raise TypeError("catalog must be a GenreCatalog")

        self.catalog = catalog
        self.compound_parser = CompoundGenreParser(catalog)

    def analyze(self, item: MediaItem) -> NormalizationDecision:
        """Analyze one media item and return a normalization decision."""

        if not isinstance(item, MediaItem):
            raise TypeError("item must be a MediaItem")

        before = item.genres

        if not item.has_genres:
            return NormalizationDecision(
                track=item,
                action=GenreAction.SKIP,
                before=before,
                after=before,
                confidence=100,
                reason="No genre values present",
                resolutions=(),
            )

        resolutions: list[GenreResolution] = []
        normalized: list[str] = []
        unknown_values: list[str] = []
        compound_values: list[str] = []

        for raw_genre in before:
            # Always try the complete value first. This protects approved
            # aliases containing slashes, such as:
            #
            #     Rap/Hip Hop -> Hip-Hop
            resolution = self.catalog.resolve(raw_genre)

            if resolution.matched and resolution.canonical is not None:
                resolutions.append(resolution)
                normalized.append(resolution.canonical)
                continue

            # Only attempt compound parsing after complete-value catalog
            # resolution has failed.
            compound = self.compound_parser.parse(raw_genre)

            if compound.matched:
                compound_values.append(raw_genre)

                for component in compound.components:
                    component_resolution = self.catalog.resolve(component)
                    resolutions.append(component_resolution)

                normalized.extend(compound.canonical)
                continue

            # Preserve unknown and ambiguous values exactly as they appeared.
            resolutions.append(resolution)
            normalized.append(raw_genre)
            unknown_values.append(raw_genre)

        after = self._deduplicate(normalized)

        alias_resolutions = tuple(
            resolution
            for resolution in resolutions
            if resolution.changed
        )

        if unknown_values:
            return NormalizationDecision(
                track=item,
                action=GenreAction.MANUAL_REVIEW,
                before=before,
                after=after,
                confidence=50,
                reason=(
                    "Unknown genre values: "
                    + ", ".join(unknown_values)
                ),
                resolutions=tuple(resolutions),
            )

        if compound_values:
            return NormalizationDecision(
                track=item,
                action=GenreAction.NORMALIZE,
                before=before,
                after=after,
                confidence=100,
                reason=(
                    "Approved compound genre normalization: "
                    + " | ".join(compound_values)
                ),
                resolutions=tuple(resolutions),
            )

        if alias_resolutions or before != after:
            return NormalizationDecision(
                track=item,
                action=GenreAction.NORMALIZE,
                before=before,
                after=after,
                confidence=100,
                reason="Approved alias normalization",
                resolutions=tuple(resolutions),
            )

        return NormalizationDecision(
            track=item,
            action=GenreAction.KEEP,
            before=before,
            after=after,
            confidence=100,
            reason="Genre values are already canonical",
            resolutions=tuple(resolutions),
        )

    @staticmethod
    def _deduplicate(values: list[str]) -> tuple[str, ...]:
        """Remove duplicate values while preserving their original order."""

        result: list[str] = []
        seen: set[str] = set()

        for value in values:
            comparison_key = value.casefold()

            if comparison_key in seen:
                continue

            seen.add(comparison_key)
            result.append(value)

        return tuple(result)
