import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
ARTICLES_DIR = DATA_DIR / "articles"
ISSUES_DIR = DATA_DIR / "issues"
CACHE_DIR = DATA_DIR / "cache"
OUTPUT_DIR = ROOT / "output"

for d in [DATA_DIR, ARTICLES_DIR, ISSUES_DIR, CACHE_DIR, OUTPUT_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# DeepSeek
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# Jina Reader
JINA_BASE = "https://r.jina.ai/"
JINA_TIMEOUT = 30

# Pipeline
DAILY_TOKEN_BUDGET = 1_000_000
MAX_ARTICLE_WORDS = 15_000
MAX_CONCURRENCY = 3
MAX_RETRIES = 3
MIN_ARTICLES_PER_ISSUE = 5
TRANSLATED_MIN_CHARS = 3000
SCREEN_MIN_WORDS = 2000
CACHE_RETENTION_DAYS = 7

# Web server
SERVER_PORT = int(os.getenv("SERVER_PORT", "8765"))
REFRESH_COOLDOWN_MINUTES = 60
REFRESH_TOKEN = os.getenv("REFRESH_TOKEN", "change-me")

# SMTP / Kindle
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.126.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
KINDLE_EMAIL = os.getenv("KINDLE_EMAIL", "")

# Editor note banned words
EDITOR_BANNED_WORDS = [
    "精彩纷呈", "不容错过", "值得一读", "为您带来",
    "精选", "今日佳作", "敬请阅读", "不可错过", "推荐阅读",
]

# Sources file
SOURCES_FILE = ROOT / "sources.yaml"
BLACKLIST_FILE = ROOT / "blacklist.txt"
BLACKLIST_TOPICS_FILE = ROOT / "blacklist_topics.txt"
