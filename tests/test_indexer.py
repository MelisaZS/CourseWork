import config
from rag import indexer


def fake_encode(texts):
    """Small deterministic vectors so tests run fast and offline."""
    return [[float(len(t)), float(t.count("a")), 1.0] for t in texts]


def fake_load_pdfs(folder):
    return [{"text": f"text from {folder.name}", "source": f"{folder.name}.pdf", "page": 1}]


def test_index_format(monkeypatch, tmp_path):
    monkeypatch.setattr(indexer, "encode", fake_encode)
    monkeypatch.setattr(indexer, "load_pdfs", fake_load_pdfs)
    folder = tmp_path / "pdfs"
    folder.mkdir()

    index = indexer.build_index([folder])

    assert set(index) == {"model", "chunks", "embeddings"}
    assert index["model"] == config.EMBEDDING_MODEL
    assert len(index["chunks"]) == len(index["embeddings"]) == 1
    assert set(index["chunks"][0]) == {"text", "source", "page"}


def test_reads_both_folders_and_skips_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(indexer, "encode", fake_encode)
    monkeypatch.setattr(indexer, "load_pdfs", fake_load_pdfs)
    pdfs, uploads = tmp_path / "pdfs", tmp_path / "uploads"
    pdfs.mkdir()
    uploads.mkdir()

    index = indexer.build_index([pdfs, uploads, tmp_path / "missing"])

    assert [c["source"] for c in index["chunks"]] == ["pdfs.pdf", "uploads.pdf"]


def test_save_and_load_roundtrip(tmp_path):
    index = {
        "model": "test-model",
        "chunks": [{"text": "büyük dil modeli", "source": "a.pdf", "page": 3}],
        "embeddings": [[0.1, 0.2, 0.3]],
    }
    path = tmp_path / "index.json"

    indexer.save_index(index, path)

    assert indexer.load_index(path) == index


def test_load_builds_index_when_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(indexer, "encode", fake_encode)
    monkeypatch.setattr(indexer, "load_pdfs", fake_load_pdfs)
    monkeypatch.setattr(config, "PDF_DIR", tmp_path)
    monkeypatch.setattr(config, "UPLOAD_DIR", tmp_path / "uploads")
    path = tmp_path / "index.json"

    index = indexer.load_index(path)

    assert path.exists()
    assert len(index["chunks"]) == 1
