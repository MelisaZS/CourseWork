
"""Flask application tests."""

from io import BytesIO

import pytest

import app as app_module
import config


@pytest.fixture
def client():
    app_module.app.config.update(TESTING=True)
    return app_module.app.test_client()


def test_home_page(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "PDF AI Search" in response.get_data(as_text=True)


def test_empty_question(client, monkeypatch):
    def unexpected_answer(question):
        pytest.fail("Boş soruda router çağrılmamalı")

    monkeypatch.setattr(
        app_module,
        "router_answer",
        unexpected_answer,
    )

    response = client.post("/", data={"question": "  "})

    assert response.status_code == 200
    assert "Lütfen bir soru girin." in response.get_data(as_text=True)


def test_answer_and_sources(client, monkeypatch):
    def fake_answer(question):
        assert question == "Büyük dil modeli nedir?"

        return {
            "route": "doc",
            "answer": "LLM, büyük dil modeli anlamına gelir.",
            "sources": [{"source": "example.pdf", "page": 7}],
            "matches": [
                {
                    "source": "example.pdf",
                    "page": 7,
                    "text": "PDF'ten alınan örnek metin.",
                    "score": 0.95,
                }
            ],
        }

    monkeypatch.setattr(app_module, "router_answer", fake_answer)

    response = client.post(
        "/",
        data={"question": "Büyük dil modeli nedir?"},
    )

    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "LLM, büyük dil modeli anlamına gelir." in html
    assert "example.pdf – sayfa 7" in html
    assert "Skor 0.950" in html
    assert "PDF&#39;ten alınan örnek metin." in html


def test_database_answer(client, monkeypatch):
    def fake_answer(question):
        return {
            "route": "db",
            "answer": "Sonuç: 200",
            "sql": "SELECT COUNT(*) FROM customers;",
            "columns": ["count"],
            "rows": [[200]],
            "sources": [],
        }

    monkeypatch.setattr(app_module, "router_answer", fake_answer)

    response = client.post(
        "/",
        data={"question": "Kaç müşterimiz var?"},
    )

    assert response.status_code == 200
    assert "Sonuç: 200" in response.get_data(as_text=True)


def test_web_answer(client, monkeypatch):
    def fake_answer(question):
        return {
            "route": "web",
            "answer": "Güncel arama bilgisi.",
            "sources": ["https://example.com"],
        }

    monkeypatch.setattr(app_module, "router_answer", fake_answer)

    response = client.post(
        "/",
        data={"question": "Bugün dolar kaç TL?"},
    )

    assert response.status_code == 200
    assert "Güncel arama bilgisi." in response.get_data(as_text=True)


def test_reject_non_pdf(client, monkeypatch, tmp_path):
    monkeypatch.setattr(config, "UPLOAD_DIR", tmp_path)

    response = client.post(
        "/upload",
        data={"files": (BytesIO(b"not a pdf"), "image.png")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert list(tmp_path.iterdir()) == []


def test_multiple_pdf_upload(client, monkeypatch, tmp_path):
    monkeypatch.setattr(config, "UPLOAD_DIR", tmp_path)

    calls = []

    def fake_rebuild_index():
        calls.append("rebuild")

    monkeypatch.setattr(
        app_module,
        "rebuild_index",
        fake_rebuild_index,
    )
    monkeypatch.setattr(app_module, "summarize_pdf", lambda path: "Örnek özet.")
    response = client.post(
        "/upload",
        data={
            "files": [
                (BytesIO(b"fake pdf one"), "first.pdf"),
                (BytesIO(b"fake pdf two"), "second.pdf"),
            ]
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert (tmp_path / "first.pdf").exists()
    assert (tmp_path / "second.pdf").exists()
    assert calls == ["rebuild"]
    assert "2 PDF" in response.get_data(as_text=True)
