import json
import sqlite3
from pathlib import Path
from typing import cast

from spark.domain.anchor import Anchor
from spark.domain.audio_map import AudioPoint, AudioMap
from spark.domain.book import Book, MatchingMap, Section, TextCorpus
from spark.domain.page_map import PageMap, PagePoint
from spark.domain.unmatched import UnmatchedSegment


class BookRepo:
    """Загружает Book из book.sqlite."""

    def load(self, db_path: str) -> Book:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            return self._load(conn)
        finally:
            conn.close()

    def _load(self, conn: sqlite3.Connection) -> Book:
        meta = self._read_metadata(conn)

        full_text, sections, matching_map = self._read_text(conn)
        audio_map = self._read_audio_map(conn)
        page_map = self._read_page_map(conn)
        anchors = self._read_anchors(conn)
        unmatched = self._read_unmatched(conn)

        return Book(
            book_id=meta["book_id"],
            version=meta["version"],
            title=meta["title"],
            corpus=TextCorpus(
                full_text=full_text,
                sections=sections,
                matching_map=matching_map,
            ),
            audio_map=audio_map,
            page_map=page_map,
            anchors=anchors,
            unmatched=unmatched,
            page_range=(meta["page_range_min"], meta["page_range_max"]),
            total_duration_sec=meta["total_duration_sec"],
        )

    def _read_metadata(self, conn: sqlite3.Connection) -> dict:
        rows = conn.execute("SELECT key, value FROM metadata").fetchall()
        meta = {r["key"]: r["value"] for r in rows}
        return {
            "book_id": meta["book_id"],
            "version": int(meta["version"]),
            "title": meta["title"],
            "page_range_min": int(meta.get("page_range_min", 0)),
            "page_range_max": int(meta.get("page_range_max", 0)),
            "total_duration_sec": float(meta.get("total_duration_sec", 0)),
        }

    def _read_text(
        self, conn: sqlite3.Connection
    ) -> tuple[str, list[Section], MatchingMap]:
        row = conn.execute("SELECT content FROM full_text").fetchone()
        full_text = row["content"] if row else ""

        sections = []
        for r in conn.execute(
            "SELECT title, char_start, char_end FROM sections ORDER BY char_start"
        ):
            sections.append(
                Section(title=r["title"], char_start=r["char_start"], char_end=r["char_end"])
            )

        segments = []
        for r in conn.execute(
            "SELECT matching_pos, normalized_pos FROM matching_map ORDER BY matching_pos"
        ):
            segments.append((r["matching_pos"], r["normalized_pos"]))

        return full_text, sections, MatchingMap(segments=segments)

    def _read_audio_map(self, conn: sqlite3.Connection) -> AudioMap:
        points = []
        for r in conn.execute(
            "SELECT global_start_sec, global_end_sec, reading_position, "
            "segment_text, score, file_index, file_name, local_start_sec, "
            "is_unmatched "
            "FROM audio_map ORDER BY global_start_sec"
        ):
            points.append(
                AudioPoint(
                    global_start_sec=r["global_start_sec"],
                    global_end_sec=r["global_end_sec"],
                    reading_position=r["reading_position"],
                    segment_text=r["segment_text"],
                    score=r["score"],
                    file_index=r["file_index"],
                    file_name=r["file_name"],
                    local_start_sec=r["local_start_sec"],
                    is_unmatched=bool(r["is_unmatched"]),
                )
            )
        return AudioMap(points=points)

    def _read_page_map(self, conn: sqlite3.Connection) -> PageMap:
        points = []
        for r in conn.execute(
            "SELECT page_number, reading_position, source "
            "FROM page_map ORDER BY page_number"
        ):
            points.append(
                PagePoint(
                    page_number=r["page_number"],
                    reading_position=r["reading_position"],
                    source=r["source"],
                )
            )
        return PageMap(points=points)

    def _read_anchors(self, conn: sqlite3.Connection) -> list[Anchor]:
        anchors = []
        for r in conn.execute(
            "SELECT page_number, reading_position, ocr_text, ocr_confidence, "
            "match_score, section, source_file FROM anchors ORDER BY page_number"
        ):
            anchors.append(
                Anchor(
                    page_number=r["page_number"],
                    reading_position=r["reading_position"],
                    ocr_text=r["ocr_text"],
                    ocr_confidence=r["ocr_confidence"],
                    match_score=r["match_score"],
                    section=r["section"],
                    source_file=r["source_file"],
                )
            )
        return anchors

    def _read_unmatched(self, conn: sqlite3.Connection) -> list[UnmatchedSegment]:
        segments = []
        for r in conn.execute(
            "SELECT global_start_sec, global_end_sec, file_name, reason "
            "FROM unmatched ORDER BY global_start_sec"
        ):
            segments.append(
                UnmatchedSegment(
                    global_start_sec=r["global_start_sec"],
                    global_end_sec=r["global_end_sec"],
                    file_name=r["file_name"],
                    reason=r["reason"],
                )
            )
        return segments
