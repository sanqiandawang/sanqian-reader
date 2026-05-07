import json
import logging
import re
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


def markdown_to_html(text: str) -> str:
    """Convert basic markdown to simple HTML for E-ink display."""
    lines = text.split('\n')
    result = []
    in_list = False
    list_type = None  # 'ul' or 'ol'

    for line in lines:
        stripped = line.strip()

        # Empty line — close any open list
        if not stripped:
            if in_list:
                result.append(f'</{list_type}>')
                in_list = False
                list_type = None
            result.append('')
            continue

        # Headers
        if stripped.startswith('### '):
            result.append(f'<h3>{_inline_md(stripped[4:])}</h3>')
            continue
        if stripped.startswith('## '):
            result.append(f'<h3>{_inline_md(stripped[3:])}</h3>')
            continue
        if stripped.startswith('# '):
            result.append(f'<h2>{_inline_md(stripped[2:])}</h2>')
            continue

        # Blockquote
        if stripped.startswith('> '):
            result.append(f'<blockquote>{_inline_md(stripped[2:])}</blockquote>')
            continue

        # Horizontal rule
        if stripped in ('---', '***', '___'):
            result.append('<hr>')
            continue

        # Unordered list
        ul_match = re.match(r'^[-*+]\s', stripped)
        if ul_match:
            if not in_list or list_type != 'ul':
                if in_list:
                    result.append(f'</{list_type}>')
                result.append('<ul>')
                in_list = True
                list_type = 'ul'
            item_text = re.sub(r'^[-*+]\s', '', stripped)
            result.append(f'<li>{_inline_md(item_text)}</li>')
            continue

        # Ordered list
        ol_match = re.match(r'^\d+\.\s', stripped)
        if ol_match:
            if not in_list or list_type != 'ol':
                if in_list:
                    result.append(f'</{list_type}>')
                result.append('<ol>')
                in_list = True
                list_type = 'ol'
            item_text = re.sub(r'^\d+\.\s', '', stripped)
            result.append(f'<li>{_inline_md(item_text)}</li>')
            continue

        # Regular paragraph
        if in_list:
            result.append(f'</{list_type}>')
            in_list = False
            list_type = None
        result.append(f'<p>{_inline_md(stripped)}</p>')

    if in_list:
        result.append(f'</{list_type}>')

    return '\n'.join(result)


def _inline_md(text: str) -> str:
    """Convert inline markdown to HTML."""
    # Bold: **text** or __text__
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'__(.+?)__', r'<strong>\1</strong>', text)
    # Italic: *text* or _text_
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    text = re.sub(r'_(.+?)_', r'<em>\1</em>', text)
    # Links: [text](url)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
    # Inline code: `code`
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    return text


def paginate_content(content: str, chars_per_page: int = PAGE_SIZE_CHARS) -> list:
    """Split HTML content into pages by visible character count, breaking at block elements."""
    # Split at block-level boundaries: </p>, </h2>, </h3>, </blockquote>, </li>, </ul>, </ol>, <hr>
    blocks = re.split(r'(</(?:p|h[234]|blockquote|li|ul|ol)>\s*|<hr[^>]*>\s*)', content)
    # Recombine: each element followed by its closing tag
    paragraphs = []
    i = 0
    while i < len(blocks):
        if i + 1 < len(blocks) and re.match(r'</(?:p|h[234]|blockquote|li|ul|ol)>\s*', blocks[i+1]):
            paragraphs.append(blocks[i] + blocks[i+1])
            i += 2
        elif blocks[i].strip():
            paragraphs.append(blocks[i])
            i += 1
        else:
            i += 1

    pages = []
    current = []
    current_len = 0
    for p in paragraphs:
        # Count visible chars (strip HTML tags)
        visible = len(re.sub(r'<[^>]+>', '', p))
        if current_len + visible > chars_per_page and current:
            pages.append("\n".join(current))
            current = []
            current_len = 0
        current.append(p)
        current_len += visible
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
            full = json.loads(json_path.read_text())
            content = full.get("content_zh", "")
            article["content_zh"] = content

    # Convert markdown to HTML for clean display
    content = markdown_to_html(content)
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
