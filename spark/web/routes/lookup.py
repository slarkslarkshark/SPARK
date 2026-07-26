"""UC-04 и UC-05: поиск страницы по таймкоду и наоборот."""

import re
from pathlib import Path

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader

from spark.adapters.book_repo import BookRepo
from spark.adapters.catalog_repo import CatalogRepo


def _trim_to_sentences(text: str) -> str:
    """Обрезает текст по границам предложений."""
    m = re.search(r"[.!?]\s", text)
    if m:
        text = text[: m.start() + 1]
    return text.strip()


router = APIRouter(prefix="/books/{book_id}", tags=["lookup"])


def _jinja(request: Request):
    templates_dir = Path(__file__).parent.parent / "templates"
    return Environment(loader=FileSystemLoader(str(templates_dir)))


def _render(request: Request, template: str, **kwargs):
    """Рендерит шаблон с root_path."""
    tmpl = _jinja(request).get_template(template)
    kwargs.setdefault("root_path", request.app.state.root_path)
    return HTMLResponse(tmpl.render(**kwargs))


def _load_book(request: Request, book_id: str):
    data_root: Path = request.app.state.data_root
    catalog_path = str(data_root / "catalog.sqlite")
    catalog_repo = CatalogRepo(catalog_path)
    catalog = catalog_repo.load()

    entry = catalog.get_active(book_id)
    if entry is None:
        return None, None

    book = BookRepo().load(entry.active_path)
    return book, entry


@router.get("/lookup/audio")
def lookup_audio(
    request: Request,
    book_id: str,
    time: str | None = Query(None, description="Глобальный таймкод ЧЧ:ММ:СС"),
    file: str | None = Query(None, description="Имя файла для локального таймкода"),
):
    """UC-04: таймкод → страница."""
    book, entry = _load_book(request, book_id)

    if book is None:
        return _render(request, "lookup_audio.html",
                       book_id=book_id, error="Книга не найдена", status_code=404)

    # Без параметров — просто показываем форму
    if time is None:
        return _render(request, "lookup_audio.html",
                       book_id=book_id, book_title=book.title)

    # Парсим таймкод
    try:
        parts = time.split(":")
        if len(parts) == 3:
            hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
        elif len(parts) == 2:
            hours, minutes, seconds = 0, int(parts[0]), int(parts[1])
        else:
            hours, minutes, seconds = 0, 0, int(parts[0])
        total_seconds = hours * 3600 + minutes * 60 + seconds
    except (ValueError, IndexError):
        return _render(request, "lookup_audio.html",
                       book_id=book_id, book_title=book.title,
                       error="Неверный формат таймкода. Используйте ЧЧ:ММ:СС")

    # Если указан файл — локальный таймкод, конвертируем в глобальный
    if file:
        for ap in book.audio_map.points:
            if ap.file_name == file:
                total_seconds = ap.global_start_sec - ap.local_start_sec + total_seconds
                break

    # Ищем аудиоточку
    ap = book.audio_map.lookup(total_seconds)
    if ap is None:
        return _render(request, "lookup_audio.html",
                       book_id=book_id, book_title=book.title,
                       error="Таймкод вне диапазона аудиокниги")

    # Ищем ближайшую страницу по reading_position
    rp = ap.reading_position
    page = None
    for p in book.page_map.points:
        if p.reading_position <= rp:
            page = p
        else:
            break

    quote = _trim_to_sentences(ap.segment_text)
    section = book.corpus.section_at(rp)

    return _render(request, "lookup_audio.html",
                   book_id=book_id,
                   book_title=book.title,
                   input_time=time,
                   file_name=ap.file_name,
                   global_time=f"{int(ap.global_start_sec // 3600):02d}:{int((ap.global_start_sec % 3600) // 60):02d}:{int(ap.global_start_sec % 60):02d}",
                   local_time=f"{int(ap.local_start_sec // 60):02d}:{int(ap.local_start_sec % 60):02d}",
                   page_number=page.page_number if page else "?",
                   page_source=page.source if page else "?",
                   section=section,
                   quote=quote,
                   score=f"{ap.score:.3f}")


@router.get("/lookup/page")
def lookup_page(
    request: Request,
    book_id: str,
    page: int | None = Query(None, description="Номер физической страницы"),
):
    """UC-05: страница → таймкод."""
    book, entry = _load_book(request, book_id)

    if book is None:
        return _render(request, "lookup_page.html",
                       book_id=book_id, error="Книга не найдена", status_code=404)

    # Без параметра — просто показываем форму
    if page is None:
        return _render(request, "lookup_page.html",
                       book_id=book_id, book_title=book.title)

    pp = book.page_map.lookup(page)
    if pp is None:
        return _render(request, "lookup_page.html",
                       book_id=book_id, book_title=book.title,
                       error=f"Страница {page} вне диапазона книги")

    # Ищем ближайшую аудиоточку
    rp = pp.reading_position
    ap = None
    for a in book.audio_map.points:
        if a.reading_position <= rp:
            ap = a
        else:
            break

    quote = book.corpus.quote(rp)
    section = book.corpus.section_at(rp)

    result = {
        "book_id": book_id,
        "book_title": book.title,
        "page_number": page,
        "matched_page": pp.page_number,
        "page_source": pp.source,
        "section": section,
        "quote": quote,
    }

    if ap:
        result.update({
            "file_name": ap.file_name,
            "global_time": f"{int(ap.global_start_sec // 3600):02d}:{int((ap.global_start_sec % 3600) // 60):02d}:{int(ap.global_start_sec % 60):02d}",
            "local_time": f"{int(ap.local_start_sec // 60):02d}:{int(ap.local_start_sec % 60):02d}",
            "score": f"{ap.score:.3f}",
        })

    return _render(request, "lookup_page.html", **result)
