#!/usr/bin/env python3
"""Generate static HTML site from pipeline data for GitHub Pages — v2 section-based."""
import json
import re
import yaml
from pathlib import Path
from datetime import date

ROOT = Path(__file__).parent
SITE = ROOT / "site"
DATA = ROOT / "data"
BASE = "/sanqian-reader"

CSS = """*{margin:0;padding:0;box-sizing:border-box}
body{max-width:680px;margin:0 auto;padding:48px 24px 72px;background:#fafaf8;color:#1a1a1a;font-size:17px;line-height:1.75;font-family:Georgia,"Noto Serif CJK SC","Source Han Serif SC",serif;-webkit-font-smoothing:antialiased}
@media(max-width:600px){body{padding:32px 16px 56px;font-size:16px}}

/* Masthead */
.masthead{text-align:center;margin-bottom:48px}
.masthead h1{font-size:2.2em;font-weight:400;letter-spacing:.04em;margin-bottom:6px;color:#111}
.masthead .date{font-size:.85em;color:#999;text-transform:uppercase;letter-spacing:.12em}
@media(max-width:600px){.masthead h1{font-size:1.7em}.masthead{margin-bottom:36px}}

/* Cat art */
.cat-art{text-align:center;color:#d4d4d0;font-size:.65em;line-height:1.3;margin:0 0 32px}

/* Editor note */
.editor-note{max-width:580px;margin:0 auto 48px;padding:0 0 0 20px;border-left:2px solid #d0d0cc;font-size:.92em;line-height:1.8;color:#555;font-style:italic}
@media(max-width:600px){.editor-note{margin-bottom:36px;padding-left:16px}}

/* Section cards */
.section-card{margin:0 0 40px;padding:36px 0 0;border-top:1px solid #e8e8e4}
.section-card:first-of-type{border-top:none;padding-top:0}
.section-card h2{font-size:1.05em;font-weight:400;color:#999;letter-spacing:.06em;text-transform:uppercase;margin-bottom:24px}
.section-card .article-item{margin-bottom:20px}
.section-card .article-item:last-child{margin-bottom:0}
.section-card .article-item a{display:block;text-decoration:none;color:#1a1a1a;padding:16px 0;border-bottom:1px solid #f0f0ec;transition:background .15s}
.section-card .article-item a:hover{background:#f5f5f0}
.section-card .title{font-size:1.15em;font-weight:600;line-height:1.45;display:block;margin-bottom:6px;color:#111}
.section-card .meta{font-size:.78em;color:#aaa;display:block;margin-bottom:4px}
.section-card .summary{font-size:.88em;color:#777;line-height:1.6;display:block}
@media(max-width:600px){.section-card{margin-bottom:32px;padding-top:28px}.section-card .title{font-size:1.05em}}

/* Article page */
.article-header{text-align:center;margin-bottom:40px;padding-bottom:24px;border-bottom:1px solid #e8e8e4}
.article-header h1{font-size:1.6em;font-weight:600;line-height:1.35;margin-bottom:10px;color:#111}
.article-header .meta{font-size:.82em;color:#aaa;letter-spacing:.04em}
@media(max-width:600px){.article-header h1{font-size:1.3em}}

/* Article body */
.content{line-height:1.85;font-size:1.05em}
.content p{margin:0 0 1.2em;text-indent:2em}
.content h2{font-size:1.25em;font-weight:600;margin:2em 0 .6em;color:#111}
.content h3{font-size:1.1em;font-weight:600;margin:1.6em 0 .5em;color:#333}
.content blockquote{margin:1.5em 0;padding:.8em 1.2em;border-left:2px solid #d0d0cc;color:#666;font-style:italic}
.content ul,.content ol{margin:1em 0;padding-left:1.5em}
.content li{margin:.4em 0}
.content hr{border:none;text-align:center;margin:2em 0}
.content hr::after{content:"· · ·";color:#ccc;font-size:1.2em}
.content strong{font-weight:700;color:#222}
.content a{color:#336;text-decoration:underline;text-underline-offset:2px}
.content code{font-size:.88em;background:#f5f5f0;padding:1px 5px;border-radius:3px}
@media(max-width:600px){.content{font-size:1em}.content p{text-indent:1.5em;margin-bottom:1em}}

/* Pagination */
.pagination{display:flex;justify-content:center;align-items:center;gap:16px;margin:48px 0 32px;font-size:.9em}
.pagination a{text-decoration:none;color:#1a1a1a;padding:8px 20px;border:1px solid #d0d0cc;border-radius:2px;transition:all .15s}
.pagination a:hover{border-color:#999;color:#000}
.pagination span{color:#bbb}

/* Nav bottom */
.nav-bottom{text-align:center;margin-top:40px;padding-top:28px;border-top:1px solid #e8e8e4;font-size:.88em}
.nav-bottom a{text-decoration:none;color:#555;padding:6px 16px;transition:color .15s}
.nav-bottom a:hover{color:#000}

/* Spoiler tag */
.spoiler-tag{display:inline-block;padding:1px 7px;border:1px solid #c44;color:#c44;font-size:.78em;margin-left:8px;letter-spacing:.04em}

/* Briefing card */
.briefing{margin:0 auto 48px;max-width:580px;padding:28px 28px 20px;background:#fff;border:1px solid #e0e0dc;border-radius:1px}
.briefing h2{font-size:.95em;font-weight:600;color:#888;letter-spacing:.08em;text-transform:uppercase;margin-bottom:20px}
.briefing ol{padding-left:0;list-style:none;counter-reset:briefing}
.briefing li{counter-increment:briefing;margin-bottom:18px;padding-bottom:18px;border-bottom:1px solid #f0f0ec}
.briefing li:last-child{border-bottom:none;margin-bottom:0;padding-bottom:0}
.briefing li::before{content:"0" counter(briefing);font-size:.7em;color:#ccc;display:block;margin-bottom:4px;letter-spacing:.06em}
.briefing h3{font-size:.95em;font-weight:600;line-height:1.45;margin:0 0 5px}
.briefing h3 a{color:#1a1a1a;text-decoration:none}
.briefing h3 a:hover{text-decoration:underline}
.briefing p{font-size:.85em;color:#666;line-height:1.65;margin:0}
.briefing small{font-size:.72em;color:#bbb}
@media(max-width:600px){.briefing{padding:20px 18px 16px;margin-bottom:36px}}

/* Archive */
.issue{margin-bottom:36px}
.issue-date{font-size:1em;font-weight:600;color:#111;margin-bottom:6px}
.issue-note{font-size:.85em;color:#888;margin-bottom:10px;line-height:1.6}
.issue ul{list-style:none;padding:0}
.issue li{padding:4px 0;font-size:.9em}
.issue a{color:#1a1a1a;text-decoration:none}
.issue a:hover{text-decoration:underline}

/* Footer */
.footer{text-align:center;margin-top:56px;padding-top:24px;border-top:1px solid #e8e8e4;font-size:.8em}
.footer a{color:#bbb;text-decoration:none;letter-spacing:.06em;transition:color .15s}
.footer a:hover{color:#555}

/* Cat footer */
.cat-footer{text-align:center;color:#e8e8e4;font-size:.5em;line-height:1.2;margin:56px 0 8px}
.push-container{margin:0 auto 48px;max-width:400px;text-align:center}
.cat-btn{background:#fff;border:1.5px solid #1a1a1a;padding:1rem 2rem;cursor:pointer;font-family:inherit;transition:all .2s;display:inline-flex;flex-direction:column;align-items:center;gap:.5rem;border-radius:2px}
.cat-btn:hover:not(:disabled){background:#1a1a1a;color:#fff}
.cat-btn:disabled{opacity:.5;cursor:not-allowed}
.cat-btn .cat-art{font-family:ui-monospace,"SF Mono",Menlo,monospace;font-size:.7rem;line-height:1.1;margin:0;white-space:pre;color:inherit}
.cat-btn .cat-label{font-size:.9rem;letter-spacing:.05em}
#push-status{margin-top:1rem;font-size:.85rem;color:#666;min-height:1.2em;line-height:1.5}
#push-status a{color:#336;text-decoration:underline}
.push-hint{font-size:.72rem;color:#bbb;margin-top:.5rem;line-height:1.5}"""

