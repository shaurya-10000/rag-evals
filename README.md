<div align="center">

# 🧠 RAG Evals

**A production-grade multi-tenant RAG architecture with per-user isolation, self-hosted JWT auth, real-time SSE streaming, and a CI-gated evaluation harness.**

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
| **What** | A multi-tenant RAG SaaS where each user signs up, ingests their own documents (text/PDF/images), and chats with a private knowledge base. Includes streaming SSE responses, self-hosted auth, and CI-gated evaluation. |
| **Why it's interesting** | Most RAG projects are toy demos. This one has **per-user document isolation** (Alice can't see Bob's documents), **self-hosted JWT auth** (Argon2 + HttpOnly cookies), **multi-modal ingestion** (Vision), a **51-question evaluation harness** with CI gating, **real-time SSE streaming**, **rate limiting**, and a **Hybrid Search + Multithreaded Reranker** pipeline. |
| **Stack** | Python 3.11 · FastAPI · SQLAlchemy 2.0 · Postgres (pgvector) · Google Gemini (Vision + Text) · Next.js 15 · Tailwind CSS · Pwdlib/Argon2 · python-jose · SlowAPI · Pytest · Ruff · Mypy · GitHub Actions |

## Contents

- [Demo](#demo)
- [Architecture](#architecture)
- [Core guarantees](#core-guarantees)
- [Security & multi-tenancy](#security--multi-tenancy)
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
    Client["Next.js Frontend\n(Vercel)"] -->|"Sign Up / Sign In"| AuthAPI["FastAPI /auth"]
    AuthAPI -->|"Argon2 + JWT"| DB[("PostgreSQL\nUsers + Documents")]
    AuthAPI -->|"HttpOnly Cookie"| Client

    Client -->|"Text / PDF / Image\n(JWT + X-API-Key)"| IngestAPI["FastAPI /ingest"]

    subgraph "Ingestion Pipeline (per-user)"
        IngestAPI -->|"PDF/MD/TXT"| PDFParser["PDF & Text Parser"]
        IngestAPI -->|"PNG/JPG"| VisionAPI["Gemini Vision\n(Image to Text)"]
        PDFParser --> Chunker["Sentence-Aware\nChunker"]
        VisionAPI --> Chunker
        Chunker --> Embedder["Gemini Embedder\n(768 dims)"]
        Embedder --> DB
    end

    Client -->|"POST /query (SSE)\n(JWT + X-API-Key)"| QueryAPI["FastAPI /query"]

    subgraph "Retrieval Pipeline (scoped to current user)"
        QueryAPI -->|"1. Embed Query"| Embedder
        Embedder -->|"2. Hybrid Search\nWHERE user_id = current"| DB
        DB -->|"3. Top 10 Chunks"| Reranker["Multithreaded\nCross-Encoder Reranker"]
        Reranker -->|"4. Top 3 Relevant Chunks"| QueryAPI
    end

    subgraph "Generation Pipeline"
        QueryAPI -->|"5. Prompt with Context"| LLM["Gemini Generator\n(Fallback Chain)"]
    end

    LLM -->|"6. Streamed Tokens + Citations"| QueryAPI
    QueryAPI -->|"7. SSE Stream"| Client
```

### Design principles

1. **Multi-tenant by default.** Every document has a `user_id`. Every query filters by `user_id`. Alice cannot see Bob's documents, even if they have the same content.
2. **The database is the source of truth for vectors.** Postgres + `pgvector` handles millions of embeddings with transactional safety.
3. **Evaluation is a first-class citizen.** The eval harness runs both locally and in CI.
4. **Fail gracefully.** LLMs fail; the fallback chain ensures the user still gets an answer. Vision models fall back to lighter models.
5. **Security by default.** JWT auth, Argon2 hashing, rate limiting, upload size caps, and API key defense-in-depth.

## Core guarantees

| Guarantee | Mechanism |
| :--- | :--- |
| No cross-user data leakage | Every query joins `documents` on `user_id = current_user.id`. |
| No duplicate ingestion per user | Composite `UNIQUE(user_id, content_hash)` constraint on `documents`. |
| Same document for different users | Two users can upload the same file independently. Each gets their own `documents` row. |
| The AI cites its sources | Prompt explicitly says: "Cite the context chunks you use by writing [1], [2]." |
| The API won't crash on LLM outage | The `Generator` catches `Exception` and loops through the `self.models` array. |
| Multi-modal support | PDFs and Images are parsed into text (via PyPDF and Gemini Vision) before embedding. |
| Real-time streaming | The `/query` endpoint returns an SSE `StreamingResponse`, and the UI renders tokens as they arrive. |
| Type safety across the board | `mypy --strict` passes on all source files. |
| CI won't merge regressions | `eval-gate` job fails if `recall_at_k < 0.7`. |

## Security & multi-tenancy

| Layer | Mechanism |
| :--- | :--- |
| **Authentication** | Self-hosted JWT (HS256) with Argon2 password hashing via `pwdlib`. |
| **Sessions** | HttpOnly cookies with 7-day expiry. JavaScript cannot read them (XSS-resistant). |
| **Route Protection** | Next.js `middleware.ts` verifies the JWT before rendering protected routes. |
| **Per-user isolation** | Every `Document` has a `user_id` FK. The retriever filters by `current_user.id` on every query. |
| **API Keys** | `/ingest` and `/query` require `X-API-Key` header (defense in depth against direct API abuse). |
| **Rate Limiting** | `slowapi` limits `/query` to 5 req/min and `/ingest` to 3 req/min per IP. |
| **Upload Size** | Files > 10MB rejected with `413 Payload Too Large`. |

## Design decisions

| Decision | Why | Trade-off |
| :--- | :--- | :--- |
| **Postgres + pgvector, not Pinecone** | Keeps everything in one database; allows transactional rollbacks and per-user RLS. | Requires managing a Postgres instance. |
| **Self-hosted JWT (not Clerk/Auth0)** | Zero external dependency; users stored in your own Postgres. | You own account recovery, password reset, OAuth (if added). |
| **Argon2, not bcrypt** | OWASP-recommended. No 72-byte limit. GPU-resistant. | Slightly slower hashing (which is the point). |
| **Composite unique constraint `(user_id, content_hash)`** | Two users uploading the same file get independent rows. | Slightly more complex migration than a global unique index. |
| **Hybrid Search (BM25 + Vector)** | Dense vectors miss exact keyword matches (SKUs, names, acronyms). | Adds a `tsvector` column and GIN index. |
| **Multithreaded Cross-Encoder Reranker** | Bi-encoders are fast but imprecise. Cross-encoders are slow but accurate. We multithread ONNX to drop latency from 28s → ~200ms. | Requires CPU cores to run efficiently. |
| **Sentence-Aware Chunking** | Splitting by arbitrary characters cuts words in half. | Slightly more complex than a character loop. |
| **Server-Sent Events (SSE)** | Real-time streaming; perceived latency drops from seconds to milliseconds. | Requires the Next.js route to proxy without buffering. |

---

## The Evaluation Harness

Most RAG projects only test that the API returns a `200 OK`. We test that the AI returns the **correct** answer.

The `eval/gold_set/qa_pairs.json` file contains **51 curated questions** in four categories:
- **Direct** (20): Exact keyword lookups.
- **Paraphrased** (15): Same meaning, different words.
- **Multi-fact** (10): Requires chaining two pieces of information.
- **Unanswerable** (6): Questions the document cannot answer (used for hallucination testing).

The `EvalRunner` calculates:
- **Recall@K**: Did we retrieve the right chunk in the top K results?
- **MRR**: How high did the correct chunk rank?

### Current Metrics

| Metric | Score |
| :--- | :--- |
| **Recall@3** | 0.77 (77%) |
| **MRR** | 0.65 (65%) |
| **Questions Evaluated** | 45 (6 unanswerable skipped) |

*(Note: The score dropped from a perfect 1.0 after moving to sentence-aware chunking and harder questions. This is well above our CI threshold of 0.7).*

To run it locally:
```bash
python -m rag.eval.run_eval
```

In CI, this is wired into GitHub Actions. If you submit a PR that degrades the retriever below 0.7 recall, the `RAG Eval Regression Gate` will fail.

## Quick start

**Prerequisites:** Python 3.11+, Docker Desktop, Node.js 20+, and a Google Gemini API key.

```bash
git clone https://github.com/shaurya-10000/rag-evals.git
cd rag-evals

# Backend setup
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pip install "pwdlib[argon2]" python-jose[cryptography] "pydantic[email]" python-multipart slowapi

# Frontend setup
cd web
npm install
npm install jose
cd ..

# Start the database
docker run -d --name rag-evals-db -p 5432:5432 -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=rag_evals pgvector/pgvector:pg16
alembic upgrade head
```

1. Create a `.env` file (root):
   ```env
   DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/rag_evals
   GEMINI_API_KEY=your-key-here
   RAG_API_KEY=<random-32-char-string>
   JWT_SECRET=<random-32-char-string>
   ```

2. Create `web/.env.local`:
   ```env
   NEXT_PUBLIC_BACKEND_URL=http://127.0.0.1:8000
   NEXT_PUBLIC_RAG_API_KEY=<same-as-RAG_API_KEY>
   JWT_SECRET=<same-as-JWT_SECRET>
   ```

3. Start the backend:
   ```bash
   uvicorn rag.api.main:app --reload
   ```

4. Start the frontend (in a new terminal):
   ```bash
   cd web
   npm run dev
   ```

Open [http://localhost:3000](http://localhost:3000). You'll be redirected to `/sign-in` → click "Create one" → sign up with username, email, password.

## Environment variables

| Variable | Scope | Required | Purpose |
| :--- | :--- | :---: | :--- |
| `DATABASE_URL` | Backend | ✅ | Postgres connection string |
| `GEMINI_API_KEY` | Backend | ✅ | Enables embeddings, vision, and generation |
| `RAG_API_KEY` | Backend | ✅ | Protects `/ingest` and `/query` from direct abuse |
| `JWT_SECRET` | Backend | ✅ | Signs/verifies auth tokens |
| `NEXT_PUBLIC_BACKEND_URL` | Frontend | ✅ | The URL of the deployed backend API |
| `NEXT_PUBLIC_RAG_API_KEY` | Frontend | ✅ | Must match `RAG_API_KEY` |
| `JWT_SECRET` | Frontend | ✅ | Must match backend `JWT_SECRET` |

## Testing

```bash
# Unit tests (fast, mock embedder)
pytest tests/unit

# Integration tests (real Postgres)
pytest tests/integration

# Pre-flight before pushing
ruff check .
mypy src
pytest tests/
```

## Project structure

```text
.
├── .github/workflows/ci.yml    # CI pipeline with Eval Gate
├── eval/gold_set/              # 51 curated Q&A pairs
├── src/rag/
│   ├── api/                    # FastAPI routes (multi-modal + SSE + auth)
│   ├── auth/                   # JWT + Argon2 password utilities
│   ├── config/                 # Pydantic settings
│   ├── db_models.py            # User, Document, Chunk models
│   ├── eval/                   # Metrics (Recall, MRR) and runner
│   ├── generate/               # Streaming LLM + Multithreaded Reranker
│   ├── ingest/                 # Sentence-aware chunking
│   ├── migrations/             # Alembic migrations
│   ├── repository.py           # Idempotent DB operations (per-user)
│   └── retrieve/               # Hybrid Retriever (scoped by user_id)
├── web/                        # Next.js frontend (auth + tabbed UI)
└── tests/                      # Unit and integration tests
```

## Known limitations

- **Cold starts on Render.** The free tier spins down after 15 minutes. First request takes ~30s.
- **Free-tier Gemini quotas.** Vision and generation have strict daily limits on the free tier.
- **No password reset flow.** If a user forgets their password, they can't recover their account yet (no email service configured).
- **No OAuth (Google/GitHub).** Users must sign up with email/password.

## Roadmap

- [x] Real-time SSE streaming
- [x] Multi-modal ingestion (PDF, Images)
- [x] Self-hosted JWT auth with Argon2
- [x] Per-user document isolation
- [x] Rate limiting + upload limits
- [ ] Password reset flow (requires email service)
- [ ] OAuth (Google Sign-In)
- [ ] RAGAS generation metrics (Faithfulness, Answer Relevance)
- [ ] Persistent chat history in Postgres

---

<div align="center">

**RAG Evals** · built by [@shaurya-10000](https://github.com/shaurya-10000)

</div>