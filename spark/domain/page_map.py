import bisect
from dataclasses import dataclass


@dataclass
class PagePoint:
    """Одна запись карты страниц."""
    page_number: int
    reading_position: int
    source: str  # "anchor" | "interpolated"


@dataclass
class PageMap:
    """Полная карта: физическая страница → позиция в тексте.

    points упорядочены по page_number.
    lookup выполняет бинарный поиск.
    """
    points: list[PagePoint]

    def __post_init__(self):
        self._page_numbers = [p.page_number for p in self.points]

    def lookup(self, page_number: int) -> PagePoint | None:
        """Бинарный поиск по номеру страницы."""
        idx = bisect.bisect_left(self._page_numbers, page_number)
        if idx < len(self.points) and self.points[idx].page_number == page_number:
            return self.points[idx]
        if idx > 0:
            return self.points[idx - 1]
        return None
