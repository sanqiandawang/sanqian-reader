from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class ProviderMetadata:
    title: str
    author: str
    published_at: Optional[str] = None
    word_count: int = 0
    canonical_url: str = ""
    lang: str = "en"


class ContentProvider(ABC):
    @abstractmethod
    def fetch(self, url: str) -> tuple[Optional[str], Optional[ProviderMetadata], Optional[str]]:
        """Returns (text_content, metadata, error_message)"""
        ...

    @abstractmethod
    def name(self) -> str:
        """Provider identifier for logging"""
        ...
