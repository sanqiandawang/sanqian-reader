#!/usr/bin/env python3
"""三千要看 — Daily pipeline: fetch, screen, curate, translate, review, publish"""
import json
import logging
import hashlib
import time
import shutil
import random
from datetime import datetime, date, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Tuple

from config import (
    CACHE_DIR, CACHE_RETENTION_DAYS, MAX_ARTICLE_WORDS, MAX_CONCURRENCY,
    MAX_RETRIES, MIN_ARTICLES_PER_ISSUE, TRANSLATED_MIN_CHARS,
    SCREEN_MIN_WORDS, DAILY_TOKEN_BUDGET,
)
from providers.rss_feed import fetch_rss_feeds, url_to_id
from providers.jina import JinaProvider
from providers.readability_provider import ReadabilityProvider
from db import (
    article_exists, insert_article, insert_issue, get_issue,
    issue_epub_sent, mark_epub_sent, today_issue_exists,
)
from models import Article, Issue, CandidateArticle

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("pipeline")

jina = JinaProvider()
readability = ReadabilityProvider()

TODAY = date.today().isoformat()


# ==================== Cache & Checkpoint Helpers ====================

def cache_path(step: str) -> Path:
    d = CACHE_DIR / TODAY
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{step}.json"


def load_cache(step: str) -> Optional[dict]:
    p = cache_path(step)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except json.JSONDecodeError:
            logger.warning(f"Corrupted cache: {p}")
    return None


def save_cache(step: str, data: dict):
    cache_path(step).write_text(json.dumps(data, ensure_ascii=False, indent=2))


def clear_stale_cache():
    cutoff = datetime.now() - timedelta(days=CACHE_RETENTION_DAYS)
    if not CACHE_DIR.exists():
        return
    for d in CACHE_DIR.iterdir():
        if d.is_dir():
            try:
                dir_date = datetime.strptime(d.name, "%Y-%m-%d")
                if dir_date < cutoff:
                    shutil.rmtree(d)
                    logger.info(f"Cleaned stale cache: {d.name}")
            except ValueError:
                pass


# ==================== Failed URL Tracking ====================

def load_failed_urls() -> dict:
    """Returns {url: fail_count} for URLs with fail_count < 3"""
    failed_file = Path(__file__).parent / "data" / "failed_urls.jsonl"
    if not failed_file.exists():
        return {}
    result = {}
    with open(failed_file) as f:
        for line in f:
            try:
                record = json.loads(line.strip())
                if record.get("fail_count", 0) < 3:
                    result[record["url"]] = record["fail_count"]
            except json.JSONDecodeError:
                pass
    return result


