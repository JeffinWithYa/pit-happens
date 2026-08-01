from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

# Recent complete seasons keep the corpus useful without ballooning size.
SEASONS = (2024, 2025)
# Race + Sprint: richest strategy/incident signal; skip FP/Q to control volume.
SESSION_TYPES = ("R", "S")

DATA_DIR = ROOT / "data"
FASTF1_CACHE = DATA_DIR / "fastf1_cache"
DOCS_DIR = DATA_DIR / "docs"
CHROMA_DIR = DATA_DIR / "chroma"
COLLECTION_NAME = "f1_rag"

SPUR_BASE_URL = os.getenv("SPUR_BASE_URL", "https://ai.spuric.com/v1").rstrip("/")
SPUR_EMBED_MODEL = os.getenv("SPUR_EMBED_MODEL", "spur-embed")
SPUR_EMBED_TOKEN = (
    os.getenv("SPUR_EMBED_TOKEN")
    or os.getenv("spur_embed_token")
    or ""
)

EMBED_BATCH_SIZE = int(os.getenv("EMBED_BATCH_SIZE", "32"))
MAX_DB_BYTES = int(os.getenv("MAX_DB_BYTES", str(2 * 1024**3)))

# Cap comparison / turning-point docs per session.
MAX_COMPARISONS_PER_SESSION = 6
MAX_TURNING_POINTS_PER_SESSION = 8
