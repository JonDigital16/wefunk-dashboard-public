"""Safe parsing of compound genre values.

Parsing is hierarchical:

1. Split comma-separated components.
2. Resolve every complete component through the catalog.
3. Only when a complete component is unresolved, consider slash splitting.
4. Require every resulting component to resolve.
5. Require at least two distinct canonical genres.

This preserves approved aliases such as:

    Rap/Hip Hop -> Hip-Hop

This module never modifies media files.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from engine.genres.catalog import GenreCatalog


COMMA_SEPARATOR_PATTERN = re.compile(r"\s*,\s*")
SLASH_SEPARATOR_PATTERN = re.compile(r"\s*/\s*")


@dataclass(frozen=True, slots=True)
class CompoundGenreResult:
    """Result of attempting to parse one compound genre value."""

    raw: str
    matched: bool
    components: tuple[str, ...]
    canonical: tuple[str, ...]
    reason: str

    @classmethod
    def no_match(
        cls,
        raw: str,
        *,
        components: tuple[str, ...] = (),
        reason: str,
    ) -> "CompoundGenreResult":
        return cls(
            raw=raw,
            matched=False,
            components=components,
            canonical=(),
            reason=reason,
        )


class CompoundGenreParser:
    """Resolve safe compound genre strings through a GenreCatalog."""

    def __init__(self, catalog: GenreCatalog) -> None:
        self.catalog = catalog

    def parse(self, raw: str) -> CompoundGenreResult:
        """Attempt to parse and resolve a compound genre value."""

        cleaned = " ".join(str(raw).split())

        if not cleaned:
            return CompoundGenreResult.no_match(
                raw=cleaned,
                reason="Genre value is empty",
            )

        has_comma = bool(COMMA_SEPARATOR_PATTERN.search(cleaned))
        has_slash = bool(SLASH_SEPARATOR_PATTERN.search(cleaned))

        if not has_comma and not has_slash:
            return CompoundGenreResult.no_match(
                raw=cleaned,
                reason="No approved compound separator present",
            )

        # Commas establish the first-level component boundaries.
        if has_comma:
            primary_components = tuple(
                component.strip()
                for component in COMMA_SEPARATOR_PATTERN.split(cleaned)
                if component.strip()
            )
        else:
            primary_components = (cleaned,)

        resolved_components: list[str] = []
        canonical: list[str] = []
        unknown: list[str] = []

        for primary_component in primary_components:
            # Protect complete aliases such as Rap/Hip Hop.
            primary_resolution = self.catalog.resolve(primary_component)

            if (
                primary_resolution.matched
                and primary_resolution.canonical is not None
            ):
                resolved_components.append(primary_component)
                self._append_unique(
                    canonical,
                    primary_resolution.canonical,
                )
                continue

            # Only unresolved primary components may be split on slashes.
            if not SLASH_SEPARATOR_PATTERN.search(primary_component):
                resolved_components.append(primary_component)
                unknown.append(primary_component)
                continue

            slash_components = tuple(
                component.strip()
                for component in SLASH_SEPARATOR_PATTERN.split(
                    primary_component
                )
                if component.strip()
            )

            if len(slash_components) < 2:
                resolved_components.append(primary_component)
                unknown.append(primary_component)
                continue

            slash_unknown: list[str] = []
            slash_canonical: list[str] = []

            for slash_component in slash_components:
                resolution = self.catalog.resolve(slash_component)

                if (
                    not resolution.matched
                    or resolution.canonical is None
                ):
                    slash_unknown.append(slash_component)
                    continue

                slash_canonical.append(resolution.canonical)

            if slash_unknown:
                resolved_components.extend(slash_components)
                unknown.extend(slash_unknown)
                continue

            resolved_components.extend(slash_components)

            for value in slash_canonical:
                self._append_unique(canonical, value)

        components = tuple(resolved_components)

        if unknown:
            return CompoundGenreResult.no_match(
                raw=cleaned,
                components=components,
                reason=(
                    "Unresolved compound components: "
                    + ", ".join(unknown)
                ),
            )

        if len(canonical) < 2:
            return CompoundGenreResult.no_match(
                raw=cleaned,
                components=components,
                reason=(
                    "Compound value did not produce at least two "
                    "distinct canonical genres"
                ),
            )

        return CompoundGenreResult(
            raw=cleaned,
            matched=True,
            components=components,
            canonical=tuple(canonical),
            reason="All compound components resolved through the catalog",
        )

    @staticmethod
    def _append_unique(values: list[str], value: str) -> None:
        """Append a value unless it already exists case-insensitively."""

        if any(
            existing.casefold() == value.casefold()
            for existing in values
        ):
            return

        values.append(value)
