import config
from rag.pdf_loader import chunk_pages, load_pdfs


def test_chunks_keep_source_and_page():
    pages = [{"page": 1, "text": "a " * 50}, {"page": 2, "text": "b " * 50}]
    chunks = chunk_pages(pages, source="test.pdf", chunk_size=20, overlap=5)
    assert chunks
    assert all(c["source"] == "test.pdf" for c in chunks)
    assert {c["page"] for c in chunks} == {1, 2}


def test_chunks_do_not_cross_pages():
    pages = [{"page": 1, "text": "a " * 10}, {"page": 2, "text": "b " * 10}]
    chunks = chunk_pages(pages, source="x.pdf", chunk_size=50, overlap=5)
    assert len(chunks) == 2
    assert "b" not in chunks[0]["text"]


def test_chunk_size_and_overlap():
    words = [f"w{i}" for i in range(100)]
    pages = [{"page": 1, "text": " ".join(words)}]
    chunks = chunk_pages(pages, source="x.pdf", chunk_size=30, overlap=10)
    assert all(len(c["text"].split()) <= 30 for c in chunks)
    # Last 10 words of a chunk are the first 10 words of the next one
    assert chunks[0]["text"].split()[-10:] == chunks[1]["text"].split()[:10]
    # No word is lost at the end
    assert chunks[-1]["text"].split()[-1] == "w99"


def test_load_example_pdf():
    chunks = load_pdfs(config.PDF_DIR)
    assert len(chunks) > 0
    assert chunks[0]["source"] == "example.pdf"
    assert chunks[0]["page"] >= 1
