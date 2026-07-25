import re
from dataclasses import dataclass

from spark.domain.anchor import Anchor
from spark.domain.audio_map import AudioMap
from spark.domain.page_map import PageMap
from spark.domain.unmatched import UnmatchedSegment


@dataclass
class Section:
    """Граница секции (часть/глава) в тексте."""
    title: str
    char_start: int  # позиция в normalized_text
    char_end: int


@dataclass
class MatchingMap:
    """Sparse-маппинг matching_pos → normalized_pos.

    Обе карты (audio_map и page_map) используют координаты normalized_text,
    поэтому в текущей версии to_normalized() возвращает входное значение.
    Маппинг сохранён для будущих сценариев, где может понадобиться
    преобразование между matching_text и normalized_text.
    """
    segments: list[tuple[int, int]]  # [(matching_pos, normalized_pos), ...]

    def __post_init__(self):
        self._keys = [s[0] for s in self.segments]
        self._vals = [s[1] for s in self.segments]

    def to_normalized(self, reading_pos: int) -> int:
        """Возвращает позицию в normalized_text.
        В текущей модели обе карты уже в normalized_text,
        поэтому возвращает входное значение без изменений.
        """
        return reading_pos


@dataclass
class TextCorpus:
    """Текст книги и маппинг двух координатных шкал.

    full_text        — канонический текст (normalized_text), источник цитат.
    matching_map     — sparse-маппинг matching_pos → normalized_pos.
    sections         — границы секций в координатах full_text.
    """
    full_text: str
    sections: list[Section]
    matching_map: MatchingMap

    # Символы, завершающие предложение
    _SENTENCE_END = re.compile(r"[.!?]\s")

    def quote(self, reading_pos: int, words: int = 60) -> str:
        """Цитата из full_text вокруг reading_position.

        Отмеряется в словах (по пробелам) и обрезается по границам
        предложений, чтобы не рвать фразы посередине.
        """
        norm_pos = self.matching_map.to_normalized(reading_pos)
        text = self.full_text

        # Левая граница: ищем ~words слов слева от позиции
        left = norm_pos
        word_count = 0
        while left > 0 and word_count < words:
            left -= 1
            if text[left] == " " and left + 1 < norm_pos:
                word_count += 1
        # Двигаемся к началу предложения
        search_start = max(0, left - 200)
        for m in re.finditer(r"[.!?]\s", text[search_start:norm_pos]):
            candidate = search_start + m.end()
            if candidate > left:
                left = candidate
                break

        # Правая граница: ищем ~words слов справа от позиции
        right = norm_pos
        word_count = 0
        text_len = len(text)
        while right < text_len and word_count < words:
            if text[right] == " " and right > norm_pos:
                word_count += 1
            right += 1
        # Двигаемся к концу предложения
        search_end = min(text_len, right + 200)
        m = re.search(r"[.!?]\s", text[norm_pos:search_end])
        if m:
            right = norm_pos + m.start() + 1  # включаем знак

        return text[left:right].strip()

    def section_at(self, reading_pos: int) -> str:
        """Название секции для reading_position."""
        norm_pos = self.matching_map.to_normalized(reading_pos)
        for s in self.sections:
            if s.char_start <= norm_pos < s.char_end:
                # Убираем технические префиксы вроде "Body 0 / "
                parts = s.title.split(" / ")
                clean = [p for p in parts if not p.startswith("Body ")]
                return " / ".join(clean)
        return ""


@dataclass
class Book:
    """Агрегат: одна версия импортированной книги."""
    book_id: str
    version: int
    title: str
    corpus: TextCorpus
    audio_map: AudioMap
    page_map: PageMap
    anchors: list[Anchor]
    unmatched: list[UnmatchedSegment]
    page_range: tuple[int, int]
    total_duration_sec: float
