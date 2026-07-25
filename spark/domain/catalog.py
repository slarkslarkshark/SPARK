from dataclasses import dataclass


@dataclass
class BookEntry:
    """Одна запись в каталоге книг."""
    book_id: str
    title: str
    active_version: int
    previous_version: int | None
    active_path: str
    previous_path: str | None
    imported_at: str
    updated_at: str


@dataclass
class Catalog:
    """Справочник импортированных книг.

    Не знает о файлах — только о путях и версиях.
    Мутабелен: register_new, activate_version, rollback меняют состояние.
    """
    entries: dict[str, BookEntry]

    def get_active(self, book_id: str) -> BookEntry | None:
        return self.entries.get(book_id)

    def list_all(self) -> list[BookEntry]:
        return list(self.entries.values())

    def register_new(self, entry: BookEntry) -> None:
        if entry.book_id in self.entries:
            raise ValueError(
                f"Книга '{entry.book_id}' уже существует в каталоге"
            )
        self.entries[entry.book_id] = entry

    def activate_version(self, book_id: str, version: int, path: str) -> None:
        entry = self.entries.get(book_id)
        if entry is None:
            raise ValueError(f"Книга '{book_id}' не найдена в каталоге")
        entry.previous_version = entry.active_version
        entry.previous_path = entry.active_path
        entry.active_version = version
        entry.active_path = path

    def rollback(self, book_id: str) -> None:
        entry = self.entries.get(book_id)
        if entry is None:
            raise ValueError(f"Книга '{book_id}' не найдена в каталоге")
        if entry.previous_version is None or entry.previous_path is None:
            raise ValueError(
                f"Для книги '{book_id}' нет предыдущей версии для отката"
            )
        entry.active_version, entry.previous_version = (
            entry.previous_version,
            entry.active_version,
        )
        entry.active_path, entry.previous_path = (
            entry.previous_path,
            entry.active_path,
        )

    def remove(self, book_id: str) -> BookEntry:
        entry = self.entries.pop(book_id, None)
        if entry is None:
            raise ValueError(f"Книга '{book_id}' не найдена в каталоге")
        return entry

    def rename(self, book_id: str, new_title: str) -> None:
        entry = self.entries.get(book_id)
        if entry is None:
            raise ValueError(f"Книга '{book_id}' не найдена в каталоге")
        entry.title = new_title
