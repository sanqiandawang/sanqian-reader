import json
import logging
import time
import re
from typing import Optional, Tuple
from openai import OpenAI
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL

logger = logging.getLogger("ai")

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
    return _client


TRANSLATION_PROMPT_VERSION = "v1"

CURATION_PROMPT = """You are a professional editor curating today's recommended reads from English long-form articles.

Candidate articles (each with ID, source, domain, title, opening 300-char excerpt, mid-article 300-char excerpt, word count):

{candidates}

Domain diversity (soft constraint — prioritize but skip if quality is too low):
{domain_rules}

Selection criteria: breadth of coverage, depth, novelty. Do not pick all from the same topic.

Domain diversity is a SOFT constraint. Prioritize it, but if a domain's candidates are clearly weaker, skip it.

Output ONLY a JSON object with selected article IDs (5-8), reasons, and domain coverage note:
```json
{{
  "selected": ["id1", "id2"],
  "reasons": {{"id1": "Why this article was selected", "id2": "..."}},
  "domain_note": "thought: 3 articles, science: 2, gaming_anime: 2. Science candidates were strong across the board."
}}
```"""


TRANSLATION_PROMPT = """Translate the following English article into Chinese. Requirements:

1. Fidelity, clarity, elegance: convey the original meaning accurately, write naturally in Chinese, preserve the original style
2. Terminology consistency: keep personal names, work titles, and technical terms consistent throughout
3. Mark uncertain translations: use [译注: explanation] for terms you are unsure about
4. Never omit: translate every paragraph fully, do not summarize or skip content
5. Preserve paragraph structure from the original

Original text:

{text}

Complete Chinese translation:"""


REVIEW_PROMPT = """Evaluate the translation quality of the following Chinese text against the original English excerpt.

Original English (first 2000 chars):
{original_sample}

Chinese translation (first 3000 chars):
{translation}

Score each dimension 0-10. Output ONLY a JSON object:
1. terms: Are proper nouns, personal names, and work titles translated consistently?
2. fluency: Is the Chinese natural and fluid? Any translationese?
3. completeness: Any omissions, truncations, or AI hallucinations?

```json
{{"terms": 8, "fluency": 7, "completeness": 9}}
```"""


EDITOR_NOTE_PROMPT = """You are an opinionated editor. Write an editor's note (150-200 Chinese characters) for today's issue.

Today's articles (title + source + selection reason):
{articles}

Requirements:
1. MUST connect the articles — find shared themes, interesting contrasts, or conversations between them
2. MUST have a specific viewpoint — do NOT just say "today we've selected X articles for you"
3. Tone: think Dense Discovery or The Browser newsletter openings — personal, insightful, sharp
4. The following Chinese phrases are FORBIDDEN and must NOT appear: 精彩纷呈、不容错过、值得一读、为您带来、精选、今日佳作、敬请阅读、不可错过、推荐阅读
5. If a domain was skipped due to low quality candidates, explain briefly in the note

Write the editor's note in Chinese:"""


SEMANTIC_BLACKLIST_PROMPT = """Determine whether the following article matches any noise topic.

Article title: {title}
Article opening (500 chars): {excerpt}

Noise topics — articles matching these should be filtered out:
{topics}

For each topic, answer YES if the article clearly matches, NO otherwise.
Output ONLY a JSON object:
```json
{{"hit": true, "topic": "topic name that matched"}}
```
or if no match:
```json
{{"hit": false}}
```"""


def call_deepseek(prompt: str, system: str = "You are a helpful assistant.", max_tokens: int = 4096) -> Tuple[Optional[str], Optional[dict]]:
    try:
        resp = _get_client().chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_tokens,
            temperature=0.3,
        )
        content = resp.choices[0].message.content.strip()
        usage = {
            "prompt_tokens": resp.usage.prompt_tokens,
            "completion_tokens": resp.usage.completion_tokens,
            "total_tokens": resp.usage.total_tokens,
        }
        return content, usage
    except Exception as e:
        logger.error(f"DeepSeek call failed: {e}")
        return None, None


