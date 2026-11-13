"""Builds and stores the embedding index used for document search.

The index reads chunks from data/pdfs and the upload folder, turns their
texts into embeddings with config.EMBEDDING_MODEL and saves everything to
config.INDEX_PATH as JSON.

Index format (shared by the whole project):
    {"model": str, "chunks": [{"text", "source", "page"}], "embeddings": [[float]]}

Run with:
    python -m rag.indexer
"""

import json
from pathlib import Path

import config
from rag.pdf_loader import load_pdfs

_model = None


def get_model():
    """Load the embedding model once and reuse it."""
    global _model
    if _model is None:
        # Imported here so tests (which use a fake encode) never load the real model
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(config.EMBEDDING_MODEL)
    return _model


def encode(texts):
    """Turn a list of texts into normalized embedding vectors (list of float lists)."""
    if not texts:
        return []
    vectors = get_model().encode(list(texts), normalize_embeddings=True, show_progress_bar=False)
    return vectors.tolist()


def build_index(folders=None):
    """Read PDFs from all folders and return the index dict (not saved)."""
    if folders is None:
        folders = [config.PDF_DIR, config.UPLOAD_DIR]

    chunks = []
    for folder in folders:
        if Path(folder).is_dir():
            chunks.extend(load_pdfs(folder))

    embeddings = encode([c["text"] for c in chunks])
    return {"model": config.EMBEDDING_MODEL, "chunks": chunks, "embeddings": embeddings}


def save_index(index, path=None):
    """Write the index to disk as JSON."""
    path = Path(path or config.INDEX_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False)


def load_index(path=None):
    """Read the index from disk. If it does not exist yet, build it first."""
    path = Path(path or config.INDEX_PATH)
    if not path.exists():
        return rebuild_index(path)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def rebuild_index(path=None):
    """Build a fresh index from all PDFs, save it and return it."""
    index = build_index()
    save_index(index, path)
    return index


if __name__ == "__main__":
    result = rebuild_index()
    print(f"Index ready: {len(result['chunks'])} chunks -> {config.INDEX_PATH}")
