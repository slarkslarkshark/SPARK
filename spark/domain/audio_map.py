import bisect
from dataclasses import dataclass


@dataclass
class AudioPoint:
    """Одна аудиогруппа (~60 сек) и её позиция в тексте."""
    global_start_sec: float
    global_end_sec: float
    reading_position: int
    segment_text: str
    score: float
    file_index: int
    file_name: str
    local_start_sec: float
    is_unmatched: bool = False


@dataclass
class AudioMap:
    """Карта: аудиотаймкод → позиция в тексте.

    points упорядочены по global_start_sec.
    lookup выполняет бинарный поиск.
    """
    points: list[AudioPoint]

    def __post_init__(self):
        self._starts = [p.global_start_sec for p in self.points]

    def lookup(self, seconds: float) -> AudioPoint | None:
        """Бинарный поиск: найти аудиогруппу по глобальному таймкоду."""
        idx = bisect.bisect_right(self._starts, seconds) - 1
        if 0 <= idx < len(self.points):
            return self.points[idx]
        return None
