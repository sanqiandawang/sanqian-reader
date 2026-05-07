#!/usr/bin/env python3
"""Generate static HTML site from pipeline data for GitHub Pages."""
import json
import os
from pathlib import Path
from datetime import date

ROOT = Path(__file__).parent
SITE = ROOT / "site"
DATA = ROOT / "data"

CSS = """body{max-width:720px;margin:0 auto;padding:24px 18px;background:#fff;color:#000;font-size:18px;line-height:1.6;font-family:serif}
h1{text-align:center;font-size:1.6em;margin-bottom:.2em}
.date{text-align:center;color:#888;font-size:.9em;margin-bottom:1.5em}
.editor-note{border-left:3px solid #333;padding:.8em 1.2em;margin:1.5em 0;background:#fafafa;font-size:.95em;line-height:1.7}
.article-list{list-style:none;padding:0}
.article-item{padding:1em 0;border-bottom:1px solid #eee}
.article-item a{text-decoration:none;color:#000}
.article-item .title{font-size:1.1em;font-weight:bold;display:block}
.article-item .meta{color:#888;font-size:.85em;margin-top:.3em}
.article-item .summary{color:#555;font-size:.9em;margin-top:.4em;line-height:1.5}
.footer{text-align:center;margin-top:2em;font-size:.85em}
.footer a{color:#888}
.cat-art{text-align:center;color:#bbb;font-size:.7em;line-height:1.3;margin:1em 0}
.content{line-height:1.8}
.content p{text-indent:2em;margin:.4em 0}
.content h2,.content h3{margin:1.2em 0 .4em}
.content blockquote{border-left:3px solid #ccc;padding:.3em 1em;margin:.5em 0;color:#555}
.article-header{margin-bottom:1.5em;border-bottom:1px solid #ccc;padding-bottom:.8em}
.article-header h1{font-size:1.4em;margin-bottom:.2em}
.article-header .meta{color:#888;font-size:.85em}
.pagination{margin:2em 0;text-align:center;font-size:.95em}
.pagination a{padding:.3em .8em;text-decoration:none;color:#000;border:1px solid #ccc}
.pagination span{padding:.3em .8em;color:#888}
.nav-bottom{margin-top:2em;padding-top:1em;border-top:1px solid #eee;text-align:center;font-size:.95em}
.nav-bottom a{text-decoration:none;color:#000;padding:.3em .8em;border:1px solid #ccc}
.done-link{color:#888;font-size:.85em}
.cat-footer{text-align:center;color:#ddd;font-size:.55em;line-height:1.2;margin:3em 0 1em}
.issue{margin-bottom:2em}
.issue-date{font-size:1.1em;font-weight:bold;border-bottom:1px solid #ccc;padding-bottom:.3em;margin-bottom:.5em}
.issue-note{color:#555;font-size:.9em;margin-bottom:.5em;line-height:1.5}
.issue a{text-decoration:none;color:#000}
.issue ul{list-style:none;padding:0;margin:0}
.issue li{padding:.2em 0;font-size:.95em}"""

CAT_ART = """      ／l、
    （ﾟ､ ｡ ７
      l  ~ヽ
      じしf_,)ノ"""

PAGE_CHARS = 2000


def markdown_to_html(text: str) -> str:
    import re
    lines = text.split('\n')
    result = []
    in_list = False
    list_type = None

    def _inline(t):
        t = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', t)
        t = re.sub(r'__(.+?)__', r'<strong>\1</strong>', t)
        t = re.sub(r'\*(.+?)\*', r'<em>\1</em>', t)
        t = re.sub(r'_(.+?)_', r'<em>\1</em>', t)
        t = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', t)
        t = re.sub(r'`([^`]+)`', r'<code>\1</code>', t)
        return t

    for line in lines:
        s = line.strip()
        if not s:
            if in_list:
                result.append(f'</{list_type}>')
                in_list = False
                list_type = None
            result.append('')
            continue
        if s.startswith('### '):
            result.append(f'<h3>{_inline(s[4:])}</h3>')
        elif s.startswith('## '):
            result.append(f'<h3>{_inline(s[3:])}</h3>')
        elif s.startswith('# '):
            result.append(f'<h2>{_inline(s[2:])}</h2>')
        elif s.startswith('> '):
            result.append(f'<blockquote>{_inline(s[2:])}</blockquote>')
        elif s in ('---', '***', '___'):
            result.append('<hr>')
        elif re.match(r'^[-*+]\s', s):
            if not in_list or list_type != 'ul':
                if in_list: result.append(f'</{list_type}>')
                result.append('<ul>')
                in_list = True; list_type = 'ul'
            item = re.sub(r'^[-*+]\s', '', s)
            result.append(f'<li>{_inline(item)}</li>')
        elif re.match(r'^\d+\.\s', s):
            if not in_list or list_type != 'ol':
                if in_list: result.append(f'</{list_type}>')
                result.append('<ol>')
                in_list = True; list_type = 'ol'
            item = re.sub(r'^\d+\.\s', '', s)
            result.append(f'<li>{_inline(item)}</li>')
        else:
            if in_list:
                result.append(f'</{list_type}>')
                in_list = False; list_type = None
            result.append(f'<p>{_inline(s)}</p>')

    if in_list:
        result.append(f'</{list_type}>')
    return '\n'.join(result)


def paginate_html(html: str, chars_per_page: int = PAGE_CHARS) -> list:
    import re
    blocks = re.split(r'(</(?:p|h[234]|blockquote|li|ul|ol)>\s*)', html)
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
        visible = len(re.sub(r'<[^>]+>', '', p))
        if current_len + visible > chars_per_page and current:
            pages.append('\n'.join(current))
            current = []
            current_len = 0
        current.append(p)
        current_len += visible
    if current:
        pages.append('\n'.join(current))
    return pages or ['']


