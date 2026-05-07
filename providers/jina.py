import logging
import requests
from typing import Optional

from providers.base import ContentProvider, ProviderMetadata
from config import JINA_BASE, JINA_TIMEOUT

logger = logging.getLogger("jina")


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
