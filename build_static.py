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

CSS = """body{max-width:720px;margin:0 auto;padding:48px 24px 64px;background:#fff;color:#1a1a1a;font-size:17px;line-height:1.65;font-family:"Noto Serif CJK SC",Georgia,"Times New Roman",serif;-webkit-font-smoothing:antialiased}
@media(max-width:600px){body{padding:24px 14px 48px;font-size:16px}}

.date-top{text-align:center;color:#bbb;font-size:.78em;letter-spacing:.1em;margin-bottom:40px}
@media(max-width:600px){.date-top{margin-bottom:28px}}

.editor-note{border-left:3px solid #e0e0dc;padding:.6em 1.2em;margin:0 0 40px;background:#fafaf8;font-size:.9em;line-height:1.75;color:#666}
@media(max-width:600px){.editor-note{margin-bottom:28px;padding:.5em .8em;font-size:.85em}}

.section-card{margin:0 0 40px;padding:0}
.section-card h2{font-size:.78em;font-weight:400;color:#bbb;letter-spacing:.08em;margin-bottom:20px;padding-bottom:8px;border-bottom:1px solid #f0f0ec}
.section-card .article-item{padding:14px 0;border-bottom:1px solid #f5f5f0}
.section-card .article-item:last-child{border-bottom:none}
.section-card .article-item a{text-decoration:none;color:inherit;display:block}
.section-card .title{font-size:1.08em;font-weight:600;line-height:1.45;display:block;margin-bottom:4px;color:#111}
.section-card .meta{font-size:.75em;color:#bbb;display:block;margin-bottom:6px}
.section-card .summary{font-size:.85em;color:#888;line-height:1.6;display:block}
@media(max-width:600px){.section-card{margin-bottom:28px}.section-card .title{font-size:1em}.section-card .summary{font-size:.82em}}

.article-header{margin-bottom:32px;padding-bottom:20px;border-bottom:1px solid #f0f0ec}
.article-header h1{font-size:1.4em;font-weight:600;line-height:1.4;margin-bottom:8px}
.article-header .meta{color:#bbb;font-size:.8em}
@media(max-width:600px){.article-header{margin-bottom:24px;padding-bottom:14px}.article-header h1{font-size:1.2em}}

.content{line-height:1.85}
.content p{text-indent:2em;margin:.5em 0}
.content h2,.content h3{margin:1.4em 0 .5em}
.content blockquote{border-left:3px solid #e8e8e4;padding:.4em 1em;margin:.8em 0;color:#777}
.content a{color:#555;text-decoration:underline;text-underline-offset:3px;text-decoration-color:#ccc}
@media(max-width:600px){.content p{text-indent:1.5em}.content{font-size:.95em}}

.pagination{margin:2em 0;text-align:right;font-size:.85em;color:#999}
.pagination a{padding:.3em .8em;text-decoration:none;color:#555;border:1px solid #e0e0dc}
.pagination span{color:#bbb}
@media(max-width:600px){.pagination{text-align:center;font-size:.8em}}

.nav-bottom{margin-top:2em;padding-top:1em;border-top:1px solid #f0f0ec;text-align:center;font-size:.9em}
.nav-bottom a{text-decoration:none;color:#555;margin:0 8px}
.nav-bottom a:hover{color:#000}

.spoiler-tag{display:inline-block;padding:0 5px;border:1px solid #c66;color:#c66;font-size:.78em;margin-left:6px;vertical-align:middle}
.zh-tag{display:inline-block;padding:0 5px;border:1px solid #ddd;color:#aaa;font-size:.72em;margin-left:6px;vertical-align:middle}

.briefing{margin:0 0 40px;padding:0}
.briefing h2{font-size:.78em;font-weight:400;color:#bbb;letter-spacing:.08em;margin-bottom:16px}
.briefing ol{list-style:none;padding:0}
.briefing li{margin-bottom:14px;padding-bottom:14px;border-bottom:1px solid #f5f5f0}
.briefing li:last-child{border-bottom:none;margin-bottom:0;padding-bottom:0}
.briefing h3{font-size:.95em;font-weight:600;line-height:1.45;margin:0 0 3px}
.briefing h3 a{color:#111;text-decoration:none}
.briefing p{font-size:.85em;color:#888;line-height:1.65;margin:0}
.briefing small{font-size:.7em;color:#ccc}
@media(max-width:600px){.briefing{margin-bottom:28px}.briefing h3{font-size:.9em}.briefing p{font-size:.82em}}

.issue{margin-bottom:28px}
.issue-date{font-size:1em;font-weight:600;margin-bottom:4px}
.issue-note{font-size:.85em;color:#888;margin-bottom:8px;line-height:1.6}
.issue ul{list-style:none;padding:0}
.issue li{padding:2px 0;font-size:.9em}
.issue a{color:inherit;text-decoration:none}

.site-footer{text-align:center;margin-top:64px;padding-top:32px;border-top:1px solid #f0f0ec}
.footer-cat{text-align:center;color:#e0e0dc;font-size:.5em;line-height:1.15;margin:0 0 8px;white-space:pre}
.slogan{font-size:.82em;color:#bbb;letter-spacing:.06em;margin-bottom:12px}
.footer-links{font-size:.75em;color:#ccc;margin-bottom:24px}
.footer-links a{color:#bbb;text-decoration:none;margin:0 4px}
@media(max-width:600px){.site-footer{margin-top:48px;padding-top:24px}.footer-cat{font-size:.45em}}

.push-container{margin:0 auto;text-align:center}
.cat-btn{display:inline-block;padding:6px 20px;background:none;border:1px solid #e0e0dc;cursor:pointer;font-family:inherit;font-size:.78em;color:#aaa;letter-spacing:.04em}
.cat-btn:hover:not(:disabled){border-color:#888;color:#555}
.cat-btn:disabled{opacity:.3;cursor:not-allowed}
.cat-btn .cat-art{display:none}
.cat-btn .cat-label{color:inherit}
#push-status{margin-top:8px;font-size:.72em;color:#bbb;line-height:1.5}
.push-hint{font-size:.65em;color:#ddd;margin-top:4px}
.briefing-warn{font-size:.72em;color:#e80;margin-bottom:12px}"""

