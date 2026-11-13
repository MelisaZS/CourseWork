import requests

import config
from agent import llm


def test_ask_llm_returns_answer(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"response": " Örnek cevap. "}

    def fake_post(url, *, json, timeout):
        assert url == f"{config.OLLAMA_URL.rstrip('/')}/api/generate"
        assert json == {
            "model": config.OLLAMA_MODEL,
            "prompt": "Örnek soru",
            "stream": False,
        }
        assert timeout == (5, 120)
        return FakeResponse()

    monkeypatch.setattr(llm.requests, "post", fake_post)
    assert llm.ask_llm("Örnek soru") == "Örnek cevap."


def test_ask_llm_handles_connection_error(monkeypatch):
    def fake_post(*args, **kwargs):
        raise requests.ConnectionError("Ollama kapalı")

    monkeypatch.setattr(llm.requests, "post", fake_post)
    assert llm.ask_llm("Örnek soru") == llm.OLLAMA_ERROR
