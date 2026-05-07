import logging
import requests
from readability import Document
from bs4 import BeautifulSoup
from providers.base import ContentProvider, ProviderMetadata
from config import JINA_TIMEOUT
from typing import Optional

logger = logging.getLogger("readability")


class ReadabilityProvider(ContentProvider):
    def name(self) -> str:
        return "readability"

    def fetch(self, url: str) -> tuple[Optional[str], Optional[ProviderMetadata], Optional[str]]:
        try:
            resp = requests.get(url, timeout=JINA_TIMEOUT,
                              headers={"User-Agent": "Mozilla/5.0 (compatible; SanqianReader/1.0)"})
            resp.raise_for_status()
            doc = Document(resp.text)
            title = doc.title() or "Untitled"
            text = doc.summary()
            soup = BeautifulSoup(text, "html.parser")
            text = soup.get_text("\n").strip()

            if not text or len(text) < 200:
                return None, None, f"Readability extracted short content ({len(text)} chars)"

            words = len(text.split())
            metadata = ProviderMetadata(
                title=title,
                author="",
                canonical_url=url,
                word_count=words,
            )
            return text, metadata, None
        except requests.Timeout:
            return None, None, f"Readability timeout: {url}"
        except requests.RequestException as e:
            return None, None, f"Readability request failed: {e}"
