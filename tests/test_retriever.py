from rag import indexer, retriever

VECTORS = {
    "llm": [1.0, 0.0, 0.0],
    "prompt": [0.8, 0.6, 0.0],
    "veri": [0.0, 1.0, 0.0],
    "sql": [0.0, 0.0, 1.0],
}


def fake_encode(texts):
    return [VECTORS[t] for t in texts]


def fake_index():
    chunks = [{"text": name, "source": f"{name}.pdf", "page": i + 1} for i, name in enumerate(VECTORS)]
    return {"model": "fake", "chunks": chunks, "embeddings": [VECTORS[c["text"]] for c in chunks]}


def setup_fakes(monkeypatch, index=None):
    monkeypatch.setattr(indexer, "encode", fake_encode)
    monkeypatch.setattr(indexer, "load_index", lambda: index if index is not None else fake_index())


def test_returns_three_results(monkeypatch):
    setup_fakes(monkeypatch)
    results = retriever.search("llm")
    assert len(results) == 3


def test_result_fields(monkeypatch):
    setup_fakes(monkeypatch)
    result = retriever.search("llm")[0]
    assert set(result) == {"text", "source", "page", "score"}
    assert result["source"] == "llm.pdf"
    assert result["page"] == 1


def test_scores_sorted_best_first(monkeypatch):
    setup_fakes(monkeypatch)
    results = retriever.search("llm")
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)
    assert [r["text"] for r in results[:2]] == ["llm", "prompt"]
    assert scores[0] == 1.0


def test_top_k_parameter(monkeypatch):
    setup_fakes(monkeypatch)
    assert len(retriever.search("llm", top_k=1)) == 1


def test_empty_question_and_empty_index(monkeypatch):
    setup_fakes(monkeypatch)
    assert retriever.search("   ") == []
    setup_fakes(monkeypatch, index={"model": "fake", "chunks": [], "embeddings": []})
    assert retriever.search("llm") == []
