<div align="center">

# 🧠 RAG Evals

**A production-grade RAG architecture with a CI-gated evaluation harness, hierarchical LLM fallbacks, and strict type safety.**

[![CI & Eval Gate](https://github.com/shaurya-10000/rag-evals/actions/workflows/ci.yml/badge.svg)](https://github.com/shaurya-10000/rag-evals/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](./LICENSE)

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com)
[![Postgres](https://img.shields.io/badge/Postgres-pgvector-4169E1?style=flat-square&logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)
[![Gemini](https://img.shields.io/badge/Google_Gemini-AI-4285F4?style=flat-square&logo=google&logoColor=white)](https://ai.google.dev)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white)](https://docker.com)

</div>

---

## Overview

|  |  |
| :--- | :--- |
| **What** | A backend API that ingests documents, embeds them using Gemini, and retrieves grounded answers with citations via a robust fallback chain. |
| **Why it's interesting** | Most RAG projects just call an LLM and hope for the best. This project includes a **CI-gated evaluation harness** that blocks PRs if retrieval quality drops, and a **hierarchical fallback** for high-availability LLM generation. |
| **Stack** | Python 3.11 · FastAPI · SQLAlchemy 2.0 · Postgres (pgvector) · Google Gemini · Pytest · Ruff · Mypy · GitHub Actions |

## Contents

- [Highlights](#highlights)
- [Architecture](#architecture)
- [Core guarantees](#core-guarantees)
- [Design decisions](#design-decisions)
- [Quick start](#quick-start)
- [Environment variables](#environment-variables)
- [The Evaluation Harness](#the-evaluation-harness)
- [Testing](#testing)
- [Project structure](#project-structure)
- [Known limitations](#known-limitations)
- [Roadmap](#roadmap)

---

## Highlights

- **CI-Gated Evaluations.** The GitHub Actions pipeline spins up a disposable Postgres instance, runs the migrations, and executes a gold-standard dataset (`eval/gold_set/qa_pairs.json`). If `Recall@K` drops below the threshold, the build fails.
- **Hierarchical LLM Fallbacks.** Gemini models frequently experience 503 (High Demand) or 504 (Timeout) errors. The generator catches these and cascades through `gemini-3.8-flash` → `gemini-3.5-flash-lite` → `gemini-3.6-flash` to guarantee an answer.
- **Idempotent Ingestion.** Document content is hashed (SHA-256) before ingestion. Re-running an ingestion script or retrying a failed webhook will not create duplicate chunks.
- **Strict Type Safety.** 100% coverage with `mypy --strict`. We don't use `Any` as a crutch; even the Gemini SDK responses are typed and validated.
- **Citation-Grounded.** The LLM is strictly prompted to only answer using retrieved context and must cite chunks (`[1]`, `[2]`). If the context doesn't contain the answer, it refuses to hallucinate.
- **Production Containerization.** The entire local stack (Postgres + pgvector) runs in Docker via `docker run` or `docker-compose`.

| Area | What it does |
| :--- | :--- |
| **Ingestion** | Parses text, chunks it with overlap, embeds it, and saves it to Postgres. |
| **Retrieval** | Cosine distance search (`<=>`) using pgvector HNSW indexes. |
| **Generation** | Falls back through 3 Gemini models, generates a streamed answer with citations. |
| **Evaluation** | Calculates Recall@K and Mean Reciprocal Rank (MRR) against a known dataset. |

---

## Architecture

```mermaid
flowchart TD
    Client["Client (Swagger UI / Next.js)"] -->|"POST /query"| API["FastAPI Server"]

    subgraph "Retrieval"
        API -->|"1. Embed Query"| Embedder["Gemini Embedder"]
        Embedder -->|"2. Vector Search"| DB[("Postgres\n(pgvector)")]
    end

    subgraph "Generation"
        DB -->|"3. Return Chunks"| API
        API -->|"4. Prompt with Context"| LLM["Gemini Generator\n(Fallback Chain)"]
    end

    LLM -->|"5. Answer + Citations"| API
    API -->|"6. 200 OK"| Client
```

### Design principles

1. **The database is the source of truth for vectors.** We don't use an in-memory vector store. Postgres + `pgvector` handles millions of embeddings with transactional safety.
2. **Evaluation is a first-class citizen.** You cannot improve what you cannot measure. The eval harness is run both locally and in CI.
3. **Fail gracefully.** LLMs are external dependencies; they will fail. The fallback chain ensures the user always gets an answer.
4. **Strict boundaries.** Pydantic schemas validate the input. Zod-equivalent validation (via Pydantic) ensures the LLM cannot invent actions or hallucinate citations outside the provided context.

## Core guarantees

| Guarantee | Mechanism |
| :--- | :--- |
| No duplicate ingestion | `content_hash` unique constraint on the `documents` table. |
| The AI cannot hallucinate | Prompt explicitly says: "If the answer is not in the context, say 'I don't know'." |
| The API won't crash on LLM outage | The `Generator` catches `Exception` and loops through the `self.models` array. |
| Type safety across the board | `mypy --strict` passes on all source files. |
| CI won't merge regressions | `eval-gate` job fails if `recall_at_k < 0.5`. |

## Design decisions

| Decision | Why | Trade-off |
| :--- | :--- | :--- |
| **Postgres + pgvector, not Pinecone** | Keeps everything in one database; allows transactional rollbacks and RLS. | Requires managing a Postgres instance. |
| **Hierarchical fallbacks for generation** | LLM APIs are prone to 503/504 errors. A fallback chain prevents downtime. | Can result in slightly varying answer quality based on which model succeeds. |
| **Fake Embedder in unit tests** | Integration tests hit the real DB with real embeddings. Unit tests use `mock=True` for speed. | Requires careful dependency injection. |

---

## Quick start

**Prerequisites:** Python 3.11+, Docker Desktop, and a Google Gemini API key.

```bash
git clone https://github.com/shaurya-10000/rag-evals.git
cd rag-evals
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

1. Create a `.env` file:
   ```env
   DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/rag_evals
   GEMINI_API_KEY=your-key-here
   ```

2. Start the database:
   ```bash
   docker run -d --name rag-evals-db -p 5432:5432 -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=rag_evals pgvector/pgvector:pg16
   alembic upgrade head
   ```

3. Start the API:
   ```bash
   uvicorn rag.api.main:app --reload
   ```

Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) for the interactive Swagger UI.

## Environment variables

| Variable | Scope | Required | Purpose |
| :--- | :--- | :---: | :--- |
| `DATABASE_URL` | Server | ✅ | Postgres connection string |
| `GEMINI_API_KEY` | Server | ✅ | Enables embeddings and generation |

## The Evaluation Harness

Most RAG projects only test that the API returns a `200 OK`. We test that the AI returns the **correct** answer.

The `eval/gold_set/qa_pairs.json` file contains known questions and the exact chunks that should be retrieved. The `EvalRunner` calculates:
- **Recall@K**: Did we retrieve the right chunk in the top K results?
- **MRR**: How high did the correct chunk rank?

To run it locally:
```bash
python -m rag.eval.run_eval
```

In CI, this is wired into GitHub Actions. If you submit a PR that degrades the retriever, the `RAG Eval Regression Gate` will fail, preventing the merge.

## Testing

We separate unit tests from integration tests.

```bash
# Run unit tests (Fast, uses mock embedder)
pytest tests/unit

# Run integration tests (Hits the real Docker Postgres)
pytest tests/integration
```

Pre-flight before pushing:
```bash
ruff check .
mypy src
pytest tests/
```

## Project structure

```text
.
├── .github/workflows/ci.yml    # CI pipeline with Eval Gate
├── eval/gold_set/              # Known Q&A pairs for evaluation
├── src/rag/
│   ├── api/                    # FastAPI routes and Pydantic schemas
│   ├── config/                 # Pydantic settings (loads .env)
│   ├── db_models.py            # SQLAlchemy models (Document, Chunk)
│   ├── eval/                   # Metrics (Recall, MRR) and runner
│   ├── generate/               # LLM Generator with fallback chain
│   ├── ingest/                 # Chunking and pipeline
│   ├── migrations/             # Alembic migrations
│   ├── repository.py           # Idempotent DB operations
│   └── retrieve/               # Embedder and pgvector retriever
└── tests/                      # Unit and integration tests
```

## Known limitations

- **No UI yet.** The project is API-first. You interact with it via Swagger UI or curl.
- **Single-table vector search.** We don't yet do hybrid search (BM25 + dense vectors). That's on the roadmap.
- **No observability.** There is no OpenTelemetry or LangSmith tracing yet.

## Roadmap

- [ ] Add a Next.js frontend for a chat interface.
- [ ] Implement Hybrid Search (combine BM25 keyword search with pgvector).
- [ ] Add a Cross-Encoder reranker to improve retrieval quality.
- [ ] Add OpenTelemetry tracing to measure latency per chunk.

---

<div align="center">

**RAG Evals** · built by [@shaurya-10000](https://github.com/shaurya-10000)

</div>