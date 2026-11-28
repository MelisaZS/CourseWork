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
            "options": {
                "num_predict": 400,
                "repeat_penalty": 1.2,
            },
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


def test_ask_llm_sends_custom_options(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"response": "Test cevabı."}

    def fake_post(url, *, json, timeout):
        assert url == f"{config.OLLAMA_URL.rstrip('/')}/api/generate"
        assert json == {
            "model": config.OLLAMA_MODEL,
            "prompt": "Test sorusu",
            "stream": False,
            "options": {
                "num_predict": 300,
                "repeat_penalty": 1.2,
                "temperature": 0.2,
            },
        }
        assert timeout == (5, 120)
        return FakeResponse()

    monkeypatch.setattr(llm.requests, "post", fake_post)

    assert llm.ask_llm(
        "Test sorusu",
        temperature=0.2,
        max_tokens=300,
    ) == "Test cevabı."
