from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader

from spark.web.routes import lookup, manage


def create_app(data_root: str) -> FastAPI:
    """Создаёт FastAPI-приложение runtime.

    data_root — путь к data/ на диске:
      data/
      ├── catalog.sqlite
      ├── books/    — импортированные книги
      └── staging/  — временная область импорта
    """
    app = FastAPI(title="SPARK Runtime")

    # Сохраняем конфигурацию в состоянии приложения
    app.state.data_root = Path(data_root)

    # Монтируем маршруты
    app.include_router(lookup.router)
    app.include_router(manage.router)

    templates_dir = Path(__file__).parent / "templates"

    def _jinja():
        return Environment(loader=FileSystemLoader(str(templates_dir)))

    def _catalog(request: Request):
        from spark.adapters.catalog_repo import CatalogRepo
        catalog_path = str(app.state.data_root / "catalog.sqlite")
        return CatalogRepo(catalog_path).load()

    # Главная страница
    @app.get("/")
    def index(request: Request):
        catalog = _catalog(request)
        tmpl = _jinja().get_template("index.html")
        return HTMLResponse(tmpl.render(books=catalog.list_all()))

    # О проекте
    @app.get("/about")
    def about():
        tmpl = _jinja().get_template("about.html")
        return HTMLResponse(tmpl.render())

    return app
