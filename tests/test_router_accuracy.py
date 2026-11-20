"""Tests for the router accuracy evaluation. No Ollama needed: the router is faked."""

import json

import requests

import agent.router as router
import eval.router_accuracy as ra


def by_expected(questions):
    """A fake router that is always right."""
    answers = {q["question"]: q["expected"] for q in questions}
    return lambda question: answers[question]


def test_question_list_has_10_per_source():
    questions = ra.load_questions()
    assert len(questions) == 30
    for route in ra.ROUTES:
        assert sum(q["expected"] == route for q in questions) == 10


def test_questions_are_unique_and_not_router_examples():
    texts = [q["question"] for q in ra.load_questions()]
    assert len(set(texts)) == len(texts)
    assert len({q["id"] for q in ra.load_questions()}) == len(texts)
    few_shot = {example for example, _ in router.ROUTE_EXAMPLES}
    assert not few_shot & set(texts)


def test_perfect_router_scores_100():
    questions = ra.load_questions()
    result = ra.evaluate(questions, route_fn=by_expected(questions))
    assert result["accuracy"] == 100.0
    assert result["mistakes"] == []
    for r in ra.ROUTES:
        assert result["confusion"][r][r] == 10


def test_always_doc_router_scores_one_third():
    questions = ra.load_questions()
    result = ra.evaluate(questions, route_fn=lambda question: "doc")
    assert result["correct"] == 10
    assert result["accuracy"] == 33.3
    assert result["per_route"]["db"]["accuracy"] == 0.0
    assert result["confusion"]["web"] == {"db": 0, "doc": 10, "web": 0}
    assert len(result["mistakes"]) == 20


def test_mistakes_list_expected_and_predicted():
    questions = [
        {"id": 1, "question": "Kaç ürün var?", "expected": "db"},
        {"id": 2, "question": "Bugün hava nasıl?", "expected": "web"},
    ]
    result = ra.evaluate(questions, route_fn=lambda question: "db")
    assert result["accuracy"] == 50.0
    assert result["mistakes"] == [{"id": 2, "question": "Bugün hava nasıl?", "expected": "web", "predicted": "db"}]


def test_report_contains_accuracy_and_table():
    questions = ra.load_questions()
    report = ra.format_report(ra.evaluate(questions, route_fn=lambda question: "web"))
    assert "10/30 = %33.3" in report
    assert "Karışıklık tablosu" in report
    assert "Yanlış yönlendirilen sorular" in report


def test_evaluate_uses_real_route_by_default(monkeypatch):
    monkeypatch.setattr(router, "route", lambda question: "db")
    result = ra.evaluate([{"id": 1, "question": "Kaç müşteri var?", "expected": "db"}])
    assert result["accuracy"] == 100.0


def test_check_ollama_reports_when_down(monkeypatch):
    def offline(*args, **kwargs):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(ra.requests, "get", offline)
    assert "ulaşılamadı" in ra.check_ollama()


class FakeTagsResponse:
    def __init__(self, names):
        self.names = names

    def raise_for_status(self):
        pass

    def json(self):
        return {"models": [{"name": name} for name in self.names]}


def test_check_ollama_needs_the_model(monkeypatch):
    monkeypatch.setattr(ra.config, "OLLAMA_MODEL", "llama3.2")
    monkeypatch.setattr(ra.requests, "get", lambda *a, **k: FakeTagsResponse(["mistral:latest"]))
    assert "ollama pull llama3.2" in ra.check_ollama()

    monkeypatch.setattr(ra.requests, "get", lambda *a, **k: FakeTagsResponse(["llama3.2:latest"]))
    assert ra.check_ollama() is None


def test_main_stops_without_ollama(monkeypatch, capsys):
    monkeypatch.setattr(ra, "check_ollama", lambda: "Ollama'ya ulaşılamadı")

    def must_not_run(*args, **kwargs):
        raise AssertionError("evaluate should not run without Ollama")

    monkeypatch.setattr(ra, "evaluate", must_not_run)
    assert ra.main([]) == 1
    assert "ulaşılamadı" in capsys.readouterr().err


def test_main_prints_report_and_saves_json(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(ra, "check_ollama", lambda: None)
    monkeypatch.setattr(router, "route", lambda question: "doc")
    output = tmp_path / "router_results.json"

    assert ra.main(["--output", str(output)]) == 0
    assert "Router doğruluğu: 10/30" in capsys.readouterr().out
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["accuracy"] == 33.3
    assert saved["confusion"]["doc"]["doc"] == 10
