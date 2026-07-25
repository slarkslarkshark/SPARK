from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from spark.domain.catalog import BookEntry


@dataclass
class SourceHashes:
    fb2: str
    audio_files: list[str]
    page_photos: list[str]


@dataclass
class ProcessorInfo:
    asr_model: str
    ocr_model: str
    matching_method: str
    matching_params: dict


@dataclass
class Manifest:
    book_id: str
    title: str
    version: int
    parent_version: int | None
    schema_version: int
    operation: str  # "new" | "update"
    page_range: tuple[int, int]
    total_duration_sec: float
    translation: str
    source_hashes: SourceHashes
    processor_info: ProcessorInfo
    created_at: str


@dataclass
class ValidationResult:
    is_valid: bool
    errors: list[str]


class ManifestValidator:
    """Проверяет manifest на совместимость с runtime и каталогом."""

    SUPPORTED_SCHEMA_VERSION = 1

    def validate(
        self, manifest: Manifest, catalog_entry: BookEntry | None
    ) -> ValidationResult:
        errors: list[str] = []

        if manifest.schema_version != self.SUPPORTED_SCHEMA_VERSION:
            errors.append(
                f"Неподдерживаемая версия схемы: "
                f"{manifest.schema_version} (поддерживается "
                f"{self.SUPPORTED_SCHEMA_VERSION})"
            )

        if manifest.operation == "new":
            if catalog_entry is not None:
                errors.append(
                    f"Книга '{manifest.book_id}' уже существует. "
                    f"Для обновления используйте operation='update'."
                )

        if manifest.operation == "update":
            if catalog_entry is None:
                errors.append(
                    f"Книга '{manifest.book_id}' не найдена в каталоге."
                )
            elif catalog_entry.active_version != manifest.parent_version:
                errors.append(
                    f"Несовпадение родительской версии: "
                    f"manifest={manifest.parent_version}, "
                    f"каталог={catalog_entry.active_version}"
                )

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
        )