CAT_ART = """      ／l、
    （ﾟ､ ｡ ７
      l  ~ヽ
      じしf_,)ノ"""

SLOGAN = "本页面由三千小猫主编"

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
            item_text = re.sub(r'^[-*+]\s', '', s)
            result.append(f'<li>{_inline(item_text)}</li>')
        elif re.match(r'^\d+\.\s', s):
            if not in_list or list_type != 'ol':
                if in_list: result.append(f'</{list_type}>')
                result.append('<ol>'); in_list = True; list_type = 'ol'
            item_text = re.sub(r'^\d+\.\s', '', s)
            result.append(f'<li>{_inline(item_text)}</li>')
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
    # Footer block reused in all pages
    footer_block = f"""<div class="site-footer">
<pre class="footer-cat">{CAT_ART}</pre>
<div class="slogan">{SLOGAN}</div>
<div class="footer-links"><a href="{BASE}/">首页</a> · <a href="{BASE}/archive.html">往期</a></div>
<div class="push-container">
  <button id="push-btn" class="cat-btn" onclick="triggerPush()">
    <span class="cat-label">推送到 Kindle</span>
  </button>
  <div id="push-status"></div>
  <div class="push-hint">Token 仅存本机</div>
</div>
</div>"""

    if not issue:
        return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><title>三千要看</title><style>{CSS}</style></head><body>
