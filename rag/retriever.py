"""Semantic search over the document index.

search() returns the chunks most similar to the question using cosine
similarity. Result format (shared by the whole project):
    [{"text": str, "source": str, "page": int, "score": float}]
"""

import numpy as np

import config
from rag import indexer


def search(question, top_k=config.TOP_K):
    """Return the top_k chunks most similar to the question, best first."""
    if not question or not question.strip() or top_k <= 0:
        return []

    index = indexer.load_index()
    chunks = index.get("chunks", [])
    if not chunks:
        return []

    doc_vectors = np.asarray(index["embeddings"], dtype=float)
    query_vector = np.asarray(indexer.encode([question])[0], dtype=float)

    # Cosine similarity = dot product of normalized vectors
    doc_norms = np.linalg.norm(doc_vectors, axis=1)
    query_norm = np.linalg.norm(query_vector)
    scores = doc_vectors @ query_vector / np.maximum(doc_norms * query_norm, 1e-12)

    best = np.argsort(-scores)[:top_k]
    return [
        {
            "text": chunks[i]["text"],
            "source": chunks[i]["source"],
            "page": chunks[i]["page"],
            "score": round(float(scores[i]), 4),
        }
        for i in best
    ]
