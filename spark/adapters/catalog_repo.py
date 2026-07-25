import sqlite3
from datetime import datetime, timezone

from spark.domain.catalog import BookEntry, Catalog


class CatalogRepo:
    """Хранит каталог книг в catalog.sqlite."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def init_schema(self) -> None:
        conn = self._connect()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS book_entries (
                    book_id          TEXT PRIMARY KEY,
                    title            TEXT NOT NULL,
                    active_version   INTEGER NOT NULL,
                    previous_version INTEGER,
                    active_path      TEXT NOT NULL,
                    previous_path    TEXT,
                    imported_at      TEXT NOT NULL,
                    updated_at       TEXT NOT NULL
                );
            """)
            conn.commit()
        finally:
            conn.close()

    def load(self) -> Catalog:
        conn = self._connect()
        try:
            conn.execute("SELECT 1 FROM book_entries LIMIT 0")
        except sqlite3.OperationalError:
            conn.close()
            return Catalog(entries={})

        try:
            entries: dict[str, BookEntry] = {}
            for r in conn.execute("SELECT * FROM book_entries"):
                entries[r["book_id"]] = BookEntry(
                    book_id=r["book_id"],
                    title=r["title"],
                    active_version=r["active_version"],
                    previous_version=r["previous_version"],
                    active_path=r["active_path"],
                    previous_path=r["previous_path"],
                    imported_at=r["imported_at"],
                    updated_at=r["updated_at"],
                )
            return Catalog(entries=entries)
        finally:
            conn.close()

    def add_or_update(self, entry: BookEntry) -> None:
        conn = self._connect()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO book_entries "
                "(book_id, title, active_version, previous_version, "
                "active_path, previous_path, imported_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    entry.book_id,
                    entry.title,
                    entry.active_version,
                    entry.previous_version,
                    entry.active_path,
                    entry.previous_path,
                    entry.imported_at,
                    entry.updated_at,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def update_after_activation(
        self,
        book_id: str,
        active_version: int,
        active_path: str,
        previous_version: int | None,
        previous_path: str | None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE book_entries SET "
                "active_version = ?, previous_version = ?, "
                "active_path = ?, previous_path = ?, updated_at = ? "
                "WHERE book_id = ?",
                (
                    active_version,
                    previous_version,
                    active_path,
                    previous_path,
                    now,
                    book_id,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def delete_entry(self, book_id: str) -> None:
        conn = self._connect()
        try:
            conn.execute(
                "DELETE FROM book_entries WHERE book_id = ?",
                (book_id,),
            )
            conn.commit()
        finally:
            conn.close()

    def rename_entry(self, book_id: str, new_title: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE book_entries SET title = ?, updated_at = ? WHERE book_id = ?",
                (new_title, now, book_id),
            )
            conn.commit()
        finally:
            conn.close()
