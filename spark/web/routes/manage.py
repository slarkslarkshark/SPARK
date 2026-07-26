"""UC-08 и UC-09: импорт .sparkbook и rollback."""

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Form, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from jinja2 import Environment, FileSystemLoader

from spark.adapters.book_repo import BookRepo
from spark.adapters.catalog_repo import CatalogRepo
from spark.adapters.staging import StagingArea
from spark.domain.catalog import BookEntry
from spark.domain.manifest import ManifestValidator

router = APIRouter(prefix="/manage", tags=["manage"])


def _jinja(request: Request):
    templates_dir = Path(__file__).parent.parent / "templates"
    return Environment(loader=FileSystemLoader(str(templates_dir)))


def _redirect(request: Request, path: str, status_code: int = 303) -> RedirectResponse:
    """Редирект с учётом root_path."""
    root = request.app.state.root_path
    url = root + path
    return RedirectResponse(url=url, status_code=status_code)


def _render(request: Request, template: str, **kwargs):
    """Рендерит шаблон с root_path."""
    tmpl = _jinja(request).get_template(template)
    kwargs.setdefault("root_path", request.app.state.root_path)
    return HTMLResponse(tmpl.render(**kwargs))


def _data_root(request: Request) -> Path:
    return request.app.state.data_root


@router.get("/import")
def import_form(request: Request):
    """Форма загрузки .sparkbook."""
    return _render(request, "import.html")


@router.post("/import")
async def import_upload(request: Request, file: UploadFile):
    """Приём архива, чтение manifest, валидация."""
    data_root = _data_root(request)

    if not file.filename or not file.filename.endswith(".sparkbook"):
        return _render(request, "import.html",
                       error="Принимаются только файлы .sparkbook")

    # Сохраняем в staging
    zip_bytes = await file.read()
    staging = StagingArea(str(data_root / "staging"))
    upload_id = staging.create_upload(zip_bytes)

    # Читаем manifest
    try:
        catalog_repo = CatalogRepo(str(data_root / "catalog.sqlite"))
        catalog = catalog_repo.load()
        manifest, validation = staging.extract_and_validate(
            upload_id, ManifestValidator(), catalog
        )
    except Exception as e:
        staging.cleanup(upload_id)
        return _render(request, "import.html",
                       error=f"Ошибка чтения пакета: {e}")

    if not validation.is_valid:
        staging.cleanup(upload_id)
        return _render(request, "import.html",
                       error="Пакет не прошёл валидацию",
                       validation_errors=validation.errors)

    # Показываем manifest для подтверждения
    return _render(request, "import_confirm.html",
                   upload_id=upload_id,
                   manifest=manifest,
                   is_update=manifest.operation == "update")


@router.post("/import/confirm")
def import_confirm(
    request: Request,
    upload_id: str = Form(...),
    title: str = Form(""),
    author: str = Form(""),
):
    """Подтверждение и атомарный импорт.

    Название книги = «Название — Автор» (если автор указан).
    """
    data_root = _data_root(request)

    staging = StagingArea(str(data_root / "staging"))
    catalog_path = str(data_root / "catalog.sqlite")
    catalog_repo = CatalogRepo(catalog_path)
    catalog_repo.init_schema()
    catalog = catalog_repo.load()

    # Повторная валидация
    try:
        manifest, validation = staging.extract_and_validate(
            upload_id, ManifestValidator(), catalog
        )
        if not validation.is_valid:
            staging.cleanup(upload_id)
            return _render(request, "import.html",
                           error="Валидация не пройдена",
                           validation_errors=validation.errors)
    except Exception as e:
        staging.cleanup(upload_id)
        return _render(request, "import.html", error=str(e))

    # Обновляем manifest с пользовательскими правками названия и автора
    manifest.title = title.strip() or manifest.title
    manifest.translation = author.strip() or manifest.translation

    # Атомарный импорт
    try:
        book_path = staging.commit(
            upload_id, manifest.book_id, manifest.version,
            str(data_root / "books"),
            manifest=manifest,
        )
    except Exception as e:
        staging.cleanup(upload_id)
        return _render(request, "import.html",
                       error=f"Ошибка при импорте: {e}")

    # Обновляем каталог
    now = datetime.now(timezone.utc).isoformat()
    name = title.strip() or manifest.title
    auth = author.strip()
    book_title = f"{name} — {auth}" if auth else name
    if manifest.operation == "new":
        entry = BookEntry(
            book_id=manifest.book_id,
            title=book_title,
            active_version=manifest.version,
            previous_version=None,
            active_path=book_path,
            previous_path=None,
            imported_at=now,
            updated_at=now,
        )
        catalog.register_new(entry)
        catalog_repo.add_or_update(entry)
    else:
        existing = catalog.get_active(manifest.book_id)
        catalog.activate_version(
            manifest.book_id, manifest.version, book_path
        )
        catalog_repo.update_after_activation(
            manifest.book_id,
            active_version=manifest.version,
            active_path=book_path,
            previous_version=existing.active_version,
            previous_path=existing.active_path,
        )

    return _redirect(request, "/")


