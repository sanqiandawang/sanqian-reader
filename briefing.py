#!/usr/bin/env python3
"""三千要看 v2 — 早报短管线。独立于主管线，失败不阻塞。"""
import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path

import feedparser
import yaml

from config import ROOT

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("briefing")

BRIEFING_SOURCES_FILE = ROOT / "briefing_sources.yaml"
DATA_DIR = ROOT / "data" / "briefings"


def fetch_briefing_entries() -> list:
    """Fetch RSS entries (title + summary only, no full text)."""
    with open(BRIEFING_SOURCES_FILE) as f:
        sources = yaml.safe_load(f).get("sources", [])

    cutoff = datetime.now() - timedelta(hours=24)
    all_entries = []
    failed_sources = []

    for src in sources:
        try:
            feed = feedparser.parse(src["url"])
            for entry in feed.entries:
                url = entry.get("link", "")
                guid = entry.get("guid", entry.get("id", url))
                title = entry.get("title", "").strip()
                summary = entry.get("summary", entry.get("description", ""))
                # Strip HTML tags from summary
                import re
                summary = re.sub(r'<[^>]+>', '', summary)[:200]
                published = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    try:
                        published = datetime(*entry.published_parsed[:6])
                        if published < cutoff:
                            break
                    except (TypeError, ValueError):
                        pass
                all_entries.append({
                    "title": title,
                    "summary": summary,
                    "url": url,
                    "guid": guid,
                    "source_name": src["id"],
                    "weight": src.get("weight", 1.0),
                    "published_at": published.isoformat() if published else None,
                })
            logger.info(f"Briefing RSS {src['id']}: {len(feed.entries)} entries")
        except Exception as e:
            logger.error(f"Briefing fetch failed for {src['id']}: {e}")
            failed_sources.append(src['id'])

    # Deduplicate by GUID
    seen_guids = set()
    deduped = []
    for e in all_entries:
        if e["guid"] not in seen_guids:
            seen_guids.add(e["guid"])
            deduped.append(e)

    # Sort by weight * recency
    deduped.sort(key=lambda e: e["weight"], reverse=True)
    logger.info(f"Briefing: {len(deduped)} unique entries after dedup")
    return deduped, failed_sources


def run_briefing():
    today_str = date.today().isoformat()
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    entries, failed_sources = fetch_briefing_entries()
    if not entries:
        logger.warning("No briefing entries found, skipping")
        return None

    from ai_client import generate_briefing
    result = generate_briefing(entries)

    if not result or not result.get("items"):
        logger.warning("Briefing generation returned empty")
        # Save with warnings even if empty
        if failed_sources:
            result = {"items": [], "_warnings": [f"早报源连接失败: {', '.join(failed_sources)}"]}
            output_path = DATA_DIR / f"{today_str}.json"
            output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        return None

    if failed_sources:
        result["_warnings"] = [f"早报源连接失败: {', '.join(failed_sources)}"]

    # Save
    output_path = DATA_DIR / f"{today_str}.json"
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    logger.info(f"Briefing saved: {output_path} ({len(result['items'])} items)")
    return result


if __name__ == "__main__":
    run_briefing()
