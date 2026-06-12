from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from app.api import interview, jobs, resumes, screening
from app.config import get_settings, validate_settings
from app.database import init_db

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"


def _public_base() -> str:
    return get_settings().public_base_path.rstrip("/")


def serve_html(path: Path) -> HTMLResponse:
    content = path.read_text(encoding="utf-8")
    base = _public_base()
    if base:
        inject = f'  <base href="{base}/">'
        content = content.replace("<head>", f"<head>\n{inject}", 1)
    return HTMLResponse(content)


def create_app() -> FastAPI:
    validate_settings()
    init_db()

    app = FastAPI(
        title="AI Recruitment Assistant",
        description="A thin screening layer + deep interview agent MVP",
        version="1.0.0",
    )

    app.include_router(jobs.router)
    app.include_router(resumes.router)
    app.include_router(screening.router)
    app.include_router(interview.router)

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/config.js")
    async def public_config():
        base = _public_base()
        body = f'window.__PUBLIC_BASE_PATH__="{base}";'
        return Response(content=body, media_type="application/javascript")

    @app.get("/")
    async def index():
        return serve_html(STATIC_DIR / "index.html")

    @app.get("/screening.html")
    async def screening_page():
        return serve_html(STATIC_DIR / "screening.html")

    @app.get("/interview.html")
    async def interview_page():
        return serve_html(STATIC_DIR / "interview.html")

    @app.get("/report.html")
    async def report_page():
        return serve_html(STATIC_DIR / "report.html")

    @app.get("/history.html")
    async def history_page():
        return serve_html(STATIC_DIR / "history.html")

    @app.get("/job.html")
    async def job_page():
        return serve_html(STATIC_DIR / "job.html")

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
