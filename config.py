"""Project-wide settings. Every module reads paths and model names from here."""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Data locations
PDF_DIR = BASE_DIR / "data" / "pdfs"
UPLOAD_DIR = BASE_DIR / "uploads"
INDEX_PATH = BASE_DIR / "data" / "index.json"
DB_PATH = BASE_DIR / "data" / "company.db"

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