def build():
    SITE.mkdir(exist_ok=True)
    (SITE / "articles").mkdir(exist_ok=True)

    # Scan issues
    issues_dir = DATA / "issues"
    issues = []
    if issues_dir.exists():
        for f in sorted(issues_dir.glob("*.json"), reverse=True):
            data = json.loads(f.read_text())
            data["_date"] = f.stem
            issues.append(data)

    today_str = date.today().isoformat()
    latest_issue = issues[0] if issues else None

    # === index.html ===
    index_html = build_index(latest_issue, today_str)
    (SITE / "index.html").write_text(index_html)

    # === Article pages ===
    articles_dir = DATA / "articles"
    if latest_issue:
        for aid in latest_issue.get("articles", []):
            article_json = articles_dir / f"{aid}.json"
            if not article_json.exists():
                continue
            article = json.loads(article_json.read_text())
            article_dir = SITE / "articles" / aid
            article_dir.mkdir(exist_ok=True)
            content_html = markdown_to_html(article.get("content_zh", ""))
            pages = paginate_html(content_html)
            for pi, page_html in enumerate(pages, 1):
                next_id = None
                ids = latest_issue.get("articles", [])
                try:
                    idx = ids.index(aid)
                    if idx + 1 < len(ids):
                        next_id = ids[idx + 1]
                except ValueError:
                    pass
                page_file = article_dir / f"page{pi}.html" if pi > 1 else article_dir / "index.html"
                page_file.write_text(build_article_page(article, page_html, pi, len(pages), next_id))

    # === archive.html ===
    archive_html = build_archive(issues)
    (SITE / "archive.html").write_text(archive_html)

    print(f"Static site built: {len(list(SITE.rglob('*.html')))} pages")


def build_index(issue, today_str):
    if not issue:
        return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><title>三千要看</title><style>{CSS}</style></head><body>
<h1>三千要看</h1><div class="date">{today_str}</div>
<pre class="cat-art">{CAT_ART}</pre>
<p style="text-align:center;color:#888;margin-top:2em">今天还没有内容，稍后回来看看。</p>
<div class="footer"><a href="/archive.html">往期</a></div>
</body></html>"""

    articles_dir = DATA / "articles"
    items = ""
    for aid in issue.get("articles", []):
        ajson = articles_dir / f"{aid}.json"
        if not ajson.exists():
            continue
        a = json.loads(ajson.read_text())
        title = a.get("title_zh") or aid
        source = a.get("source", "")
        wc = a.get("word_count_zh", 0)
        summary = a.get("summary_zh", "")
        items += f"""<li class="article-item">
  <a href="/articles/{aid}/">
    <span class="title">{title}</span>
    <span class="meta">{source} | {wc} 字</span>
    <span class="summary">{summary}</span>
  </a>
</li>"""

    fb = issue.get("stats", {}).get("fallback_note", "")
    fb_html = f'<p style="color:#c00;text-align:center">{fb}</p>' if fb else ""

    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><title>三千要看 — {issue["_date"]}</title><style>{CSS}</style></head><body>
<h1>三千要看</h1><div class="date">{issue["_date"]}</div>
<pre class="cat-art">{CAT_ART}</pre>
<div class="editor-note">{issue.get("editor_note", "")}</div>
{fb_html}
<ul class="article-list">{items}</ul>
<div class="footer"><a href="/archive.html">往期</a></div>
</body></html>"""


def build_article_page(article, content_html, page, total, next_id):
    title = article.get("title_zh") or article.get("id", "")
    source = article.get("source", "")
    wc = article.get("word_count_zh", 0)

    prev_link = ""
    if page > 1:
        prev_url = f"page{page-1}.html" if page > 2 else ""
        prev_link = f'<a href="{prev_url}">上一页</a>'

    next_link = ""
    if page < total:
        next_url = f"page{page+1}.html"
        next_link = f'<a href="{next_url}">下一页</a>'

    is_last = page == total
    done_link = ""
    if is_last:
        if next_id:
            done_link = f'| <a class="done-link" href="/articles/{next_id}/">下一篇</a>'
        else:
            done_link = '| <span class="done-link">已读完 ✓</span>'

    cat = f'<pre class="cat-footer">{CAT_ART}</pre>'

    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><title>{title} — 三千要看</title><style>{CSS}</style></head><body>
<div class="article-header"><h1>{title}</h1><div class="meta">{source} | {wc} 字</div></div>
<div class="content">{content_html}</div>
<div class="pagination">{prev_link} <span>第 {page} / {total} 页</span> {next_link}</div>
<div class="nav-bottom"><a href="/">回首页</a> {done_link}</div>
{cat}</body></html>"""


def build_archive(issues):
    items = ""
    for iss in issues:
        note = iss.get("editor_note", "")
        if len(note) > 120:
            note = note[:120] + "..."
        links = ""
        for aid in iss.get("articles", []):
            links += f'<li><a href="/articles/{aid}/">{aid}</a></li>'
        items += f"""<div class="issue">
<div class="issue-date">{iss["_date"]}</div>
<div class="issue-note">{note}</div>
<ul>{links}</ul>
</div>"""

    if not items:
        items = '<p style="text-align:center;color:#888">还没有往期内容。</p>'

    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><title>往期 — 三千要看</title><style>{CSS}</style></head><body>
<h1>往期</h1>
{items}
<div class="footer"><a href="/">回首页</a></div>
</body></html>"""


if __name__ == "__main__":
    build()