def log_failed_url(url: str, reason: str, previous_count: int = 0):
    failed_file = Path(__file__).parent / "data" / "failed_urls.jsonl"
    record = {
        "url": url,
        "fail_count": previous_count + 1,
        "last_failed": TODAY,
        "reason": reason,
    }
    with open(failed_file, "a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ==================== Blacklist ====================

def load_blacklist_keywords() -> list:
    p = Path(__file__).parent / "blacklist.txt"
    if not p.exists():
        return []
    return [line.strip() for line in p.read_text().splitlines()
            if line.strip() and not line.startswith("#")]


def load_blacklist_topics() -> list:
    p = Path(__file__).parent / "blacklist_topics.txt"
    if not p.exists():
        return []
    return [line.strip() for line in p.read_text().splitlines()
            if line.strip() and not line.startswith("#")]


def keyword_blacklist_hit(text: str, keywords: list) -> bool:
    for kw in keywords:
        if kw.lower() in text.lower():
            return True
    return False


# ==================== Step 1: Fetch ====================

def step_fetch() -> list:
    cached = load_cache("fetch")
    if cached:
        logger.info("Step 1: Using cached fetch results")
        return cached.get("candidates", [])

    logger.info("Step 1: Fetching RSS feeds...")
    rss_results = fetch_rss_feeds(since_hours=48)
    logger.info(f"RSS returned {len(rss_results)} entries")

    failed_urls = load_failed_urls()
    candidates = []
    seen_urls = set()

    for entry in rss_results:
        url = entry["url"]
        if url in seen_urls:
            continue
        seen_urls.add(url)

        article_id = url_to_id(url)
        if article_exists(article_id):
            continue

        if url in failed_urls:
            logger.debug(f"Skipping previously failed URL: {url}")
            continue

        text, metadata, error = jina.fetch(url)
        provider_used = "jina"
        if not text:
            logger.debug(f"Jina failed for {url}, trying readability: {error}")
            text, metadata, error = readability.fetch(url)
            provider_used = "readability"

        if not text:
            log_failed_url(url, error or "unknown", failed_urls.get(url, 0))
            logger.warning(f"All providers failed for {url}: {error}")
            continue

        if metadata.word_count < SCREEN_MIN_WORDS:
            logger.debug(f"Too short ({metadata.word_count} words): {metadata.title}")
            continue

        candidate = {
            "id": article_id,
            "url": url,
            "source_name": entry["source_name"],
            "source_id": entry.get("source_id", ""),
            "title_en": metadata.title,
            "text_en": text,
            "word_count": metadata.word_count,
            "published_at": entry.get("published_at"),
            "author": metadata.author,
        }
        candidates.append(candidate)
        logger.info(f"  {provider_used}: [{entry['source_name']}] {metadata.title[:60]} ({metadata.word_count} words)")

    result = {"candidates": candidates}
    save_cache("fetch", result)
    logger.info(f"Step 1 done: {len(candidates)} candidates")
    return candidates


# ==================== Step 2: Screen ====================

def step_screen(candidates: list) -> list:
    cached = load_cache("screen")
    if cached:
        logger.info("Step 2: Using cached screen results")
        return cached.get("passed", [])

    logger.info(f"Step 2: Screening {len(candidates)} candidates...")
    keywords = load_blacklist_keywords()
    topics = load_blacklist_topics()
    passed = []

    for c in candidates:
        text = c["text_en"]

        if keyword_blacklist_hit(text, keywords):
            logger.info(f"  SKIP keyword: {c['title_en'][:60]}")
            continue

        if topics:
            from ai_client import semantic_blacklist_check
            hit, topic = semantic_blacklist_check(c["title_en"], text[:500], topics)
            if hit:
                logger.info(f"  SKIP semantic ({topic}): {c['title_en'][:60]}")
                continue

        passed.append(c)

    result = {"passed": passed}
    save_cache("screen", result)
    logger.info(f"Step 2 done: {len(passed)} passed screening")
    return passed


# ==================== Step 3: Curate (v2 section-based) ====================

def _load_sections() -> list:
    import yaml
    from config import SECTIONS_FILE
    with open(SECTIONS_FILE) as f:
        data = yaml.safe_load(f)
    sections = data.get("sections", {})
    # Inject section id into each section dict
    for sid, cfg in sections.items():
        cfg["id"] = sid
    return sections


def step_curate(passed: list) -> list:
    cached = load_cache("curate")
    if cached:
        logger.info("Step 3: Using cached curation results")
        return cached.get("selected", [])

    logger.info(f"Step 3: Curating {len(passed)} candidates into sections...")
    sections = _load_sections()
    from ai_client import pick_for_section

    selected = []
    used_ids = set()
    section_results = {}  # {section_id: candidate}

    for section_id, cfg in sections.items():
        if section_id == "wildcard":
            continue  # Do wildcard last

        eligible = [
            c for c in passed
            if c.get("source_id") in cfg.get("sources", [])
            and c["id"] not in used_ids
        ]

        if not eligible:
            logger.info(f"  [{section_id}] 无合适候选，跳过")
            continue

        # Limit candidate pool to 8, weighted by source weight
        from providers.rss_feed import load_sources as _ls
        sources = {s["source_id"]: s for s in _ls()}
        if len(eligible) > 8:
            scored = [(sources.get(c.get("source_id", ""), {}).get("weight", 1), c) for c in eligible]
            scored.sort(reverse=True, key=lambda x: x[0])
            eligible = [s[1] for s in scored[:8]]

        logger.info(f"  [{section_id}] {cfg['emoji']}{cfg['name']}: {len(eligible)} eligible")
        result = pick_for_section(cfg, eligible)
        if result:
            result["section_id"] = section_id
            selected.append(result)
            used_ids.add(result["id"])
            section_results[section_id] = result
            logger.info(f"    -> {result['title_en'][:50]}")

    # Wildcard: pick from remaining, avoiding topic overlap
    wildcard_cfg = sections.get("wildcard")
    if wildcard_cfg:
        used_topics = []
        for c in selected:
            used_topics.extend(c.get("topic_keywords", []))
        remaining = [c for c in passed if c["id"] not in used_ids]
        if remaining:
            if len(remaining) > 8:
                random.shuffle(remaining)
                remaining = remaining[:8]
            logger.info(f"  [wildcard] {wildcard_cfg['emoji']}{wildcard_cfg['name']}: {len(remaining)} remaining")
            result = pick_for_section(wildcard_cfg, remaining)
            if result:
                result["section_id"] = "wildcard"
                selected.append(result)
                section_results["wildcard"] = result
                logger.info(f"    -> {result['title_en'][:50]}")

    result = {"selected": selected, "sections": section_results}
    save_cache("curate", result)
    logger.info(f"Step 3 done: {len(selected)} articles across {len(section_results)} sections")
    return selected


# ==================== Step 4: Translate ====================

def step_translate(selected: list) -> list:
    cached = load_cache("translate")
    if cached:
        logger.info("Step 4: Using cached translation results")
        return cached.get("translated", [])

    logger.info(f"Step 4: Translating {len(selected)} articles...")

    to_translate = []
    skipped_long = []
    for c in selected:
        if c["word_count"] > MAX_ARTICLE_WORDS:
            skipped_long.append(c)
            logger.info(f"  SKIP long ({c['word_count']} words): {c['title_en'][:60]}")
        else:
            to_translate.append(c)

    if skipped_long:
        _log_line(f"Skipped {len(skipped_long)} super-long articles")

    from ai_client import translate_article, TRANSLATION_PROMPT_VERSION

    translated = []
    total_tokens = 0
    with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as executor:
        futures = {executor.submit(_translate_one, c): c for c in to_translate}

        for future in as_completed(futures):
            c = futures[future]
            try:
                zh_text, usage = future.result()
                # Rate-limit delay for cloud APIs
                if MAX_CONCURRENCY == 1:
                    time.sleep(5)
                if zh_text:
                    word_count_zh = len(zh_text.replace(" ", "").replace("\n", ""))
                    c["content_zh"] = zh_text
                    c["word_count_zh"] = word_count_zh
                    c["translation_model"] = "deepseek-chat"
                    c["prompt_version"] = TRANSLATION_PROMPT_VERSION
                    c["usage"] = usage
                    translated.append(c)
                    if usage:
                        total_tokens += usage.get("total_tokens", 0)
                    logger.info(f"  OK [{c['source_name']}] {c['title_en'][:40]} -> {word_count_zh} zh chars")
                else:
                    logger.error(f"  FAIL: {c['title_en'][:60]}")
            except Exception as e:
                logger.error(f"  ERROR: {c['title_en'][:60]}: {e}")

    # Log token usage
    _log_usage(total_tokens)

    result = {"translated": translated, "skipped_long": len(skipped_long)}
    save_cache("translate", result)
    logger.info(f"Step 4 done: {len(translated)} translated, {total_tokens} tokens")
    return translated


def _translate_one(c: dict) -> Tuple[Optional[str], Optional[dict]]:
    from ai_client import translate_article
    for attempt in range(1, MAX_RETRIES + 1):
        result, usage = translate_article(c["text_en"])
        if result:
            return result, usage
        wait = 2 ** attempt
        logger.warning(f"Retry {attempt}/{MAX_RETRIES} after {wait}s: {c['title_en'][:40]}")
        time.sleep(wait)
    return None, None


# ==================== Step 5: Review ====================

def step_review(translated: list) -> list:
    cached = load_cache("review")
    if cached:
        logger.info("Step 5: Using cached review results")
        return cached.get("approved", [])

    logger.info(f"Step 5: Reviewing {len(translated)} translations...")

    from ai_client import review_translation

    approved = []
    demoted = []

    for c in translated:
        demote_reasons = []

        if c["word_count_zh"] < TRANSLATED_MIN_CHARS:
            demote_reasons.append(f"word_count_zh={c['word_count_zh']} < {TRANSLATED_MIN_CHARS}")

        original_sample = c["text_en"][:2000]
        scores = review_translation(c["content_zh"], original_sample)

        if scores:
            c["quality_score"] = scores
            completeness = scores.get("completeness", 0)
            composite = (scores.get("terms", 0) + scores.get("fluency", 0) + completeness) / 3

            if completeness < 5:
                demote_reasons.append(f"completeness={completeness}")
            if composite < 6:
                demote_reasons.append(f"composite={composite:.1f}")
        else:
            c["quality_score"] = {"terms": 5, "fluency": 5, "completeness": 5, "note": "review_failed"}
            logger.warning(f"  Review call failed for {c['title_en'][:40]}")

        # Spoiler check for screen section
        if c.get("section_id") == "screen":
            from ai_client import spoiler_check
            spoiler = spoiler_check(c["content_zh"])
            c["has_spoiler"] = spoiler.get("has_spoiler", False)
            if c["has_spoiler"]:
                logger.info(f"  SPOILER [{spoiler.get('type', '?')}] {c['title_en'][:40]}")

        if demote_reasons:
            c["demote_reasons"] = demote_reasons
            demoted.append(c)
            logger.info(f"  DEMOTE {c['title_en'][:40]}: {', '.join(demote_reasons)}")
        else:
            approved.append(c)
            logger.info(f"  APPROVE [{c.get('quality_score', {})}] {c['title_en'][:40]}")

    if demoted:
        pool_dir = Path(__file__).parent / "data" / "candidate_pool"
        pool_dir.mkdir(exist_ok=True)
        for c in demoted:
            (pool_dir / f"{c['id']}.json").write_text(json.dumps(c, ensure_ascii=False, indent=2))

    result = {"approved": approved, "demoted": len(demoted)}
    save_cache("review", result)
    logger.info(f"Step 5 done: {len(approved)} approved, {len(demoted)} demoted to pool")
    return approved


# ==================== Step 6: Publish ====================

def _load_candidate_pool(min_chars: int = 3000) -> list:
    pool_dir = Path(__file__).parent / "data" / "candidate_pool"
    if not pool_dir.exists():
        return []
    articles = []
    for f in pool_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            if data.get("word_count_zh", 0) >= min_chars:
                articles.append(data)
        except json.JSONDecodeError:
            pass
    return sorted(articles, key=lambda a: a.get("quality_score", {}).get("completeness", 0), reverse=True)


def step_publish(approved: list, send_epub_flag: bool = True) -> Optional[dict]:
    cached = load_cache("publish")
    if cached:
        logger.info("Step 6: Issue already published today")
        return cached

    logger.info(f"Step 6: Publishing issue with {len(approved)} approved articles...")

    final_articles = list(approved)
    fallback_note = ""

    if len(final_articles) < MIN_ARTICLES_PER_ISSUE:
        pool = _load_candidate_pool()
        needed = MIN_ARTICLES_PER_ISSUE - len(final_articles)
        existing_ids = {c["id"] for c in final_articles}
        for p in pool:
            if p["id"] not in existing_ids and needed > 0:
                final_articles.append(p)
                existing_ids.add(p["id"])
                needed -= 1

        if len(final_articles) <= 2:
            fallback_note = "今日以精选往期为主"
        elif len(final_articles) < MIN_ARTICLES_PER_ISSUE:
            fallback_note = "今日篇目较少"
        logger.info(f"  Supplemented from pool, now {len(final_articles)} articles")

    # Generate editor note
    articles_info = []
    for a in final_articles:
        articles_info.append({
            "title_zh": a.get("title_en", "Untitled"),
            "source": a.get("source_name", ""),
            "reason": a.get("curation_reason", ""),
        })
    from ai_client import generate_editor_note
    from config import EDITOR_BANNED_WORDS
    editor_note = generate_editor_note(articles_info, EDITOR_BANNED_WORDS)

    # Build issue
    issue = {
        "date": TODAY,
        "articles": [a["id"] for a in final_articles],
        "editor_note": editor_note,
        "stats": {
            "total_articles": len(final_articles),
            "fallback_note": fallback_note,
            "section_distribution": {c.get("section_id", "unknown"): c.get("source_name", "") for c in final_articles},
        },
    }

    # Save articles as JSON
    articles_dir = Path(__file__).parent / "data" / "articles"
    for a in final_articles:
        article = Article(
            id=a["id"],
            title_zh=a.get("title_en", "Untitled"),
            source=a.get("source_name", ""),
            source_url=a.get("url", ""),
            author=a.get("author", ""),
            summary_zh=a.get("curation_reason", ""),
            content_zh=a.get("content_zh", ""),
            word_count_zh=a.get("word_count_zh", 0),
            original_word_count=a.get("word_count", 0),
            translation_model=a.get("translation_model", ""),
            prompt_version=a.get("prompt_version", ""),
            quality_score=a.get("quality_score", {}),
            fetched_at=datetime.now().isoformat(),
        )
        (articles_dir / f"{a['id']}.json").write_text(
            json.dumps(article.to_dict(), ensure_ascii=False, indent=2)
        )

    # Save issue JSON
    issues_dir = Path(__file__).parent / "data" / "issues"
    (issues_dir / f"{TODAY}.json").write_text(
        json.dumps(issue, ensure_ascii=False, indent=2)
    )

    # Write to SQLite
    for a in final_articles:
        article_data = {
            "id": a["id"],
            "title_zh": a.get("title_en", "Untitled"),
            "source": a.get("source_name", ""),
            "source_url": a.get("url", ""),
            "author": a.get("author", ""),
            "summary_zh": a.get("curation_reason", ""),
            "word_count_zh": a.get("word_count_zh", 0),
            "original_word_count": a.get("word_count", 0),
            "translation_model": a.get("translation_model", ""),
            "prompt_version": a.get("prompt_version", ""),
            "quality_score": a.get("quality_score", {}),
            "fetched_at": a.get("fetched_at", datetime.now().isoformat()),
            "tags": a.get("topic_keywords", [a.get("source_id", "")]),
            "section_id": a.get("section_id", ""),
            "has_spoiler": a.get("has_spoiler", False),
            "topic_keywords": a.get("topic_keywords", []),
        }
        insert_article(article_data)
    insert_issue(issue)

    save_cache("publish", issue)

    # EPUB generation and send
    epub_sent = False
    if send_epub_flag and not issue_epub_sent(TODAY):
        epub_ok = _generate_and_send_epub(final_articles, issue)
        if epub_ok:
            mark_epub_sent(TODAY)
            epub_sent = True

    # Daily log
    _write_daily_log(issue, final_articles, epub_sent)

    # Alert checks
    _check_alerts(issue)

    logger.info(f"Step 6 done: Issue {TODAY} published ({len(final_articles)} articles, epub={epub_sent})")
    return issue


def _generate_and_send_epub(articles: list, issue: dict) -> bool:
    try:
        from sender import send_epub
        from ebooklib import epub as epub_lib

        book = epub_lib.EpubBook()
        book.set_identifier(f"sanqian-{TODAY}")
        book.set_title(f"三千要看 {TODAY}")
        book.set_language("zh-CN")
        book.add_author("三千要看")

        cover_path = _generate_cover(articles)
        if cover_path:
            with open(cover_path, "rb") as f:
                book.set_cover("cover.jpg", f.read())

        css = """body{font-family:serif;line-height:1.8}
h2{text-align:center;margin:1em 0 .5em}
p{text-indent:2em;margin:0 0 .8em;text-align:justify}
.source-tag{text-align:center;font-size:.8em;color:#888}"""
        nav_css = epub_lib.EpubItem(uid="style", file_name="style/main.css",
                                    media_type="text/css", content=css.encode("utf-8"))
        book.add_item(nav_css)

        spine, toc = [], []

        note_paragraphs = "".join(f"<p>{p}</p>" for p in issue['editor_note'].split('\n') if p.strip())
        note_html = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html><html xmlns="http://www.w3.org/1999/xhtml" xml:lang="zh-CN">
<head><title>编者按</title></head><body>
<h2>编者按</h2>
<div class="source-tag">{TODAY}</div>
{note_paragraphs}
</body></html>"""
        note_chap = epub_lib.EpubHtml(title="编者按", file_name="intro.xhtml", lang="zh-CN")
        note_chap.content = note_html.encode("utf-8"); note_chap.add_item(nav_css)
        book.add_item(note_chap); spine.append(note_chap); toc.append(note_chap)

        for i, a in enumerate(articles):
            title = a.get("title_en", f"Article {i}")
            body_parts = "\n".join(f"<p>{p.strip()}</p>" for p in a.get("content_zh", "").split('\n') if p.strip())
            html = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html><html xmlns="http://www.w3.org/1999/xhtml" xml:lang="zh-CN">
<head><title>{title}</title></head><body>
<h2>{title}</h2>
<div class="source-tag">{a.get('source_name','')}</div>
{body_parts}
</body></html>"""
            chap = epub_lib.EpubHtml(title=title, file_name=f"article_{i:03d}.xhtml", lang="zh-CN")
            chap.content = html.encode("utf-8"); chap.add_item(nav_css)
            book.add_item(chap); spine.append(chap); toc.append(chap)

        book.spine = spine; book.toc = toc
        book.add_item(epub_lib.EpubNcx()); book.add_item(epub_lib.EpubNav())

        epub_path = Path(__file__).parent / "output" / f"三千要看-{TODAY}.epub"
        epub_lib.write_epub(str(epub_path), book)
        logger.info(f"EPUB: {epub_path}")

        from config import KINDLE_EMAIL
        if KINDLE_EMAIL:
            return send_epub(str(epub_path))
        return False
    except Exception as e:
        logger.error(f"EPUB generation/send failed: {e}")
        return False


def _generate_cover(articles: list) -> Optional[str]:
    try:
        from PIL import Image, ImageDraw, ImageFont
        cover_path = Path(__file__).parent / "output" / f"cover-{TODAY}.jpg"
        img = Image.new("RGB", (600, 800), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        try:
            font_title = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 36)
            font_body = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 18)
        except (OSError, IOError):
            font_title = ImageFont.load_default()
            font_body = ImageFont.load_default()

        draw.text((300, 60), "三千要看", fill=(0, 0, 0), font=font_title, anchor="mt")
        draw.text((300, 110), TODAY, fill=(128, 128, 128), font=font_body, anchor="mt")

        # Cat ASCII art
        cat_lines = [
            "      ／l、",
            "    （ﾟ､ ｡ ７",
            "      l  ~ヽ",
            "      じしf_,)ノ",
        ]
        cat_y = 160
        for line in cat_lines:
            draw.text((300, cat_y), line, fill=(180, 180, 180), font=font_body, anchor="mt")
            cat_y += 28

        y = 290
        for a in articles[:10]:
            title = a.get("title_en", "Untitled")[:25]
            draw.text((50, y), f"· {title}", fill=(0, 0, 0), font=font_body)
            y += 40

        img.save(str(cover_path))
        return str(cover_path)
    except Exception as e:
        logger.warning(f"Cover generation failed: {e}")
        return None


