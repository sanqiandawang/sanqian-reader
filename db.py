import sqlite3
import json
import logging
from datetime import datetime, date
from pathlib import Path
from typing import Optional

logger = logging.getLogger("db")

DB_PATH = Path(__file__).parent / "data" / "index.db"

_conn = None


def get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA busy_timeout=5000")
        _conn.row_factory = sqlite3.Row
        _init_schema(_conn)
    return _conn


def _init_schema(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS articles (
            id TEXT PRIMARY KEY,
            title_zh TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT '',
            source_url TEXT NOT NULL DEFAULT '',
            author TEXT NOT NULL DEFAULT '',
            summary_zh TEXT NOT NULL DEFAULT '',
            tags TEXT NOT NULL DEFAULT '[]',
            word_count_zh INTEGER NOT NULL DEFAULT 0,
            original_word_count INTEGER NOT NULL DEFAULT 0,
            translation_model TEXT NOT NULL DEFAULT '',
            prompt_version TEXT NOT NULL DEFAULT '',
            quality_score TEXT NOT NULL DEFAULT '{}',
            read_status TEXT NOT NULL DEFAULT 'unread',
            read_at TEXT,
            fetched_at TEXT NOT NULL DEFAULT '',
            section_id TEXT NOT NULL DEFAULT '',
            has_spoiler INTEGER NOT NULL DEFAULT 0,
            topic_keywords TEXT NOT NULL DEFAULT '[]'
        );

        CREATE TABLE IF NOT EXISTS issues (
            date TEXT PRIMARY KEY,
            articles TEXT NOT NULL DEFAULT '[]',
            editor_note TEXT NOT NULL DEFAULT '',
            stats TEXT NOT NULL DEFAULT '{}',
            epub_sent_at TEXT
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
            title_zh, content='articles', content_rowid='rowid'
        );

        CREATE TRIGGER IF NOT EXISTS articles_ai AFTER INSERT ON articles BEGIN
            INSERT INTO articles_fts(rowid, title_zh) VALUES (new.rowid, new.title_zh);
        END;
    """)
    # Idempotent ALTER TABLE for v2 columns (existing DBs)
    for col, col_def in [
        ("section_id", "TEXT NOT NULL DEFAULT ''"),
        ("has_spoiler", "INTEGER NOT NULL DEFAULT 0"),
        ("topic_keywords", "TEXT NOT NULL DEFAULT '[]'"),
    ]:
        try:
            conn.execute(f"ALTER TABLE articles ADD COLUMN {col} {col_def}")
        except sqlite3.OperationalError:
            pass  # column already exists
    conn.commit()


def article_exists(url_hash: str) -> bool:
    row = get_conn().execute("SELECT 1 FROM articles WHERE id = ?", (url_hash,)).fetchone()
    return row is not None


def insert_article(article: dict):
    conn = get_conn()
    conn.execute("""
        INSERT OR REPLACE INTO articles
        (id, title_zh, source, source_url, author, summary_zh, tags,
         word_count_zh, original_word_count, translation_model, prompt_version,
         quality_score, section_id, has_spoiler, topic_keywords,
         read_status, read_at, fetched_at)
        VALUES (:id, :title_zh, :source, :source_url, :author, :summary_zh, :tags,
                :word_count_zh, :original_word_count, :translation_model, :prompt_version,
                :quality_score, :section_id, :has_spoiler, :topic_keywords,
                :read_status, :read_at, :fetched_at)
    """, {
        "id": article["id"],
        "title_zh": article.get("title_zh", ""),
        "source": article.get("source", ""),
        "source_url": article.get("source_url", ""),
        "author": article.get("author", ""),
        "summary_zh": article.get("summary_zh", ""),
        "tags": json.dumps(article.get("tags", [])),
        "word_count_zh": article.get("word_count_zh", 0),
        "original_word_count": article.get("original_word_count", 0),
        "translation_model": article.get("translation_model", ""),
        "prompt_version": article.get("prompt_version", ""),
        "quality_score": json.dumps(article.get("quality_score", {})),
        "section_id": article.get("section_id", ""),
        "has_spoiler": 1 if article.get("has_spoiler") else 0,
        "topic_keywords": json.dumps(article.get("topic_keywords", [])),
        "read_status": article.get("read_status", "unread"),
        "read_at": article.get("read_at"),
        "fetched_at": article.get("fetched_at", ""),
    })
    conn.commit()


def get_article(id: str) -> Optional[dict]:
    row = get_conn().execute("SELECT * FROM articles WHERE id = ?", (id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["tags"] = json.loads(d.get("tags", "[]"))
    d["quality_score"] = json.loads(d.get("quality_score", "{}"))
    return d


def get_articles_by_ids(ids: list[str]) -> list[dict]:
    if not ids:
        return []
    placeholders = ','.join('?' * len(ids))
    rows = get_conn().execute(
        f"SELECT * FROM articles WHERE id IN ({placeholders})", ids
    ).fetchall()
    result = []
    for row in rows:
        d = dict(row)
        d["tags"] = json.loads(d.get("tags", "[]"))
        d["quality_score"] = json.loads(d.get("quality_score", "{}"))
        result.append(d)
    return result


def update_read_status(id: str, status: str):
    conn = get_conn()
    conn.execute(
        "UPDATE articles SET read_status = ?, read_at = ? WHERE id = ?",
        (status, datetime.now().isoformat(), id)
    )
    conn.commit()


def insert_issue(issue: dict):
    conn = get_conn()
    conn.execute("""
        INSERT OR REPLACE INTO issues (date, articles, editor_note, stats, epub_sent_at)
        VALUES (:date, :articles, :editor_note, :stats, :epub_sent_at)
    """, {
        "date": issue["date"],
        "articles": json.dumps(issue.get("articles", [])),
        "editor_note": issue.get("editor_note", ""),
        "stats": json.dumps(issue.get("stats", {})),
        "epub_sent_at": issue.get("epub_sent_at"),
    })
    conn.commit()


def get_issue(date_str: str) -> Optional[dict]:
    row = get_conn().execute("SELECT * FROM issues WHERE date = ?", (date_str,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["articles"] = json.loads(d.get("articles", "[]"))
    d["stats"] = json.loads(d.get("stats", "{}"))
    return d


def get_latest_issue_date() -> Optional[str]:
    row = get_conn().execute("SELECT date FROM issues ORDER BY date DESC LIMIT 1").fetchone()
    return row["date"] if row else None


def get_recent_issues(limit: int = 30, offset: int = 0) -> list[dict]:
    rows = get_conn().execute(
        "SELECT * FROM issues ORDER BY date DESC LIMIT ? OFFSET ?",
        (limit, offset)
    ).fetchall()
    result = []
    for row in rows:
        d = dict(row)
        d["articles"] = json.loads(d.get("articles", "[]"))
        d["stats"] = json.loads(d.get("stats", "{}"))
        result.append(d)
    return result


def today_issue_exists(today_str: str) -> bool:
    row = get_conn().execute("SELECT 1 FROM issues WHERE date = ?", (today_str,)).fetchone()
    return row is not None


def issue_epub_sent(date_str: str) -> bool:
    row = get_conn().execute("SELECT epub_sent_at FROM issues WHERE date = ?", (date_str,)).fetchone()
    return row is not None and row["epub_sent_at"] is not None


def mark_epub_sent(date_str: str):
    get_conn().execute(
        "UPDATE issues SET epub_sent_at = ? WHERE date = ?",
        (datetime.now().isoformat(), date_str)
    )
    get_conn().commit()
