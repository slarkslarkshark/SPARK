"""Сборка .sparkbook из готовой директории книги."""

import json
import zipfile
from pathlib import Path


class PackageBuilder:
    """Собирает .sparkbook (ZIP) из book.sqlite и manifest.json."""

    def build_from_dir(self, book_dir: str, output_path: str) -> None:
        """Создаёт .sparkbook из директории с book.sqlite и manifest.json.

        Если рядом есть cover.jpg — включается в пакет.
        """
        book_dir = Path(book_dir)
        sqlite_path = book_dir / "book.sqlite"
        manifest_path = book_dir / "manifest.json"
        cover_path = book_dir / "cover.jpg"

        if not sqlite_path.is_file():
            raise FileNotFoundError(f"Нет book.sqlite в {book_dir}")
        if not manifest_path.is_file():
            raise FileNotFoundError(f"Нет manifest.json в {book_dir}")

        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(str(sqlite_path), "book.sqlite")
            zf.write(str(manifest_path), "manifest.json")
            if cover_path.is_file():
                zf.write(str(cover_path), "cover.jpg")
