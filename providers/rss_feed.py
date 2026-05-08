import logging
import hashlib
from datetime import datetime, timedelta
from typing import Optional
import feedparser
import yaml
from config import SOURCES_FILE

logger = logging.getLogger("rss")


def load_sources() -> list[dict]:
    with open(SOURCES_FILE) as f:
        data = yaml.safe_load(f)
    return data.get("sources", [])


def load_domains() -> dict:
    with open(SOURCES_FILE) as f:
        data = yaml.safe_load(f)
    return data.get("domains", {})


def fetch_rss_feeds(since_hours: int = 48) -> list[dict]:
    """
    Fetch recent articles from all RSS sources.
    Returns list of {url, title, source_name, source_domain, published_at}.
    """
    sources = load_sources()
    cutoff = datetime.now() - timedelta(hours=since_hours)
    results = []

    for src in sources:
        name = src["name"]
        rss_url = src["rss"]
        source_id = src.get("source_id", name.lower().replace(" ", "_"))
        language = src.get("language", "en")
        try:
            feed = feedparser.parse(rss_url)
            if feed.bozo:
                logger.warning(f"RSS parse warning for {name}: {feed.bozo_exception}")
            for entry in feed.entries:
                url = entry.get("link", "")
                if not url:
                    continue
                title = entry.get("title", "").strip()
                published = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    try:
                        published = datetime(*entry.published_parsed[:6])
                        if published < cutoff:
                            break  # entries are typically reverse-chronological
                    except (TypeError, ValueError):
                        pass

                results.append({
                    "url": url,
                    "title": title,
                    "source_name": name,
                    "source_id": source_id,
                    "language": language,
                    "published_at": published.isoformat() if published else None,
                })
            logger.info(f"RSS {name}: {len(feed.entries)} entries")
        except Exception as e:
            logger.error(f"RSS fetch failed for {name}: {e}")

    return results


def url_to_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]