@router.post("/{book_id}/rollback")
def rollback(request: Request, book_id: str):
    """Откатить книгу к предыдущей версии."""
    data_root = _data_root(request)
    catalog_path = str(data_root / "catalog.sqlite")
    catalog_repo = CatalogRepo(catalog_path)
    catalog = catalog_repo.load()

    entry = catalog.get_active(book_id)
    if entry is None:
        return _redirect(request, "/")

    try:
        catalog.rollback(book_id)
        catalog_repo.update_after_activation(
            book_id,
            active_version=entry.previous_version,
            active_path=entry.previous_path,
            previous_version=entry.active_version,
            previous_path=entry.active_path,
        )
    except ValueError:
        pass

    return _redirect(request, "/")


@router.post("/{book_id}/delete")
def delete_book(request: Request, book_id: str):
    """Удалить книгу и все её версии."""
    import shutil
    data_root = _data_root(request)
    catalog_path = str(data_root / "catalog.sqlite")
    catalog_repo = CatalogRepo(catalog_path)
    catalog = catalog_repo.load()

    entry = catalog.get_active(book_id)
    if entry is None:
        return _redirect(request, "/")

    book_dir = data_root / "books" / book_id
    if book_dir.exists():
        shutil.rmtree(str(book_dir))

    catalog.remove(book_id)
    catalog_repo.delete_entry(book_id)

    return _redirect(request, "/")


@router.post("/{book_id}/rename")
def rename_book(
    request: Request,
    book_id: str,
    title: str = Form(...),
):
    """Переименовать книгу."""
    data_root = _data_root(request)
    catalog_path = str(data_root / "catalog.sqlite")
    catalog_repo = CatalogRepo(catalog_path)
    catalog = catalog_repo.load()

    new_title = title.strip()
    if not new_title:
        return _redirect(request, "/")

    try:
        catalog.rename(book_id, new_title)
        catalog_repo.rename_entry(book_id, new_title)
    except ValueError:
        pass

    return _redirect(request, "/")


@router.get("/{book_id}/cover")
def get_cover(request: Request, book_id: str):
    """Отдать обложку книги."""
    data_root = _data_root(request)
    catalog_path = str(data_root / "catalog.sqlite")
    catalog_repo = CatalogRepo(catalog_path)
    catalog = catalog_repo.load()

    entry = catalog.get_active(book_id)
    if entry is None:
        return _redirect(request, "/")

    cover_path = Path(entry.active_path).parent / "cover.jpg"
    if not cover_path.is_file():
        from fastapi.responses import Response
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="150">'
            '<rect width="100" height="150" rx="4" fill="#f8fafc" stroke="#94a3b8" stroke-width="1.5"/>'
            '<text x="50" y="82" text-anchor="middle" fill="#94a3b8" font-size="30">📖</text>'
            '</svg>'
        )
        return Response(content=svg, media_type="image/svg+xml")

    return FileResponse(str(cover_path), media_type="image/jpeg")


@router.post("/{book_id}/cover")
async def upload_cover(request: Request, book_id: str, file: UploadFile):
    """Загрузить обложку книги."""
    data_root = _data_root(request)
    catalog_path = str(data_root / "catalog.sqlite")
    catalog_repo = CatalogRepo(catalog_path)
    catalog = catalog_repo.load()

    entry = catalog.get_active(book_id)
    if entry is None:
        return _redirect(request, "/")

    if not file.filename or not file.content_type or not file.content_type.startswith("image/"):
        return _redirect(request, "/")

    cover_path = Path(entry.active_path).parent / "cover.jpg"
    content = await file.read()
    cover_path.write_bytes(content)

    return _redirect(request, "/")


@router.post("/{book_id}/cover/delete")
def delete_cover(request: Request, book_id: str):
    """Удалить обложку книги."""
    data_root = _data_root(request)
    catalog_path = str(data_root / "catalog.sqlite")
    catalog_repo = CatalogRepo(catalog_path)
    catalog = catalog_repo.load()

    entry = catalog.get_active(book_id)
    if entry is None:
        return _redirect(request, "/")

    cover_path = Path(entry.active_path).parent / "cover.jpg"
    cover_path.unlink(missing_ok=True)

    return _redirect(request, "/")


@router.get("/{book_id}/export")
def export_book(request: Request, book_id: str):
    """Скачать книгу как .sparkbook."""
    import tempfile

    data_root = _data_root(request)
    catalog_path = str(data_root / "catalog.sqlite")
    catalog_repo = CatalogRepo(catalog_path)
    catalog = catalog_repo.load()

    entry = catalog.get_active(book_id)
    if entry is None:
        return _redirect(request, "/")

    book_dir = Path(entry.active_path).parent

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".sparkbook")
    try:
        from spark.adapters.package_builder import PackageBuilder
        PackageBuilder().build_from_dir(str(book_dir), tmp.name)
    except Exception:
        Path(tmp.name).unlink(missing_ok=True)
        return _redirect(request, "/")

    filename = f"{entry.book_id}-{entry.active_version}.sparkbook"
    return FileResponse(
        tmp.name,
        media_type="application/zip",
        filename=filename,
        background=None,
    )