def curate_articles(candidates: list, domains: dict) -> Optional[dict]:
    candidates_text = ""
    for c in candidates:
        excerpt_head = c.get("text_head", "")[:300]
        excerpt_mid = c.get("text_mid", "")[:300]
        candidates_text += (
            f"ID: {c['id']}\n"
            f"Source: {c['source_name']} | Domain: {c['source_domain']}\n"
            f"Title: {c['title_en']}\n"
            f"Opening excerpt: {excerpt_head}\n"
            f"Mid-article excerpt: {excerpt_mid}\n"
            f"Word count: {c['word_count']}\n\n"
        )

    domain_rules = ""
    for d, cfg in domains.items():
        domain_rules += f"- {d}: aim for {cfg.get('min_articles', 0)}-{cfg.get('max_articles', 99)} articles\n"
    domain_rules += "\nThese are SOFT constraints. If a domain's candidates are clearly weaker (quality <= 3/10), skip it and mention why in the domain_note."

    prompt = CURATION_PROMPT.format(
        candidates=candidates_text,
        domain_rules=domain_rules,
    )

    result, usage = call_deepseek(prompt, system="You are a professional editor.", max_tokens=2048)
    if not result:
        return None

    try:
        json_match = re.search(r'```json\s*(.*?)\s*```', result, re.DOTALL)
        if json_match:
            result = json_match.group(1)
        return json.loads(result)
    except json.JSONDecodeError:
        logger.error(f"Curation JSON parse failed: {result[:200]}")
        return None


def translate_article(text: str) -> Tuple[Optional[str], Optional[dict]]:
    max_chunk = 8000
    if len(text) <= max_chunk:
        result, usage = call_deepseek(
            TRANSLATION_PROMPT.format(text=text),
            system="You are a professional translator. Translate English to Chinese with high fidelity.",
            max_tokens=8192,
        )
        return result, usage

    # Chunked translation for long texts
    chunks = [text[i:i+max_chunk] for i in range(0, len(text), max_chunk)]
    translated = []
    total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    for i, chunk in enumerate(chunks):
        context = "\n".join(translated[-2:]) if translated else ""
        if context:
            chunk_prompt = f"Previous translation context:\n{context}\n\nContinue translating the following text:\n{chunk}"
        else:
            chunk_prompt = TRANSLATION_PROMPT.format(text=chunk)
        result, usage = call_deepseek(chunk_prompt, max_tokens=8192)
        if not result:
            logger.error(f"Chunk {i+1}/{len(chunks)} translation failed")
            return None, None
        translated.append(result)
        if usage:
            for k in total_usage:
                total_usage[k] += usage.get(k, 0)
    return "\n\n".join(translated), total_usage


def review_translation(translation: str, original_sample: str) -> Optional[dict]:
    result, usage = call_deepseek(
        REVIEW_PROMPT.format(original_sample=original_sample[:2000], translation=translation[:3000]),
        system="You are a translation quality reviewer.",
        max_tokens=512,
    )
    if not result:
        return None
    try:
        json_match = re.search(r'```json\s*(.*?)\s*```', result, re.DOTALL)
        if json_match:
            result = json_match.group(1)
        return json.loads(result)
    except json.JSONDecodeError:
        logger.error(f"Review JSON parse failed: {result[:200]}")
        return None


def generate_editor_note(articles_info: list, banned_words: list) -> str:
    articles_text = ""
    for a in articles_info:
        articles_text += f"- [{a['source']}] {a['title_zh']}: {a.get('reason', '')}\n"

    prompt = EDITOR_NOTE_PROMPT.format(articles=articles_text)

    for attempt in range(3):
        result, usage = call_deepseek(prompt, system="You are a magazine editor with strong opinions.", max_tokens=1024)
        if not result:
            continue
        # Check banned words
        hit = False
        for w in banned_words:
            if w in result:
                logger.warning(f"Editor note attempt {attempt+1} hit banned word: '{w}'")
                hit = True
                break
        if not hit:
            return result
        prompt += f"\n\nRETRY REQUIREMENT: Completely avoid these words/phrases: {', '.join(banned_words)}"

    # Use template fallback
    titles = [a['title_zh'] for a in articles_info]
    return f"今天的选文围绕几个共同议题展开：{'、'.join(titles[:3])}等。每篇都值得细读，希望有一篇能陪你度过此刻。"


def semantic_blacklist_check(title: str, excerpt: str, topics: list) -> Tuple[bool, str]:
    if not topics:
        return False, ""
    prompt = SEMANTIC_BLACKLIST_PROMPT.format(
        title=title,
        excerpt=excerpt[:500],
        topics="\n".join(f"- {t}" for t in topics),
    )
    result, usage = call_deepseek(prompt, max_tokens=256)
    if not result:
        return False, ""
    try:
        json_match = re.search(r'```json\s*(.*?)\s*```', result, re.DOTALL)
        if json_match:
            result = json_match.group(1)
        data = json.loads(result)
        return data.get("hit", False), data.get("topic", "")
    except json.JSONDecodeError:
        return False, ""
