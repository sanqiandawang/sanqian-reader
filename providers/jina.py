import logging
import re
import requests
from typing import Optional

from providers.base import ContentProvider, ProviderMetadata
from config import JINA_BASE, JINA_TIMEOUT

logger = logging.getLogger("jina")

JINA_HEADER_PATTERNS = [
    r'^Title:\s*.*$',
    r'^URL Source:\s*.*$',
    r'^Published Time:\s*.*$',
    r'^Markdown Content:\s*$',
    r'^> URL Source:.*$',
    r'^> Published Time:.*$',
    r'^> Markdown Content:.*$',
]


def strip_jina_headers(text: str) -> str:
    """Strip Jina Reader metadata headers from the first 10 lines only."""
    lines = text.split('\n')
    head, body = lines[:10], lines[10:]
    cleaned = []
    for ln in head:
        if any(re.match(p, ln.strip()) for p in JINA_HEADER_PATTERNS):
            continue
        cleaned.append(ln)
    return '\n'.join(cleaned + body).lstrip('\n')


class JinaProvider(ContentProvider):
    def name(self) -> str:
        return "jina"

    def fetch(self, url: str) -> tuple[Optional[str], Optional[ProviderMetadata], Optional[str]]:
        jina_url = f"{JINA_BASE.rstrip('/')}/{url}"
        try:
            resp = requests.get(jina_url, timeout=JINA_TIMEOUT,
                               headers={"Accept": "text/markdown"})
            resp.raise_for_status()
            text = resp.text.strip()
            if not text or len(text) < 200:
                return None, None, f"Jina returned short content ({len(text)} chars)"

            # Strip Jina metadata headers before extracting title
            text = strip_jina_headers(text)

            words = len(text.split())
            title = self._extract_title(text)
            author = self._extract_author(text)
            metadata = ProviderMetadata(
                title=title,
                author=author,
                canonical_url=url,
                word_count=words,
            )
            return text, metadata, None
        except requests.Timeout:
            return None, None, f"Jina timeout after {JINA_TIMEOUT}s: {url}"
        except requests.RequestException as e:
            return None, None, f"Jina request failed: {e}"

    @staticmethod
    def _extract_title(text: str) -> str:
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("# ") and not line.startswith("## "):
                return line[2:].strip()
            if line and len(line) < 200 and not line.startswith("http"):
                return line
        return "Untitled"

    @staticmethod
    def _extract_author(text: str) -> str:
        for line in text.splitlines():
            line = line.strip()
            if line.lower().startswith("by ") and len(line) < 100:
                return line[3:].strip()
        return ""