CAT_ART = """      ／l、
    （ﾟ､ ｡ ７
      l  ~ヽ
      じしf_,)ノ"""

PAGE_CHARS = 2000


def load_section_meta():
    """Load section emoji and name mapping from sections.yaml."""
    sec_file = ROOT / "sections.yaml"
    if not sec_file.exists():
        return {}
    with open(sec_file) as f:
        data = yaml.safe_load(f)
    meta = {}
    for sid, cfg in data.get("sections", {}).items():
        meta[sid] = {"name": cfg["name"], "emoji": cfg["emoji"]}
    return meta


def markdown_to_html(text: str) -> str:
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
                in_list = False; list_type = None
            result.append('')
            continue
        if s.startswith('### '): result.append(f'<h3>{_inline(s[4:])}</h3>')
        elif s.startswith('## '): result.append(f'<h3>{_inline(s[3:])}</h3>')
        elif s.startswith('# '): result.append(f'<h2>{_inline(s[2:])}</h2>')
        elif s.startswith('> '): result.append(f'<blockquote>{_inline(s[2:])}</blockquote>')
        elif s in ('---', '***', '___'): result.append('<hr>')
        elif re.match(r'^[-*+]\s', s):
            if not in_list or list_type != 'ul':
                if in_list: result.append(f'</{list_type}>')
                result.append('<ul>'); in_list = True; list_type = 'ul'
            result.append(f'<li>{_inline(re.sub(r"^[-*+]\s", "", s))}</li>')
        elif re.match(r'^\d+\.\s', s):
            if not in_list or list_type != 'ol':
                if in_list: result.append(f'</{list_type}>')
                result.append('<ol>'); in_list = True; list_type = 'ol'
            result.append(f'<li>{_inline(re.sub(r"^\d+\.\s", "", s))}</li>')
        else:
            if in_list: result.append(f'</{list_type}>'); in_list = False; list_type = None
            result.append(f'<p>{_inline(s)}</p>')
    if in_list: result.append(f'</{list_type}>')
    return '\n'.join(result)


