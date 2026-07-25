import json
import shutil
import uuid
from pathlib import Path

from spark.adapters.package_reader import PackageReader
from spark.domain.catalog import BookEntry, Catalog
from spark.domain.manifest import Manifest, ManifestValidator, ValidationResult


def _save_manifest(manifest: Manifest, path: str) -> None:
    """Сериализует Manifest в JSON-файл."""
    data = {
        "book_id": manifest.book_id,
        "title": manifest.title,
        "version": manifest.version,
        "parent_version": manifest.parent_version,
        "schema_version": manifest.schema_version,
        "operation": manifest.operation,
        "page_range": list(manifest.page_range),
        "total_duration_sec": manifest.total_duration_sec,
        "translation": manifest.translation,
        "source_hashes": {
            "fb2": manifest.source_hashes.fb2,
            "audio_files": manifest.source_hashes.audio_files,
            "page_photos": manifest.source_hashes.page_photos,
        },
        "processor_info": {
            "asr_model": manifest.processor_info.asr_model,
            "ocr_model": manifest.processor_info.ocr_model,
            "matching_method": manifest.processor_info.matching_method,
            "matching_params": manifest.processor_info.matching_params,
        },
        "created_at": manifest.created_at,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class StagingArea:
    """Временная файловая область для импорта .sparkbook.

    staging_root/
    └── <upload_id>/
        ├── original.sparkbook
        └── book.sqlite  (после extract_book_sqlite)
    """

    def __init__(self, staging_root: str):
        self.root = Path(staging_root)
        self.root.mkdir(parents=True, exist_ok=True)

    def create_upload(self, zip_bytes: bytes) -> str:
        """Сохраняет архив во временную директорию. Возвращает upload_id."""
        upload_id = uuid.uuid4().hex
        upload_dir = self.root / upload_id
        upload_dir.mkdir(parents=True)
        (upload_dir / "original.sparkbook").write_bytes(zip_bytes)
        return upload_id

    def get_reader(self, upload_id: str) -> PackageReader:
        zip_path = self.root / upload_id / "original.sparkbook"
        if not zip_path.is_file():
            raise FileNotFoundError(
                f"Архив для '{upload_id}' не найден в staging"
            )
        return PackageReader(str(zip_path))

    def extract_and_validate(
        self,
        upload_id: str,
        validator: ManifestValidator,
        catalog: Catalog,
    ) -> tuple[Manifest, ValidationResult]:
        """Читает manifest из архива и проверяет его."""
        with self.get_reader(upload_id) as reader:
            manifest = reader.read_manifest()

        catalog_entry = catalog.get_active(manifest.book_id)
        result = validator.validate(manifest, catalog_entry)
        return manifest, result

    def commit(
        self,
        upload_id: str,
        book_id: str,
        version: int,
        books_root: str,
        manifest: Manifest | None = None,
    ) -> str:
        """Извлекает book.sqlite и атомарно перемещает в books/<book_id>/<version>/.

        Если передан manifest, сохраняет его как manifest.json рядом с book.sqlite.
        Возвращает финальный путь к book.sqlite.
        """
        upload_dir = self.root / upload_id
        target_dir = Path(books_root) / book_id / str(version)

        # Извлекаем book.sqlite во временную директорию
        with self.get_reader(upload_id) as reader:
            reader.extract_book_sqlite(str(upload_dir))

        # Сохраняем manifest.json для будущего экспорта
        if manifest is not None:
            _save_manifest(manifest, str(upload_dir / "manifest.json"))

        # Атомарно: rename временной директории в финальную.
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        if target_dir.exists():
            shutil.rmtree(str(target_dir))
        shutil.move(str(upload_dir), str(target_dir))

        return str(target_dir / "book.sqlite")

    def cleanup(self, upload_id: str) -> None:
        """Удаляет временную директорию upload'а."""
        upload_dir = self.root / upload_id
        if upload_dir.exists():
            shutil.rmtree(str(upload_dir))
