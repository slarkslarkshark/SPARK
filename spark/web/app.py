import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader

from spark.web.routes import lookup, manage


def create_app(data_root: str, root_path: str = "") -> FastAPI:
    """Создаёт FastAPI-приложение runtime.

    data_root — путь к data/ на диске.
    root_path — базовый путь приложения (например, /spark).
    """
    app = FastAPI(
        title="SPARK Runtime",
        root_path=root_path,
    )

    app.state.data_root = Path(data_root)
    app.state.root_path = root_path.rstrip("/")

    # Монтируем маршруты
    app.include_router(lookup.router)
    app.include_router(manage.router)

    templates_dir = Path(__file__).parent / "templates"

    def _jinja():
        return Environment(loader=FileSystemLoader(str(templates_dir)))

    def _render(template_name: str, **kwargs):
        """Рендерит шаблон с root_path в контексте."""
        tmpl = _jinja().get_template(template_name)
        kwargs.setdefault("root_path", app.state.root_path)
        return HTMLResponse(tmpl.render(**kwargs))

    # Главная страница
    @app.get("/")
    def index(request: Request):
        from spark.adapters.catalog_repo import CatalogRepo
        catalog_path = str(app.state.data_root / "catalog.sqlite")
        catalog = CatalogRepo(catalog_path).load()
        return _render("index.html", books=catalog.list_all())

    # Иконка сайта
    @app.get("/favicon.ico")
    @app.get("/favicon.svg")
    def favicon():
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
            '<rect x="4" y="2" width="24" height="28" rx="2" fill="#8b4513"/>'
            '<rect x="7" y="5" width="13" height="2" rx="0.5" fill="#f5deb3" opacity="0.9"/>'
            '<rect x="7" y="9" width="13" height="2" rx="0.5" fill="#f5deb3" opacity="0.7"/>'
            '<rect x="7" y="13" width="9" height="2" rx="0.5" fill="#f5deb3" opacity="0.5"/>'
            '<line x1="20" y1="2" x2="20" y2="30" stroke="#6b3410" stroke-width="0.5"/>'
            '</svg>'
        )
        return HTMLResponse(content=svg, media_type="image/svg+xml")

    # О проекте
    @app.get("/about")
    def about():
        return _render("about.html")

    return app