def paginate_html(html: str, chars_per_page: int = PAGE_CHARS) -> list:
    blocks = re.split(r'(</(?:p|h[234]|blockquote|li|ul|ol)>\s*)', html)
    paragraphs = []
    i = 0
    while i < len(blocks):
        if i + 1 < len(blocks) and re.match(r'</(?:p|h[234]|blockquote|li|ul|ol)>\s*', blocks[i+1]):
            paragraphs.append(blocks[i] + blocks[i+1]); i += 2
        elif blocks[i].strip(): paragraphs.append(blocks[i]); i += 1
        else: i += 1
    pages, current, current_len = [], [], 0
    for p in paragraphs:
        visible = len(re.sub(r'<[^>]+>', '', p))
        if current_len + visible > chars_per_page and current:
            pages.append('\n'.join(current)); current = []; current_len = 0
        current.append(p); current_len += visible
    if current: pages.append('\n'.join(current))
    return pages or ['']


def build():
    SITE.mkdir(exist_ok=True)
    (SITE / "articles").mkdir(exist_ok=True)

    issues_dir = DATA / "issues"
    issues = []
    if issues_dir.exists():
        for f in sorted(issues_dir.glob("*.json"), reverse=True):
            data = json.loads(f.read_text())
            data["_date"] = f.stem
            issues.append(data)

    today_str = date.today().isoformat()
    latest_issue = issues[0] if issues else None
    section_meta = load_section_meta()

    (SITE / "index.html").write_text(build_index(latest_issue, today_str, section_meta))

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
                    if idx + 1 < len(ids): next_id = ids[idx + 1]
                except ValueError: pass
                page_file = article_dir / f"page{pi}.html" if pi > 1 else article_dir / "index.html"
                page_file.write_text(build_article_page(article, page_html, pi, len(pages), next_id))

    (SITE / "archive.html").write_text(build_archive(issues))
    print(f"Static site built: {len(list(SITE.rglob('*.html')))} pages")


