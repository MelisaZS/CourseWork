import json

import config
from agent import summarizer


def test_summarize_pdf_saves_and_reuses_summary(monkeypatch, tmp_path):
    pdf = tmp_path / "example.pdf"
    pdf.write_bytes(b"same PDF content")
    copy = tmp_path / "renamed.pdf"
    copy.write_bytes(pdf.read_bytes())
    cache = tmp_path / "data" / "summaries.json"
    calls = []

    class FakePage:
        def extract_text(self):
            return "PDF'in ilk sayfasındaki örnek metin."

    class FakeReader:
        def __init__(self, stream):
            self.pages = [FakePage()]

    def fake_llm(prompt):
        assert "PDF'in ilk sayfasındaki örnek metin." in prompt
        calls.append(prompt)
        return "Örnek özet."

    monkeypatch.setattr(config, "SUMMARIES_PATH", cache)
    monkeypatch.setattr(summarizer, "PdfReader", FakeReader)
    monkeypatch.setattr(summarizer, "ask_llm", fake_llm)

    assert summarizer.summarize_pdf(pdf) == "Örnek özet."
    assert list(json.loads(cache.read_text(encoding="utf-8")).values()) == [
        "Örnek özet."
    ]
    assert summarizer.summarize_pdf(copy) == "Örnek özet."
    assert len(calls) == 1
