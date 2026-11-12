# PDF AI Query – Standards Project

Term project for **Software Development with Standards** (İstanbul Kültür University, Fall 2026).

A locally running, AI-assisted question answering system. Users can ask questions about their PDF documents, a company database and the web. A decision (router) agent picks the right source. The project is developed and evaluated against the **ISO/IEC 25010** software quality model, with a security layer for personal and commercial data.

## Team

| Member | Role |
|---|---|
| Hasan Mert Yıldırım | Group leader |
| Melisa Zeynep Sarıgüzel | Developer |
| Gürkan Zıba| Developer |
| Ahmet Celal Koç | Developer |
| Elif Başak Yılmaz | Developer |

## Features (planned over 4 weeks)

- **Week 1 – Infrastructure & document search:** PDF upload, page-aware chunking, embedding-based search (top-3 results with source file and page), answer generation with a local LLM (Ollama), company database schema with sample data, unit tests
- **Week 2 – Router agent & three sources:** decision agent that routes questions to database query (Text-to-SQL), document search or web search; automatic PDF summaries
- **Week 3 – Security layer:** login and roles, SQL safety checks, personal data masking and encryption, prompt injection protection, audit log, admin panel
- **Week 4 – Testing & quality:** CI/CD pipeline, security tests, Recall@3, router accuracy and response time measurements, `/report` quality page

## Tech Stack

- Python, Flask
- Sentence Transformers (`paraphrase-multilingual-MiniLM-L12-v2`), cosine similarity
- pypdf
- Ollama (local LLM)
- SQLite, Faker
- pytest, ruff

## Setup

```bash
pip install -r requirements.txt
python -m rag.indexer   # builds the document index from data/pdfs
python db/seed.py       # creates the sample company database
python app.py           # http://127.0.0.1:5000
```

Ollama must be installed and running for LLM answers.

## Project Structure

```
config.py   # shared settings (paths, model names)
rag/        # PDF loading, chunking, indexing, retrieval
agent/      # LLM, router agent, web search, summaries
db/         # database schema, sample data, Text-to-SQL
auth/       # login, roles, security
templates/  # web interface
data/pdfs/  # PDF documents
docs/       # weekly reports
tests/      # unit tests
```

## Quality Standard

The project follows **ISO/IEC 25010**. Functional suitability, performance efficiency, security, reliability and maintainability are measured with tests and metrics, and results are reported in the weekly progress reports.
