from rag import answer


def test_answer_from_docs_passes_context_and_returns_sources(monkeypatch):
    def fake_search(question, top_k):
        assert question == "LLM nedir?"
        assert top_k == 3
        return [
            {"text": "LLM, büyük dil modelidir.", "source": "example.pdf", "page": 7},
            {"text": "Aynı sayfadan ek bilgi.", "source": "example.pdf", "page": 7},
            {"text": "Başka bir açıklama.", "source": "guide.pdf", "page": 2},
        ]

    def fake_llm(prompt):
        assert "Sadece aşağıdaki PDF metinlerine dayanarak" in prompt
        assert "LLM nedir?" in prompt
        assert "LLM, büyük dil modelidir." in prompt
        return "LLM, büyük dil modelidir."

    monkeypatch.setattr(answer, "search", fake_search)
    monkeypatch.setattr(answer, "ask_llm", fake_llm)

    assert answer.answer_from_docs("LLM nedir?") == {
        "answer": "LLM, büyük dil modelidir.",
        "sources": [
            {"source": "example.pdf", "page": 7},
            {"source": "guide.pdf", "page": 2},
        ],
    }


def test_answer_from_docs_skips_llm_when_no_results(monkeypatch):
    def unexpected_llm(prompt):
        raise AssertionError("Arama boşsa LLM çağrılmamalı")

    monkeypatch.setattr(answer, "search", lambda *args, **kwargs: [])
    monkeypatch.setattr(answer, "ask_llm", unexpected_llm)
    assert answer.answer_from_docs("Örnek soru") == {
        "answer": answer.NO_RESULTS,
        "sources": [],
    }


def test_answer_from_docs_handles_ollama_error(monkeypatch):
    chunks = [{"text": "Örnek metin", "source": "example.pdf", "page": 7}]
    monkeypatch.setattr(answer, "search", lambda *args, **kwargs: chunks)
    monkeypatch.setattr(answer, "ask_llm", lambda prompt: answer.OLLAMA_ERROR)

    assert answer.answer_from_docs("Örnek soru") == {
        "answer": answer.OLLAMA_ERROR,
        "sources": [],
    }
