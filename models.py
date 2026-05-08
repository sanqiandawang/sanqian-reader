from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional


@dataclass
class Article:
    id: str
    title_zh: str
    source: str
    source_url: str
    author: str
    summary_zh: str = ""
    content_zh: str = ""
    tags: list[str] = field(default_factory=list)
    word_count_zh: int = 0
    original_word_count: int = 0
    translation_model: str = ""
    prompt_version: str = ""
    quality_score: dict = field(default_factory=dict)
    section_id: str = ""
    has_spoiler: bool = False
    topic_keywords: list[str] = field(default_factory=list)
    read_status: str = "unread"
    read_at: Optional[str] = None
    fetched_at: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Article":
        return cls(**{k: d.get(k) for k in cls.__dataclass_fields__ if k in d})


@dataclass
class Issue:
    date: str  # YYYY-MM-DD
    articles: list[str] = field(default_factory=list)  # article ids
    editor_note: str = ""
    stats: dict = field(default_factory=dict)
    epub_sent_at: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Issue":
        return cls(**{k: d.get(k) for k in cls.__dataclass_fields__ if k in d})


@dataclass
class CandidateArticle:
    """Intermediate representation during pipeline screening"""
    id: str
    url: str
    source_name: str
    title_en: str
    text_en: str
    word_count: int
    source_id: str = ""
    published_at: Optional[str] = None
    author: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "CandidateArticle":
        return cls(**{k: d.get(k) for k in cls.__dataclass_fields__ if k in d})
