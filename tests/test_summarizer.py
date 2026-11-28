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

    def fake_llm(prompt, *, max_tokens=400):
        assert "PDF'in ilk sayfasındaki örnek metin." in prompt
        assert max_tokens == 300
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


def test_summarize_pdf_removes_repeated_sentences(monkeypatch, tmp_path):
    pdf = tmp_path / "repeated.pdf"
    pdf.write_bytes(b"PDF test content")
    cache = tmp_path / "data" / "summaries.json"

    class FakePage:
        def extract_text(self):
            return "Test PDF içeriği."

    class FakeReader:
        def __init__(self, stream):
            self.pages = [FakePage()]

    repeated_sentence = "Bu cümle tekrar ediyor."
    llm_answer = (
        " ".join([repeated_sentence] * 20)
        + " İkinci cümle. Üçüncü cümle. Dördüncü cümle. "
        "Beşinci cümle. Altıncı cümle. Yedinci cümle."
    )

    def fake_llm(prompt, *, max_tokens=400):
        assert max_tokens == 300
        return llm_answer

    monkeypatch.setattr(config, "SUMMARIES_PATH", cache)
    monkeypatch.setattr(summarizer, "PdfReader", FakeReader)
    monkeypatch.setattr(summarizer, "ask_llm", fake_llm)

    summary = summarizer.summarize_pdf(pdf)

    expected = (
        "Bu cümle tekrar ediyor. "
        "İkinci cümle. Üçüncü cümle. Dördüncü cümle. "
        "Beşinci cümle. Altıncı cümle."
    )

    assert summary == expected
    assert summary.count(repeated_sentence) == 1
    assert len(summary.split(". ")) <= 6

    saved = json.loads(cache.read_text(encoding="utf-8"))
    assert list(saved.values()) == [expected]

    assert summarizer.summarize_pdf(pdf) == expected