def _write_daily_log(issue: dict, articles: list, epub_sent: bool):
    log_file = Path(__file__).parent / "data" / "daily.log"
    lines = [
        f"[{datetime.now().isoformat()}] Issue {TODAY}",
        f"  Articles: {len(articles)}",
        f"  EPUB sent: {epub_sent}",
        f"  Editor note: {issue['editor_note'][:80]}...",
        f"  Sections: {issue['stats'].get('section_distribution', {})}",
    ]
    with open(log_file, "a") as f:
        f.write("\n".join(lines) + "\n")


def _check_alerts(issue: dict):
    if len(issue["articles"]) == 0:
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        yest_issue = get_issue(yesterday)
        if not yest_issue or len(yest_issue.get("articles", [])) == 0:
            from config import KINDLE_EMAIL, SMTP_USER, SMTP_HOST, SMTP_PORT, SMTP_PASS
            if KINDLE_EMAIL and SMTP_USER:
                import smtplib
                from email.mime.text import MIMEText
                try:
                    msg = MIMEText("三千要看连续两天未能生成内容。请检查 RSS 源和 DeepSeek API。", "plain", "utf-8")
                    msg["Subject"] = "[三千要看] 连续两天零篇告警"
                    msg["From"] = SMTP_USER
                    msg["To"] = SMTP_USER
                    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as s:
                        s.starttls(); s.login(SMTP_USER, SMTP_PASS)
                        s.sendmail(SMTP_USER, SMTP_USER, msg.as_string())
                    logger.warning("Alert sent: 2 consecutive days with 0 articles")
                except Exception as e:
                    logger.error(f"Failed to send alert: {e}")


