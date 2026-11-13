
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
    def fake_search(*args, **kwargs):
        pytest.fail("Boş soruda search çağrılmamalı")

    monkeypatch.setattr(app_module, "search", fake_search)

    response = client.post("/", data={"question": "  "})

    assert response.status_code == 200
    assert "Lütfen bir soru girin." in response.get_data(as_text=True)


def test_search_results(client, monkeypatch):
    def fake_search(question, top_k=3):
        assert question == "Büyük dil modeli nedir?"
        assert top_k == 3
        return [
            {
                "text": "LLM, büyük dil modeli anlamına gelir.",
                "source": "example.pdf",
                "page": 7,
                "score": 0.95,
            }
        ]

    monkeypatch.setattr(app_module, "search", fake_search)

    response = client.post(
        "/",
        data={"question": "Büyük dil modeli nedir?"},
    )

    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "example.pdf" in html
    assert "0.95" in html
    assert "LLM, büyük dil modeli" in html


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
