"""Reads PDF files page by page and splits them into chunks.

Every chunk keeps the file name and page number it came from, so answers
can show their sources later.

Chunk format (shared by the whole project):
    {"text": str, "source": str, "page": int}
"""

from pathlib import Path

from pypdf import PdfReader

import config


def read_pdf_pages(path):
    """Return the text of each page as a list of {"page", "text"} dicts.

    Page numbers start from 1. Pages without text are skipped.
    """
    reader = PdfReader(str(path))
    pages = []
    for number, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append({"page": number, "text": text})
    return pages


def chunk_pages(pages, source, chunk_size=config.CHUNK_SIZE, overlap=config.CHUNK_OVERLAP):
    """Split page texts into overlapping word chunks.

    Chunks never cross page boundaries, so each chunk has exactly one page number.
    """
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    step = chunk_size - overlap
    chunks = []
    for page in pages:
        words = page["text"].split()
        for start in range(0, len(words), step):
            part = words[start:start + chunk_size]
            if not part:
                break
            chunks.append({"text": " ".join(part), "source": source, "page": page["page"]})
            if start + chunk_size >= len(words):
                break
    return chunks


def load_pdfs(folder=config.PDF_DIR):
    """Read every PDF in a folder and return all chunks together."""
    folder = Path(folder)
    chunks = []
    for pdf_path in sorted(folder.glob("*.pdf")):
        pages = read_pdf_pages(pdf_path)
        chunks.extend(chunk_pages(pages, source=pdf_path.name))
    return chunks
