import logging
import shutil
import threading
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader

from config import SERVER_PORT, REFRESH_COOLDOWN_MINUTES, REFRESH_TOKEN, CACHE_DIR, CACHE_RETENTION_DAYS
from db import (
    get_issue, get_latest_issue_date, get_recent_issues,
    get_article, get_articles_by_ids, update_read_status, today_issue_exists,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("server")

app = FastAPI(title="三千要看")
env = Environment(loader=FileSystemLoader(Path(__file__).parent / "templates"))
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

PAGE_SIZE_CHARS = 2000


def paginate_content(content: str, chars_per_page: int = PAGE_SIZE_CHARS) -> list:
    """Split content into pages by character count, trying to break at paragraphs."""
    paragraphs = content.split("\n")
    pages = []
    current = []
    current_len = 0
    for p in paragraphs:
        p_len = len(p)
        if current_len + p_len > chars_per_page and current:
            pages.append("\n".join(current))
            current = []
            current_len = 0
        current.append(p)
        current_len += p_len
    if current:
        pages.append("\n".join(current))
    return pages


@app.get("/", response_class=HTMLResponse)
async def index():
    latest_date = get_latest_issue_date()
    today_str = date.today().isoformat()
    if not latest_date:
        template = env.get_template("index.html")
        return template.render(issue=None, articles=[], today=today_str)

    issue = get_issue(latest_date)
    if not issue:
        template = env.get_template("index.html")
        return template.render(issue=None, articles=[], today=today_str)

    article_ids = issue.get("articles", [])
    articles = get_articles_by_ids(article_ids)

    template = env.get_template("index.html")
    return template.render(issue=issue, articles=articles, today=latest_date)


@app.get("/article/{article_id}", response_class=HTMLResponse)
async def article_view(article_id: str, page: int = Query(1, ge=1)):
    article = get_article(article_id)
    if not article:
        return HTMLResponse("<h1>Article not found</h1>", status_code=404)

    # Load full content from JSON cold storage if not in SQLite
    content = article.get("content_zh", "")
    if not content:
        json_path = Path(__file__).parent / "data" / "articles" / f"{article_id}.json"
        if json_path.exists():
            import json
            full = json.loads(json_path.read_text())
            content = full.get("content_zh", "")
            article["content_zh"] = content
    pages = paginate_content(content)
    total_pages = len(pages) or 1
    page = min(page, total_pages)
    is_last = (page == total_pages)

    # Track reading progress
    status = "done" if is_last else "reading"
    update_read_status(article_id, status)

    # Find next article in same issue
    issue_date = article.get("fetched_at", "")[:10]
    next_id = None
    if issue_date:
        issue = get_issue(issue_date)
        if issue:
            ids = issue.get("articles", [])
            try:
                idx = ids.index(article_id)
                if idx + 1 < len(ids):
                    next_id = ids[idx + 1]
            except ValueError:
                pass

    template = env.get_template("article.html")
    return template.render(
        article=article,
        page_content=pages[page - 1] if pages else "",
        page=page,
        total_pages=total_pages,
        is_last=is_last,
        next_id=next_id,
    )


@app.get("/archive", response_class=HTMLResponse)
async def archive(page: int = Query(1, ge=1)):
    per_page = 20
    offset = (page - 1) * per_page
    issues = get_recent_issues(limit=per_page, offset=offset)
    template = env.get_template("archive.html")
    return template.render(issues=issues, page=page)


@app.get("/api/epub/{date_str}")
async def download_epub(date_str: str):
    epub_path = Path(__file__).parent / "output" / f"三千要看-{date_str}.epub"
    if epub_path.exists():
        return FileResponse(str(epub_path), media_type="application/epub+zip",
                           filename=f"三千要看-{date_str}.epub")
    return JSONResponse({"error": "EPUB not found"}, status_code=404)


@app.get("/refresh")
async def refresh(token: str = Query(...)):
    if token != REFRESH_TOKEN:
        return JSONResponse({"error": "Invalid token"}, status_code=403)

    # Rate limit check
    last_refresh_file = Path(__file__).parent / "data" / "cache" / ".last_refresh"
    if last_refresh_file.exists():
        last = datetime.fromisoformat(last_refresh_file.read_text().strip())
        if (datetime.now() - last).total_seconds() < REFRESH_COOLDOWN_MINUTES * 60:
            remaining = REFRESH_COOLDOWN_MINUTES * 60 - int((datetime.now() - last).total_seconds())
            return JSONResponse({"error": f"Rate limited. Try again in {remaining // 60} min"}, status_code=429)

    last_refresh_file.parent.mkdir(parents=True, exist_ok=True)
    last_refresh_file.write_text(datetime.now().isoformat())

    # Clear today's cache
    today_str = date.today().isoformat()
    cache_today = CACHE_DIR / today_str
    if cache_today.exists():
        shutil.rmtree(cache_today)

    # Clean stale caches
    cutoff = datetime.now() - timedelta(days=CACHE_RETENTION_DAYS)
    for d in CACHE_DIR.iterdir():
        if d.is_dir() and d.name != ".last_refresh":
            try:
                dir_date = datetime.strptime(d.name, "%Y-%m-%d")
                if dir_date < cutoff:
                    shutil.rmtree(d)
            except ValueError:
                pass

    def run():
        from pipeline import run_pipeline
        run_pipeline(send_epub=True)

    thread = threading.Thread(target=run)
    thread.start()

    return JSONResponse({"status": "Pipeline started", "date": today_str})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=SERVER_PORT)