<div class="date-top">{today_str}</div>
<p style="text-align:center;color:#999;margin-top:3em">今天还没有内容，一会回来看看。</p>
{footer_block}
</body></html>"""

    articles_dir = DATA / "articles"

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
            zh_tag = '<span class="zh-tag">中文原创</span>' if a.get("language") == "zh" else ""
            spoiler_tag = '<span class="spoiler-tag">[剧透]</span>' if a.get("has_spoiler") else ""
            section_html += f"""<div class="article-item">
  <a href="{BASE}/articles/{aid_}/">
    <span class="title">{title}{zh_tag}{spoiler_tag}</span>
    <span class="meta">{source} | 约 {max(1, wc//600)} 分钟</span>
    <span class="summary">{summary}</span>
  </a>
</div>"""
        section_html += '</section>'

    if not articles_by_section:
        section_html = '<p style="text-align:center;color:#999">本期暂无长文。</p>'

    fb = issue.get("stats", {}).get("fallback_note", "")
    fb_html = f'<p style="color:#c00;text-align:center">{fb}</p>' if fb else ""

    briefing_html = ""
    briefing_file = DATA / "briefings" / f"{issue['_date']}.json"
    if briefing_file.exists():
        try:
            briefing_data = json.loads(briefing_file.read_text())
            items = briefing_data.get("items", [])
            if items:
                items_html = ""
                for item in items[:10]:
                    items_html += f"""<li>
  <h3><a href="{item.get('source_url', '#')}">{item.get('title', '')}</a></h3>
  <p>{item.get('body', '')}</p>
  <small>- {item.get('source_name', '')}</small>
</li>"""
                warning_html = ""
                if briefing_data.get("_warnings"):
                    for w in briefing_data["_warnings"]:
                        warning_html += f'<p class="briefing-warn">{w}</p>'
                briefing_html = f'<section class="briefing"><h2>今日要闻</h2>{warning_html}<ol>{items_html}</ol></section>'
            else:
                reason = "未知原因"
                if briefing_data.get("_warnings"):
                    reason = "; ".join(briefing_data["_warnings"])
                briefing_html = f'<section class="briefing"><h2>今日要闻</h2><p class="briefing-warn">今日早报暂未生成（{reason}）</p></section>'
        except Exception:
            pass

    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><title>三千要看 - {issue["_date"]}</title><style>{CSS}</style></head><body>
<div class="date-top">{issue["_date"]}</div>
{briefing_html}
<div class="editor-note">{issue.get("editor_note", "")}</div>
{fb_html}
{section_html}
{footer_block}
<script>
const ISSUE_DATE = "{issue['_date']}";
async function triggerPush() {{
  const btn = document.getElementById('push-btn');
  const status = document.getElementById('push-status');
  let token = localStorage.getItem('gh_push_token');
  if (!token) {{
    token = prompt('请输入 GitHub Personal Access Token（仅存本机）：');
    if (!token) return;
    localStorage.setItem('gh_push_token', token);
    localStorage.setItem('gh_push_token_created_at', new Date().toISOString());
  }}
  // PAT expiry check (>11 months)
  const createdAt = localStorage.getItem('gh_push_token_created_at');
  if (createdAt) {{
    const ageMonths = (Date.now() - new Date(createdAt).getTime()) / (1000*60*60*24*30);
    if (ageMonths > 11) {{
      status.innerHTML = '<span style="color:#e80">⚠ Token 可能已过期（超过11个月），请重新生成</span>';
    }}
  }}
  btn.disabled = true;
  status.textContent = '小猫正在出门送信...';
  try {{
    const resp = await fetch(
      'https://api.github.com/repos/sanqiandawang/sanqian-reader/actions/workflows/manual_push.yml/dispatches',
      {{ method:'POST', headers:{{ 'Accept':'application/vnd.github+json','Authorization':`Bearer ${{token}}`,'X-GitHub-Api-Version':'2022-11-28' }}, body:JSON.stringify({{ ref:'main', inputs:{{ issue_date:ISSUE_DATE }} }}) }}
    );
    if (resp.status === 204) {{
      status.innerHTML = '✓ 小猫已上路！2-3 分钟后 Kindle 收到。';
    }} else if (resp.status === 401) {{
      status.textContent = 'Token 无效，已清除';
      localStorage.removeItem('gh_push_token'); btn.disabled = false;
    }} else {{
      status.textContent = '发送失败: ' + resp.status; btn.disabled = false;
    }}
  }} catch(e) {{ status.textContent = '网络错误'; btn.disabled = false; }}
}}
</script>
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
            zh_tag = '<span class="zh-tag">中文原创</span>' if a.get("language") == "zh" else ""
            spoiler_tag = '<span class="spoiler-tag">[剧透]</span>' if a.get("has_spoiler") else ""
            section_html += f"""<div class="article-item">
  <a href="{BASE}/articles/{aid_}/">
    <span class="title">{title}{zh_tag}{spoiler_tag}</span>
    <span class="meta">{source} | 约 {max(1, wc//600)} 分钟</span>
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
            items = briefing_data.get("items", [])
            if items:
                items_html = ""
                for item in items[:10]:
                    items_html += f"""<li>
  <h3><a href="{item.get('source_url', '#')}">{item.get('title', '')}</a></h3>
  <p>{item.get('body', '')}</p>
  <small>- {item.get('source_name', '')}</small>
</li>"""
                briefing_html = f'<section class="briefing"><h2>📰 今日要闻</h2><ol>{items_html}</ol></section>'
            else:
                reason = "未知原因"
                if briefing_data.get("_warnings"):
                    reason = "; ".join(briefing_data["_warnings"])
                briefing_html = f'<section class="briefing"><h2>📰 今日要闻</h2><p class="briefing-warn">今日早报暂未生成（{reason}）</p></section>'
        except Exception:
            pass

    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><title>三千要看 - {issue["_date"]}</title><style>{CSS}</style></head><body>
<h1>三千要看</h1><div class="date">{issue["_date"]}</div>
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

    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><title>{title} - 三千要看</title><style>{CSS}</style></head><body>
<div class="article-header"><h1>{title}{spoiler_tag}</h1><div class="meta">{source} | 约 {max(1, wc//600)} 分钟</div></div>
<div class="content">{content_html}</div>
<div class="pagination">{prev_link} <span>第 {page} / {total} 页</span> {next_link}</div>
<div class="nav-bottom"><a href="{BASE}/">回首页</a> {done_link}</div>
</body></html>"""


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
