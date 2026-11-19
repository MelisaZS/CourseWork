
"""Tests for LLM router and source dispatching."""

import agent.router as router


def test_prompt_contains_examples_and_rules():
    prompt = router.build_route_prompt("Kaç müşterimiz var?")

    assert "db" in prompt
    assert "doc" in prompt
    assert "web" in prompt
    assert "Kaç müşterimiz var?" in prompt
    assert "Yalnızca db, doc veya web yaz" in prompt


def test_route_db(monkeypatch):
    monkeypatch.setattr(router, "ask_llm", lambda prompt: "db")

    assert router.route("Kaç müşterimiz var?") == "db"


def test_route_doc(monkeypatch):
    monkeypatch.setattr(router, "ask_llm", lambda prompt: "doc")

    assert router.route("PDF'te Scrum nedir?") == "doc"


def test_route_web(monkeypatch):
    monkeypatch.setattr(router, "ask_llm", lambda prompt: " WEB ")

    assert router.route("Bugün dolar kaç TL?") == "web"


def test_invalid_llm_response_defaults_to_doc(monkeypatch):
    monkeypatch.setattr(
        router,
        "ask_llm",
        lambda prompt: "Bence veritabanını kullanmalısın.",
    )

    assert router.route("Kaç müşteri var?") == "doc"


def test_empty_question_defaults_to_doc(monkeypatch):
    def unexpected_llm(prompt):
        raise AssertionError("LLM should not be called")

    monkeypatch.setattr(router, "ask_llm", unexpected_llm)

    assert router.route("   ") == "doc"


def test_answer_routes_to_database(monkeypatch):
    monkeypatch.setattr(router, "route", lambda question: "db")

    def fake_db(question):
        assert question == "Kaç müşterimiz var?"
        return {
            "answer": "Sonuç: 200",
            "sql": "SELECT COUNT(*) FROM customers;",
            "columns": ["count"],
            "rows": [[200]],
        }

    monkeypatch.setattr(router, "answer_from_db", fake_db)

    result = router.answer("Kaç müşterimiz var?")

    assert result["route"] == "db"
    assert result["answer"] == "Sonuç: 200"
    assert result["rows"] == [[200]]
    assert result["sources"] == []


def test_answer_routes_to_documents(monkeypatch):
    monkeypatch.setattr(router, "route", lambda question: "doc")

    def fake_docs(question, *, include_matches=False):
        assert question == "PDF'te Scrum nedir?"
        assert include_matches is True

        return {
            "answer": "Scrum çevik bir geliştirme yaklaşımıdır.",
            "sources": [{"source": "example.pdf", "page": 3}],
            "matches": [
                {
                    "text": "Scrum hakkında metin",
                    "source": "example.pdf",
                    "page": 3,
                    "score": 0.95,
                }
            ],
        }

    monkeypatch.setattr(router, "answer_from_docs", fake_docs)

    result = router.answer("PDF'te Scrum nedir?")

    assert result["route"] == "doc"
    assert result["sources"][0]["page"] == 3
    assert result["matches"][0]["score"] == 0.95


def test_answer_routes_to_web(monkeypatch):
    monkeypatch.setattr(router, "route", lambda question: "web")

    def fake_web(question):
        assert question == "Bugün dolar kaç TL?"
        return {
            "answer": "Güncel arama bilgisi.",
            "sources": ["https://example.com"],
        }

    monkeypatch.setattr(router, "answer_from_web", fake_web)

    result = router.answer("Bugün dolar kaç TL?")

    assert result["route"] == "web"
    assert result["answer"] == "Güncel arama bilgisi."
    assert result["sources"] == ["https://example.com"]


def test_route_db_with_period(monkeypatch):
    monkeypatch.setattr(router, "ask_llm", lambda prompt: "db.")

    assert router.route("Kaç müşterimiz var?") == "db"


def test_route_web_with_prefix(monkeypatch):
    monkeypatch.setattr(router, "ask_llm", lambda prompt: "Rota: web")

    assert router.route("Bugün dolar kaç TL?") == "web"


def test_route_db_with_quotes(monkeypatch):
    monkeypatch.setattr(router, "ask_llm", lambda prompt: '"db"')

    assert router.route("En çok sipariş veren müşteri kim?") == "db"


def test_route_db_with_explanation(monkeypatch):
    monkeypatch.setattr(
        router,
        "ask_llm",
        lambda prompt: "db\n\nÇünkü soru müşterilerle ilgili.",
    )

    assert router.route("Kaç müşterimiz var?") == "db"