def build_index(issue, today_str, section_meta):
    if not issue:
        return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><title>三千要看</title><style>{CSS}</style></head><body>
<div class="masthead"><h1>三千要看</h1><div class="date">{today_str}</div></div>
<p style="text-align:center;color:#999;margin-top:2em">今天还没有内容，一会回来看看。</p>
<div class="footer"><a href="{BASE}/archive.html">往期</a></div>
</body></html>"""

    articles_dir = DATA / "articles"

    # Group articles by section
    articles_by_section = {}
    for aid in issue.get("articles", []):
        ajson = articles_dir / f"{aid}.json"
        if not ajson.exists():
            continue
        a = json.loads(ajson.read_text())
        sid = a.get("section_id", "unknown")
        if sid not in articles_by_section:
            articles_by_section[sid] = []
        articles_by_section[sid].append(a)

    section_html = ""
    for sid, articles in articles_by_section.items():
        meta = section_meta.get(sid, {"name": sid, "emoji": ""})
        section_html += f'<section class="section-card"><h2>{meta["emoji"]} {meta["name"]}</h2>'
        for a in articles:
            title = a.get("title_zh") or a.get("id", "")
            source = a.get("source", "")
            wc = a.get("word_count_zh", 0)
            summary = a.get("summary_zh", "")
            aid_ = a.get("id", "")
            spoiler_tag = '<span class="spoiler-tag">[剧透]</span>' if a.get("has_spoiler") else ""
            section_html += f"""<div class="article-item">
  <a href="{BASE}/articles/{aid_}/">
    <span class="title">{title}{spoiler_tag}</span>
    <span class="meta">{source} | {wc} 字</span>
    <span class="summary">{summary}</span>
  </a>
</div>"""
        section_html += '</section>'

    if not articles_by_section:
        section_html = '<p style="text-align:center;color:#888">本期暂无长文。</p>'

    fb = issue.get("stats", {}).get("fallback_note", "")
    fb_html = f'<p style="color:#c00;text-align:center">{fb}</p>' if fb else ""

    # Check for briefing
    briefing_html = ""
    briefing_file = DATA / "briefings" / f"{issue['_date']}.json"
    if briefing_file.exists():
        try:
            briefing_data = json.loads(briefing_file.read_text())
            items_html = ""
            for item in briefing_data.get("items", [])[:10]:
                items_html += f"""<li>
  <h3><a href="{item.get('source_url', '#')}">{item.get('title', '')}</a></h3>
  <p>{item.get('body', '')}</p>
  <small>- {item.get('source_name', '')}</small>
