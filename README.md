<div align="center">

# 🧠 RAG Evals

**A production-grade RAG architecture with a CI-gated evaluation harness, hierarchical LLM fallbacks, and strict type safety.**

[![CI & Eval Gate](https://github.com/shaurya-10000/rag-evals/actions/workflows/ci.yml/badge.svg)](https://github.com/shaurya-10000/rag-evals/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](./LICENSE)

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-000000?style=flat-square&logo=nextdotjs&logoColor=white)](https://nextjs.org)
[![Postgres](https://img.shields.io/badge/Postgres-pgvector-4169E1?style=flat-square&logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)
[![Gemini](https://img.shields.io/badge/Google_Gemini-AI-4285F4?style=flat-square&logo=google&logoColor=white)](https://ai.google.dev)

</div>

---

## Overview

|  |  |
| :--- | :--- |
| **What** | A full-stack RAG application that ingests documents, embeds them using Gemini, and retrieves grounded answers with citations via a robust fallback chain. |
| **Why it's interesting** | Most RAG projects just call an LLM and hope for the best. This project includes a **CI-gated evaluation harness** that blocks PRs if retrieval quality drops, a **hierarchical fallback** for high-availability LLM generation, and a **Hybrid Search + Reranker** pipeline. |
| **Stack** | Python 3.11 · FastAPI · SQLAlchemy 2.0 · Postgres (pgvector) · Google Gemini · Next.js 15 · Tailwind CSS · Pytest · Ruff · Mypy · GitHub Actions |

## Contents

- [Demo](#demo)
- [Architecture](#architecture)
- [Core guarantees](#core-guarantees)
- [Design decisions](#design-decisions)
- [The Evaluation Harness](#the-evaluation-harness)
- [Quick start](#quick-start)
- [Environment variables](#environment-variables)
- [Testing](#testing)
- [Project structure](#project-structure)
- [Known limitations](#known-limitations)
- [Roadmap](#roadmap)

---

## Demo

**Live Application:** [rag-evals.vercel.app](https://rag-evals.vercel.app)

> **Note:** The backend is deployed on Render's free tier, which spins down after 15 minutes of inactivity. The first request may take ~30 seconds to cold-start.

## Architecture

```mermaid
flowchart TD
    Client["Next.js Frontend\n(Vercel)"] -->|"POST /query"| API["FastAPI Server\n(Render)"]

    subgraph "Retrieval Pipeline"
        API -->|"1. Embed Query"| Embedder["Gemini Embedder\n(768 dims)"]
        Embedder -->|"2. Hybrid Search"| DB[("PostgreSQL + pgvector\n(Neon)")]
        DB -->|"3. Top 20 Chunks"| Reranker["Cross-Encoder\nReranker"]
        Reranker -->|"4. Top 3 Chunks"| API
    end

    subgraph "Generation Pipeline"
        API -->|"5. Prompt with Context"| LLM["Gemini Generator\n(Fallback Chain)"]
    end

    LLM -->|"6. Answer + Citations"| API
    API -->|"7. 200 OK"| Client
```

### Design principles

1. **The database is the source of truth for vectors.** We don't use an in-memory vector store. Postgres + `pgvector` handles millions of embeddings with transactional safety.
2. **Evaluation is a first-class citizen.** You cannot improve what you cannot measure. The eval harness runs both locally and in CI.
3. **Fail gracefully.** LLMs are external dependencies; they will fail. The fallback chain ensures the user always gets an answer.
4. **Strict boundaries.** Pydantic schemas validate the input. The LLM cannot invent actions or hallucinate citations outside the provided context.

## Core guarantees

| Guarantee | Mechanism |
| :--- | :--- |
| No duplicate ingestion | `content_hash` unique constraint on the `documents` table. |
| The AI cites its sources | Prompt explicitly says: "Cite the context chunks you use by writing [1], [2]." |
| The API won't crash on LLM outage | The `Generator` catches `Exception` and loops through the `self.models` array. |
| Type safety across the board | `mypy --strict` passes on all source files. |
| CI won't merge regressions | `eval-gate` job fails if `recall_at_k < 0.7`. |

## Design decisions

| Decision | Why | Trade-off |
| :--- | :--- | :--- |
| **Postgres + pgvector, not Pinecone** | Keeps everything in one database; allows transactional rollbacks and RLS. | Requires managing a Postgres instance. |
| **Hybrid Search (BM25 + Vector)** | Dense vectors miss exact keyword matches (SKUs, names, acronyms). BM25 fixes this. | Adds a `tsvector` column and GIN index. |
| **Cross-Encoder Reranker** | Bi-encoders (vector search) are fast but imprecise. Cross-encoders are slow but highly accurate. | Adds ~200ms to the query time. |
| **Hierarchical fallbacks** | LLM APIs are prone to 503/504 errors. A fallback chain prevents downtime. | Can result in slightly varying answer quality based on which model succeeds. |

---

## The Evaluation Harness

Most RAG projects only test that the API returns a `200 OK`. We test that the AI returns the **correct** answer.

The `eval/gold_set/qa_pairs.json` file contains known questions and the exact chunks that should be retrieved. The `EvalRunner` calculates:
- **Recall@K**: Did we retrieve the right chunk in the top K results?
- **MRR**: How high did the correct chunk rank?

### Current Metrics

On our synthetic gold set of 18 questions (generated from 20 distinct facts), the Hybrid Search + Reranker pipeline achieves:

| Metric | Score |
| :--- | :--- |
| **Recall@3** | 1.00 (100%) |
| **MRR** | 1.00 (100%) |

This is a **perfect score**, meaning the correct chunk was always retrieved in the top 3, and always ranked first.

To run it locally:
```bash
python -m rag.eval.run_eval
```

In CI, this is wired into GitHub Actions. If you submit a PR that degrades the retriever, the `RAG Eval Regression Gate` will fail, preventing the merge.

## Quick start

**Prerequisites:** Python 3.11+, Docker Desktop, Node.js 20+, and a Google Gemini API key.

```bash
git clone https://github.com/shaurya-10000/rag-evals.git
cd rag-evals

# Backend setup
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

# Frontend setup
cd web
npm install
cd ..

# Start the database
docker run -d --name rag-evals-db -p 5432:5432 -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=rag_evals pgvector/pgvector:pg16
alembic upgrade head
```

1. Create a `.env` file:
   ```env
   DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/rag_evals
   GEMINI_API_KEY=your-key-here
   ```

2. Start the backend:
   ```bash
   uvicorn rag.api.main:app --reload
   ```

3. Start the frontend (in a new terminal):
   ```bash
   cd web
   npm run dev
   ```

Open [http://localhost:3000](http://localhost:3000) to use the chat interface.

## Environment variables

| Variable | Scope | Required | Purpose |
| :--- | :--- | :---: | :--- |
| `DATABASE_URL` | Backend | ✅ | Postgres connection string |
| `GEMINI_API_KEY` | Backend | ✅ | Enables embeddings and generation |
| `NEXT_PUBLIC_BACKEND_URL` | Frontend | ✅ | The URL of the deployed backend API |

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
│   └── retrieve/               # Hybrid Retriever and Embedder
├── web/                        # Next.js frontend
└── tests/                      # Unit and integration tests
```

## Known limitations

- **No streaming responses.** The Next.js UI waits for the full response before displaying it.
- **Cold starts on Render.** The free tier spins down after 15 minutes. The first request takes ~30 seconds.

## Roadmap

- [ ] Add streaming SSE responses for a better UX.
- [ ] Implement RAGAS for generation metrics (Faithfulness, Answer Relevance).
- [ ] Add user authentication (Clerk or Supabase Auth).

---

<div align="center">

**RAG Evals** · built by [@shaurya-10000](https://github.com/shaurya-10000)

</div>