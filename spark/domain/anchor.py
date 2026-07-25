from dataclasses import dataclass


@dataclass
class Anchor:
    """OCR-якорь: одна страница, надёжно привязанная к тексту-шаблону."""
    page_number: int
    reading_position: int
    ocr_text: str
    ocr_confidence: float
    match_score: float
    section: str
    source_file: str