def _log_line(msg: str):
    log_file = Path(__file__).parent / "data" / "daily.log"
    with open(log_file, "a") as f:
        f.write(f"[{datetime.now().isoformat()}] {msg}\n")


def _log_usage(total_tokens: int):
    usage_file = Path(__file__).parent / "data" / "usage.jsonl"
    record = {"date": TODAY, "total_tokens": total_tokens, "budget": DAILY_TOKEN_BUDGET}
    with open(usage_file, "a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    if total_tokens > DAILY_TOKEN_BUDGET * 0.8:
        from config import KINDLE_EMAIL, SMTP_USER, SMTP_HOST, SMTP_PORT, SMTP_PASS
        if KINDLE_EMAIL and SMTP_USER:
            import smtplib
            from email.mime.text import MIMEText
            try:
                msg = MIMEText(
                    f"今日 token 消耗 {total_tokens}，已超过预算 ({DAILY_TOKEN_BUDGET}) 的 80%。",
                    "plain", "utf-8"
                )
                msg["Subject"] = "[三千要看] Token 预算告警"
                msg["From"] = SMTP_USER; msg["To"] = SMTP_USER
                with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as s:
                    s.starttls(); s.login(SMTP_USER, SMTP_PASS)
                    s.sendmail(SMTP_USER, SMTP_USER, msg.as_string())
                logger.warning("Token budget alert sent")
            except Exception as e:
                logger.error(f"Failed to send token alert: {e}")


# ==================== Main Entry ====================

def run_pipeline(send_epub: bool = True) -> Optional[dict]:
    """Run full pipeline with checkpoint/resume."""
    clear_stale_cache()

    if load_cache("publish"):
        logger.info(f"Issue {TODAY} already published. Use --force to re-run.")
        return load_cache("publish")

    try:
        candidates = step_fetch()
    except Exception as e:
        logger.error(f"Step 1 (fetch) failed: {e}")
        return None

    if not candidates:
        logger.warning("No candidates from fetch, aborting")
        return None

    try:
        passed = step_screen(candidates)
    except Exception as e:
        logger.error(f"Step 2 (screen) failed: {e}")
        return None

    if not passed:
        logger.warning("No articles passed screening")
        return None

    try:
        selected = step_curate(passed)
    except Exception as e:
        logger.error(f"Step 3 (curate) failed: {e}, using all passed")
        selected = passed[:8]

    try:
        translated = step_translate(selected)
    except Exception as e:
        logger.error(f"Step 4 (translate) failed: {e}")
        translated = []

    if not translated:
        logger.warning("No articles translated successfully")
        return None

    try:
        approved = step_review(translated)
    except Exception as e:
        logger.error(f"Step 5 (review) failed: {e}, approving all")
        approved = translated

    try:
        issue = step_publish(approved, send_epub_flag=send_epub)
    except Exception as e:
        logger.error(f"Step 6 (publish) failed: {e}")
        return None

    return issue


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="三千要看 Pipeline")
    parser.add_argument("--no-send", action="store_true", help="Skip EPUB send")
    parser.add_argument("--force", action="store_true", help="Ignore cache, re-run all steps")
    parser.add_argument("--step", choices=["fetch","screen","curate","translate","review","publish"], help="Run single step")
    args = parser.parse_args()

    if args.force:
        cache_today = CACHE_DIR / TODAY
        if cache_today.exists():
            shutil.rmtree(cache_today)
            logger.info(f"Cleared cache for {TODAY}")

    if args.step == "fetch":
        step_fetch()
    elif args.step == "screen":
        cached = load_cache("fetch")
        if cached:
            step_screen(cached.get("candidates", []))
    elif args.step == "curate":
        cached = load_cache("screen")
        if cached:
            step_curate(cached.get("passed", []))
    elif args.step == "translate":
        cached = load_cache("curate")
        if cached:
            step_translate(cached.get("selected", []))
    elif args.step == "review":
        cached = load_cache("translate")
        if cached:
            step_review(cached.get("translated", []))
    elif args.step == "publish":
        cached = load_cache("review")
        if cached:
            step_publish(cached.get("approved", []), send_epub_flag=not args.no_send)
    else:
        run_pipeline(send_epub=not args.no_send)
