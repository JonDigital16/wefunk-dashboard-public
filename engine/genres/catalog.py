"""Genre catalog loading, validation, and lookup.

The catalog is the authoritative source for:

- canonical genre names,
- approved aliases,
- genre-family membership.

This module does not scan audio files or modify metadata.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:
    raise RuntimeError(
        "PyYAML is required by the WEFUNK genre catalog"
    ) from exc

from .models import Genre, GenreMatchType, GenreResolution


DEFAULT_CATALOG_PATH = (
    Path(__file__).resolve().parent
    / "data"
    / "catalog.yaml"
)


class GenreCatalogError(Exception):
    """Base exception for genre-catalog failures."""


class GenreCatalogFileError(GenreCatalogError):
    """Raised when the catalog file cannot be loaded."""


class GenreCatalogValidationError(GenreCatalogError):
    """Raised when catalog contents are invalid or ambiguous."""


def normalize_genre_lookup(value: str) -> str:
    """Normalize a genre value for case-insensitive catalog lookup.

    This intentionally performs conservative normalization:

    - strips leading and trailing whitespace,
    - collapses repeated whitespace,
    - applies Unicode-aware case folding.

    Punctuation is preserved so distinct genres are not accidentally merged.
    """

    if not isinstance(value, str):
        raise TypeError("Genre lookup values must be strings")

    return re.sub(r"\s+", " ", value.strip()).casefold()


class GenreCatalog:
    """An immutable, validated collection of canonical genres."""

    __slots__ = (
        "_genres",
        "_canonical_exact",
        "_canonical_lookup",
        "_alias_lookup",
        "_families",
        "_version",
        "_source_path",
    )

    def __init__(
        self,
        genres: Mapping[str, Genre],
        *,
        version: int = 1,
        source_path: Path | None = None,
    ) -> None:
        if not genres:
            raise GenreCatalogValidationError(
                "The genre catalog cannot be empty"
            )

        if version < 1:
            raise GenreCatalogValidationError(
                "Catalog version must be at least 1"
            )

        canonical_exact: dict[str, Genre] = {}
        canonical_lookup: dict[str, Genre] = {}
        alias_lookup: dict[str, Genre] = {}
        families: dict[str, list[Genre]] = defaultdict(list)

        for key, genre in genres.items():
            if not isinstance(genre, Genre):
                raise GenreCatalogValidationError(
                    f"Catalog entry {key!r} is not a Genre object"
                )

            if key != genre.canonical:
                raise GenreCatalogValidationError(
                    f"Catalog key {key!r} does not match canonical "
                    f"name {genre.canonical!r}"
                )

            if genre.canonical in canonical_exact:
                raise GenreCatalogValidationError(
                    f"Duplicate canonical genre: {genre.canonical!r}"
                )

            lookup_key = normalize_genre_lookup(genre.canonical)

            existing_canonical = canonical_lookup.get(lookup_key)

            if (
                existing_canonical is not None
                and existing_canonical.canonical != genre.canonical
            ):
                raise GenreCatalogValidationError(
                    "Canonical genres differ only by case or whitespace: "
                    f"{existing_canonical.canonical!r} and "
                    f"{genre.canonical!r}"
                )

            canonical_exact[genre.canonical] = genre
            canonical_lookup[lookup_key] = genre
            families[genre.family].append(genre)

        for genre in canonical_exact.values():
            for alias in genre.aliases:
                alias_key = normalize_genre_lookup(alias)

                canonical_collision = canonical_lookup.get(alias_key)

                if (
                    canonical_collision is not None
                    and canonical_collision.canonical != genre.canonical
                ):
                    raise GenreCatalogValidationError(
                        f"Alias {alias!r} for {genre.canonical!r} "
                        f"conflicts with canonical genre "
                        f"{canonical_collision.canonical!r}"
                    )

                existing_alias = alias_lookup.get(alias_key)

                if (
                    existing_alias is not None
                    and existing_alias.canonical != genre.canonical
                ):
                    raise GenreCatalogValidationError(
                        f"Alias {alias!r} is assigned to both "
                        f"{existing_alias.canonical!r} and "
                        f"{genre.canonical!r}"
                    )

                # An alias that differs from its own canonical name only by
                # capitalization or whitespace is safe but does not need a
                # separate index entry. The canonical lookup handles it.
                if (
                    canonical_collision is not None
                    and canonical_collision.canonical == genre.canonical
                ):
                    continue

                alias_lookup[alias_key] = genre

        sorted_genres = dict(
            sorted(
                canonical_exact.items(),
                key=lambda item: item[0].casefold(),
            )
        )

        sorted_families = {
            family: tuple(
                sorted(
                    entries,
                    key=lambda item: item.canonical.casefold(),
                )
            )
            for family, entries in sorted(
                families.items(),
                key=lambda item: item[0].casefold(),
            )
        }

        self._genres = sorted_genres
        self._canonical_exact = canonical_exact
        self._canonical_lookup = canonical_lookup
        self._alias_lookup = alias_lookup
        self._families = sorted_families
        self._version = version
        self._source_path = (
            Path(source_path).expanduser()
            if source_path is not None
            else None
        )

    @classmethod
    def load(
        cls,
        path: Path | str = DEFAULT_CATALOG_PATH,
    ) -> GenreCatalog:
        """Load and validate a catalog from YAML."""

        catalog_path = Path(path).expanduser()

        if not catalog_path.exists():
            raise GenreCatalogFileError(
                f"Genre catalog not found: {catalog_path}"
            )

        if not catalog_path.is_file():
            raise GenreCatalogFileError(
                f"Genre catalog path is not a file: {catalog_path}"
            )

        try:
            with catalog_path.open(encoding="utf-8") as handle:
                raw_data = yaml.safe_load(handle)
        except OSError as exc:
            raise GenreCatalogFileError(
                f"Could not read genre catalog: {catalog_path}: {exc}"
            ) from exc
        except yaml.YAMLError as exc:
            raise GenreCatalogFileError(
                f"Invalid YAML in genre catalog {catalog_path}: {exc}"
            ) from exc

        if raw_data is None:
            raise GenreCatalogValidationError(
                f"Genre catalog is empty: {catalog_path}"
            )

        if not isinstance(raw_data, dict):
            raise GenreCatalogValidationError(
                "Catalog root must be a YAML mapping"
            )

        version = raw_data.get("version", 1)

        if not isinstance(version, int):
            raise GenreCatalogValidationError(
                "Catalog version must be an integer"
            )

        raw_genres = raw_data.get("genres")

        if not isinstance(raw_genres, dict):
            raise GenreCatalogValidationError(
                "Catalog must contain a 'genres' mapping"
            )

        genres: dict[str, Genre] = {}

        for canonical, settings in raw_genres.items():
            if not isinstance(canonical, str):
                raise GenreCatalogValidationError(
                    "Canonical genre names must be strings"
                )

            if settings is None:
                settings = {}

            if not isinstance(settings, dict):
                raise GenreCatalogValidationError(
                    f"Settings for {canonical!r} must be a mapping"
                )

            family = settings.get("family")

            if not isinstance(family, str) or not family.strip():
                raise GenreCatalogValidationError(
                    f"Genre {canonical!r} requires a non-empty family"
                )

            raw_aliases = settings.get("aliases", [])

            if raw_aliases is None:
                raw_aliases = []

            if not isinstance(raw_aliases, list):
                raise GenreCatalogValidationError(
                    f"Aliases for {canonical!r} must be a list"
                )

            aliases: list[str] = []

            for alias in raw_aliases:
                if not isinstance(alias, str):
                    raise GenreCatalogValidationError(
                        f"Aliases for {canonical!r} must be strings"
                    )

                aliases.append(alias)

            description = settings.get("description")

            if description is not None and not isinstance(
                description,
                str,
            ):
                raise GenreCatalogValidationError(
                    f"Description for {canonical!r} must be a string"
                )

            try:
                genre = Genre(
                    canonical=canonical,
                    family=family,
                    aliases=tuple(aliases),
                    description=description,
                )
            except (TypeError, ValueError) as exc:
                raise GenreCatalogValidationError(
                    f"Invalid genre {canonical!r}: {exc}"
                ) from exc

            genres[genre.canonical] = genre

        return cls(
            genres,
            version=version,
            source_path=catalog_path,
        )

    @property
    def version(self) -> int:
        """Return the catalog schema version."""

        return self._version

    @property
    def source_path(self) -> Path | None:
        """Return the YAML file used to construct this catalog."""

        return self._source_path

    @property
    def genre_count(self) -> int:
        """Return the number of canonical genres."""

        return len(self._genres)

    @property
    def alias_count(self) -> int:
        """Return the number of distinct indexed aliases."""

        return len(self._alias_lookup)

    @property
    def family_count(self) -> int:
        """Return the number of genre families."""

        return len(self._families)

    @property
    def canonical_names(self) -> tuple[str, ...]:
        """Return every canonical genre name alphabetically."""

        return tuple(self._genres)

    @property
    def family_names(self) -> tuple[str, ...]:
        """Return every family name alphabetically."""

        return tuple(self._families)

    def __len__(self) -> int:
        return self.genre_count

    def __iter__(self) -> Iterator[Genre]:
        return iter(self._genres.values())

    def __contains__(self, value: object) -> bool:
        if not isinstance(value, str):
            return False

        return self.resolve(value).matched

    def get(self, canonical: str) -> Genre | None:
        """Return a genre by canonical name.

        This method permits capitalization and whitespace differences but
        does not resolve unrelated aliases.
        """

        return self._canonical_lookup.get(
            normalize_genre_lookup(canonical)
        )

    def require(self, canonical: str) -> Genre:
        """Return a canonical genre or raise KeyError."""

        genre = self.get(canonical)

        if genre is None:
            raise KeyError(f"Unknown canonical genre: {canonical!r}")

        return genre

    def resolve(self, raw: str) -> GenreResolution:
        """Resolve one raw genre value.

        Exact canonical spellings are classified as canonical matches.
        Approved aliases, capitalization differences, and whitespace
        differences are classified as aliases.
        """

        if not isinstance(raw, str):
            raise TypeError("Raw genre values must be strings")

        cleaned = re.sub(r"\s+", " ", raw.strip())

        if not cleaned:
            raise ValueError("Raw genre values cannot be empty")

        exact_genre = self._canonical_exact.get(cleaned)

        if exact_genre is not None:
            return GenreResolution(
                raw=cleaned,
                canonical=exact_genre.canonical,
                family=exact_genre.family,
                match_type=GenreMatchType.CANONICAL,
                confidence=100,
            )

        lookup_key = normalize_genre_lookup(cleaned)

        alias_genre = self._alias_lookup.get(lookup_key)

        if alias_genre is not None:
            return GenreResolution(
                raw=cleaned,
                canonical=alias_genre.canonical,
                family=alias_genre.family,
                match_type=GenreMatchType.ALIAS,
                confidence=100,
            )

        canonical_variant = self._canonical_lookup.get(lookup_key)

        if canonical_variant is not None:
            return GenreResolution(
                raw=cleaned,
                canonical=canonical_variant.canonical,
                family=canonical_variant.family,
                match_type=GenreMatchType.ALIAS,
                confidence=100,
            )

        return GenreResolution(
            raw=cleaned,
            canonical=None,
            family=None,
            match_type=GenreMatchType.UNKNOWN,
            confidence=0,
        )

    def genres_in_family(self, family: str) -> tuple[Genre, ...]:
        """Return all canonical genres belonging to a family."""

        lookup = normalize_genre_lookup(family)

        for family_name, genres in self._families.items():
            if normalize_genre_lookup(family_name) == lookup:
                return genres

        return ()

    def aliases_for(self, canonical: str) -> tuple[str, ...]:
        """Return all explicit aliases for a canonical genre."""

        return self.require(canonical).aliases

    def family_for(self, value: str) -> str | None:
        """Resolve a canonical name or alias and return its family."""

        return self.resolve(value).family

    def is_canonical(self, value: str) -> bool:
        """Return True only for an exact canonical spelling."""

        return value in self._canonical_exact

    def is_known(self, value: str) -> bool:
        """Return True when a value resolves to the catalog."""

        return self.resolve(value).matched

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable catalog representation."""

        return {
            "version": self.version,
            "source_path": (
                str(self.source_path)
                if self.source_path is not None
                else None
            ),
            "genre_count": self.genre_count,
            "alias_count": self.alias_count,
            "family_count": self.family_count,
            "genres": {
                genre.canonical: {
                    "family": genre.family,
                    "aliases": list(genre.aliases),
                    **(
                        {"description": genre.description}
                        if genre.description is not None
                        else {}
                    ),
                }
                for genre in self
            },
        }
