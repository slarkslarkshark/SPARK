from dataclasses import dataclass


@dataclass
class UnmatchedSegment:
    """Аудиофрагмент без соответствия в тексте-шаблоне
    (интро, титры, музыка, проигрыши)."""
    global_start_sec: float
    global_end_sec: float
    file_name: str
    reason: str
