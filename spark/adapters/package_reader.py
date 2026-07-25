import json
import zipfile
from pathlib import Path

from spark.domain.manifest import Manifest, ProcessorInfo, SourceHashes


class PackageReader:
    """Читает .sparkbook (ZIP), извлекает manifest и book.sqlite."""

    def __init__(self, zip_path: str):
        self.zip_path = zip_path
        self._zf: zipfile.ZipFile | None = None

    def _open(self) -> zipfile.ZipFile:
        if self._zf is None:
            self._zf = zipfile.ZipFile(self.zip_path, "r")
        return self._zf

    def close(self) -> None:
        if self._zf is not None:
            self._zf.close()
            self._zf = None

    def read_manifest(self) -> Manifest:
        zf = self._open()
        data = json.loads(zf.read("manifest.json"))
        return Manifest(
            book_id=data["book_id"],
            title=data["title"],
            version=data["version"],
            parent_version=data.get("parent_version"),
            schema_version=data["schema_version"],
            operation=data["operation"],
            page_range=tuple(data["page_range"]),
            total_duration_sec=data["total_duration_sec"],
            translation=data.get("translation", ""),
            source_hashes=SourceHashes(
                fb2=data["source_hashes"]["fb2"],
                audio_files=data["source_hashes"].get("audio_files", []),
                page_photos=data["source_hashes"].get("page_photos", []),
            ),
            processor_info=ProcessorInfo(
                asr_model=data.get("processor_info", {}).get("asr_model", ""),
                ocr_model=data.get("processor_info", {}).get("ocr_model", ""),
                matching_method=data.get("processor_info", {}).get(
                    "matching_method", ""
                ),
                matching_params=data.get("processor_info", {}).get(
                    "matching_params", {}
                ),
            ),
            created_at=data.get("created_at", ""),
        )

    def extract_book_sqlite(self, target_dir: str) -> str:
        """Извлекает book.sqlite и cover.jpg (если есть) в target_dir.
        Возвращает путь к book.sqlite.
        """
        zf = self._open()
        target = Path(target_dir)
        zf.extract("book.sqlite", target_dir)
        # Обложка — опциональна
        if "cover.jpg" in (n.filename for n in zf.infolist()):
            zf.extract("cover.jpg", target_dir)
        return str(target / "book.sqlite")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
