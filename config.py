"""Project-wide settings. Every module reads paths and model names from here."""

import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Data locations
PDF_DIR = BASE_DIR / "data" / "pdfs"
UPLOAD_DIR = BASE_DIR / "uploads"
INDEX_PATH = BASE_DIR / "data" / "index.json"
DB_PATH = BASE_DIR / "data" / "company.db"
SUMMARIES_PATH = BASE_DIR / "data" / "summaries.json"

# Embedding model (multilingual, works with Turkish and English PDFs)
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

# Chunking (in words)
CHUNK_SIZE = 200
CHUNK_OVERLAP = 40

# Retrieval
TOP_K = 3

# Local LLM (Ollama)
OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "llama3.2"

# Web search (DuckDuckGo)
WEB_MAX_RESULTS = 3
WEB_REGION = "tr-tr"

# Flask session signing key. Set SECRET_KEY in the environment (.env) to keep users
# logged in across restarts; otherwise a random key is generated at every start.
SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

# bcrypt cost factor for password hashes (tests lower it to run fast)
BCRYPT_ROUNDS = 12
