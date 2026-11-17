import agent.web_search as web
from agent.llm import OLLAMA_ERROR

FAKE_RAW = [
    {"title": " Dolar kuru ", "href": "https://example.com/dolar", "body": " 1 USD = 34 TL "},
    {"title": "Döviz", "href": "https://example.org/doviz", "body": "Güncel kurlar"},
    {"title": "Linksiz sonuç", "href": "", "body": "atlanmalı"},
    {"title": "Fazla", "href": "https://example.net/fazla", "body": "4. sonuç"},
]


def fake_ddg(raw):
    return lambda query, max_results: raw


def fake_results():
    return [
        {"title": "Dolar kuru", "url": "https://example.com/dolar", "snippet": "1 USD = 34 TL"},
        {"title": "Döviz", "url": "https://example.org/doviz", "snippet": "Güncel kurlar"},
        {"title": "Tekrar", "url": "https://example.com/dolar", "snippet": "aynı link"},
    ]


# --- web_search


def test_web_search_format(monkeypatch):
    monkeypatch.setattr(web, "_ddg_text", fake_ddg(FAKE_RAW))
    results = web.web_search("dolar kaç TL", max_results=3)
    assert len(results) == 3
    assert all(set(r) == {"title", "url", "snippet"} for r in results)
    assert results[0] == {"title": "Dolar kuru", "url": "https://example.com/dolar", "snippet": "1 USD = 34 TL"}
    assert all(r["url"] for r in results)


def test_web_search_no_internet_does_not_crash(monkeypatch):
    def broken(query, max_results):
        raise ConnectionError("internet yok")

    monkeypatch.setattr(web, "_ddg_text", broken)
    assert web.web_search("dolar kaç TL") == []


def test_web_search_empty_question_skips_search(monkeypatch):
    def must_not_run(query, max_results):
        raise AssertionError("boş soru için arama yapılmamalı")

    monkeypatch.setattr(web, "_ddg_text", must_not_run)
    assert web.web_search("   ") == []


# --- answer_from_web


def test_answer_from_web_format_and_sources(monkeypatch):
    prompts = []
    monkeypatch.setattr(web, "web_search", lambda question: fake_results())
    monkeypatch.setattr(web, "ask_llm", lambda prompt: prompts.append(prompt) or "Dolar 34 TL civarında.")

    result = web.answer_from_web("Bugün dolar kaç TL?")

    assert set(result) == {"answer", "sources"}
    assert result["answer"] == "Dolar 34 TL civarında."
    assert result["sources"] == ["https://example.com/dolar", "https://example.org/doviz"]
    assert "1 USD = 34 TL" in prompts[0] and "Soru: Bugün dolar kaç TL?" in prompts[0]


def test_answer_from_web_empty_results(monkeypatch):
    monkeypatch.setattr(web, "web_search", lambda question: [])
    monkeypatch.setattr(web, "ask_llm", lambda prompt: (_ for _ in ()).throw(AssertionError("LLM çağrılmamalı")))
    result = web.answer_from_web("Bugün dolar kaç TL?")
    assert result == {"answer": web.NO_RESULTS_MESSAGE, "sources": []}


def test_answer_from_web_ollama_down(monkeypatch):
    monkeypatch.setattr(web, "web_search", lambda question: fake_results())
    monkeypatch.setattr(web, "ask_llm", lambda prompt: OLLAMA_ERROR)
    result = web.answer_from_web("Bugün dolar kaç TL?")
    assert result == {"answer": OLLAMA_ERROR, "sources": []}