</li>"""
            briefing_html = f'<section class="briefing"><h2>📰 今日要闻</h2><ol>{items_html}</ol></section>'
        except Exception:
            pass

    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><title>三千要看 - {issue["_date"]}</title><style>{CSS}</style></head><body>
<div class="masthead"><h1>三千要看</h1><div class="date">{issue["_date"]}</div></div>
{briefing_html}
<div class="push-container">
  <button id="push-btn" class="cat-btn" onclick="triggerPush()">
    <pre class="cat-art">{CAT_ART}</pre>
    <span class="cat-label">决定推送到 Kindle</span>
  </button>
  <div id="push-status"></div>
  <div class="push-hint">按钮触发后 2-3 分钟到 Kindle · Token 仅存本机浏览器</div>
</div>
<div class="editor-note">{issue.get("editor_note", "")}</div>
{fb_html}
{section_html}
<div class="footer"><a href="{BASE}/archive.html">往期</a></div>
<script>
const ISSUE_DATE = "{issue['_date']}";
async function triggerPush() {{
  const btn = document.getElementById('push-btn');
  const status = document.getElementById('push-status');
  let token = localStorage.getItem('gh_push_token');
  if (!token) {{
    token = prompt('首次使用，请输入 GitHub Personal Access Token\\n（仅存本机浏览器，不上传服务器）：');
    if (!token) return;
    localStorage.setItem('gh_push_token', token);
  }}
  btn.disabled = true;
  status.textContent = '小猫正在出门送信...';
  try {{
    const resp = await fetch(
      'https://api.github.com/repos/sanqiandawang/sanqian-reader/actions/workflows/manual_push.yml/dispatches',
      {{
        method: 'POST',
        headers: {{
          'Accept': 'application/vnd.github+json',
          'Authorization': `Bearer ${{token}}`,
          'X-GitHub-Api-Version': '2022-11-28',
        }},
        body: JSON.stringify({{ ref: 'main', inputs: {{ issue_date: ISSUE_DATE }} }}),
      }}
    );
    if (resp.status === 204) {{
      status.innerHTML = '✓ 小猫已上路！2-3 分钟后 Kindle 收到。<br><a href="https://github.com/sanqiandawang/sanqian-reader/actions" target="_blank">查看推送进度</a>';
    }} else if (resp.status === 401) {{
      status.textContent = '✗ Token 无效，已清除，请刷新重试';
      localStorage.removeItem('gh_push_token');
      btn.disabled = false;
    }} else {{
      const err = await resp.text();
      status.textContent = '✗ 推送失败: ' + resp.status + ' ' + err.slice(0, 100);
      btn.disabled = false;
    }}
  }} catch (e) {{
    status.textContent = '✗ 网络错误: ' + e.message;
    btn.disabled = false;
  }}
}}
</script>
</body></html>"""


def build_article_page(article, content_html, page, total, next_id):
    title = article.get("title_zh") or article.get("id", "")
    source = article.get("source", "")
    wc = article.get("word_count_zh", 0)
    spoiler_tag = '<span class="spoiler-tag">[剧透]</span>' if article.get("has_spoiler") else ""

    prev_link = ""
    if page > 1:
        prev_url = f"page{page-1}.html" if page > 2 else ""
        prev_link = f'<a href="{prev_url}">上一页</a>'
    next_link = ""
    if page < total:
        next_link = f'<a href="page{page+1}.html">下一页</a>'
    is_last = page == total
    done_link = ""
    if is_last:
        done_link = '| <span class="done-link">已读完</span>'
    cat = f'<pre class="cat-footer">{CAT_ART}</pre>'

    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><title>{title} - 三千要看</title><style>{CSS}</style></head><body>
<div class="article-header"><h1>{title}{spoiler_tag}</h1><div class="meta">{source} | {wc} 字</div></div>
<div class="content">{content_html}</div>
<div class="pagination">{prev_link} <span>第 {page} / {total} 页</span> {next_link}</div>
<div class="nav-bottom"><a href="{BASE}/">回首页</a> {done_link}</div>
{cat}</body></html>"""


def build_archive(issues):
    items = ""
    for iss in issues:
        note = iss.get("editor_note", "")
        if len(note) > 120: note = note[:120] + "..."
        links = ""
        for aid in iss.get("articles", []):
            links += f'<li><a href="{BASE}/articles/{aid}/">{aid}</a></li>'
        items += f"""<div class="issue">
<div class="issue-date">{iss["_date"]}</div>
<div class="issue-note">{note}</div>
<ul>{links}</ul>
</div>"""
    if not items:
        items = '<p style="text-align:center;color:#888">还没有往期内容。</p>'
    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><title>往期 - 三千要看</title><style>{CSS}</style></head><body>
<h1>往期</h1>
{items}
<div class="footer"><a href="{BASE}/">回首页</a></div>
</body></html>"""


if __name__ == "__main__":
    build()
