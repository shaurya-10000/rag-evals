<div align="center">

# &#129504; RAG Evals

**A multi-tenant RAG app with per-user isolation, self-hosted JWT auth, streaming answers with clickable citations, background imports, and a CI-gated evaluation harness.**

[![CI & Eval Gate](https://github.com/shaurya-10000/rag-evals/actions/workflows/ci.yml/badge.svg)](https://github.com/shaurya-10000/rag-evals/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](./LICENSE)

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-000000?style=flat-square&logo=nextdotjs&logoColor=white)](https://nextjs.org)
[![Postgres](https://img.shields.io/badge/Postgres-pgvector-4169E1?style=flat-square&logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)
[![Gemini](https://img.shields.io/badge/Google_Gemini-AI-4285F4?style=flat-square&logo=google&logoColor=white)](https://ai.google.dev)
[![Tailwind](https://img.shields.io/badge/Tailwind_CSS-38B2AC?style=flat-square&logo=tailwind-css&logoColor=white)](https://tailwindcss.com)

</div>

---

## Overview

|  |  |
| :--- | :--- |
| **What** | A multi-tenant RAG app. Each user signs up, imports their own documents (text, files or web pages) and chats with a private knowledge base. Answers stream in real time with clickable citations. |
| **Why it's interesting** | Per-user isolation on every query, self-hosted auth with revocable sessions, SSRF-guarded URL import, background imports with progress, query rewriting for follow-up questions, a relevance gate that refuses instead of guessing, answer feedback, shareable chats, request-id tracing with per-answer latency, and an evaluation harness that gates CI. |
| **Stack** | Python 3.11, FastAPI, SQLAlchemy 2.0, Postgres (pgvector), Google Gemini, Next.js 16, Tailwind CSS v4, Framer Motion, Argon2, python-jose, SlowAPI, Pytest, Ruff, Mypy, GitHub Actions |

## Contents

- [Demo](#demo)
- [Features](#features)
- [Architecture](#architecture)
- [Core guarantees](#core-guarantees)
- [Security and multi-tenancy](#security-and-multi-tenancy)
- [Observability](#observability)
- [Design decisions](#design-decisions)
- [API overview](#api-overview)
- [The evaluation harness](#the-evaluation-harness)
- [Quick start](#quick-start)
- [Environment variables](#environment-variables)
- [Deployment](#deployment)
- [Testing](#testing)
- [Project structure](#project-structure)
- [Known limitations](#known-limitations)
- [Roadmap](#roadmap)

---

## Demo

**Live application:** [rag-evals.vercel.app](https://rag-evals.vercel.app)

> **Note:** The backend runs on Render's free tier, which spins down after 15 minutes of inactivity. The first request can take about 30 seconds to cold-start.

## Features

**Chat**
- Streaming answers (SSE) with numbered citations. Clicking a citation opens the source passage and can jump to the document.
- **Follow-up rewriting:** a question like "what about its pricing?" is rewritten into a standalone search query using the recent conversation.
- **Refusal threshold:** when the best reranker score is below a threshold, the app says nothing relevant was found instead of guessing, and skips generation.
- **Answer feedback:** thumbs up/down with an optional comment on any answer.
- **Chat search and export**, pinned chats, auto-generated titles, text-to-speech.
- **Share links:** publish a read-only snapshot of a chat at an unguessable URL and stop sharing at any time.

**Knowledge base**
- **Import** pasted text, files (PDF, DOCX, PPTX, CSV, TXT, Markdown, images) or a **web page URL**.
- Imports run as **background jobs** with a progress bar (extracting, embedding, saving), so large documents never block the request.
- **Document library** with search, rename, full-text editing (re-chunked and re-embedded safely) and **collections**. Chats can be scoped to one collection.

**Account**
- Email/password sign-up with email verification, password reset, and Google sign-in.
- **Account settings:** change password, see active sessions and sign out any device, delete the account and all its data.
- **Usage tab:** documents, passages, questions per day, refused answers, helpful-answer rate, import history and the limits that apply to you.

## Architecture

```mermaid
flowchart TD
    Client["Next.js frontend\n(Vercel)"] -->|"Sign up / sign in"| AuthAPI["FastAPI /auth"]
    AuthAPI -->|"Argon2 + JWT + session row"| DB[("PostgreSQL\nusers, documents, chats")]
    AuthAPI -->|"HttpOnly cookie"| Client

    Client -->|"Text / file / URL\n(JWT + X-API-Key)"| JobsAPI["FastAPI /ingest/jobs\n(202 + progress)"]

    subgraph "Background import (per user)"
        JobsAPI --> Extract["Extract\nPDF, DOCX, PPTX, CSV, web page, image"]
        Extract --> Chunker["Sentence-aware chunker"]
        Chunker --> Embedder["Gemini embedder\n(768 dims, timeout + retry)"]
        Embedder --> DB
    end

    Client -->|"POST /query (SSE)"| QueryAPI["FastAPI /query"]

    subgraph "Answer pipeline (scoped to the current user)"
        QueryAPI -->|"1. Rewrite follow-up"| Rewriter["Query rewriter"]
        Rewriter -->|"2. Hybrid search\nWHERE user_id = current"| DB
        DB -->|"3. Top 10 chunks"| Reranker["Cross-encoder reranker"]
        Reranker -->|"4. Best score vs threshold"| Gate{"Relevant?"}
        Gate -->|"yes: top 3"| LLM["Gemini generator\n(fallback chain)"]
        Gate -->|"no"| Refusal["Nothing relevant found"]
    end

    LLM -->|"Streamed tokens + citations"| QueryAPI
    Refusal --> QueryAPI
    QueryAPI -->|"SSE"| Client
```

### Design principles

1. **Multi-tenant by default.** Every document has a `user_id`, and every query filters by it.
2. **The database is the source of truth for vectors.** Postgres + `pgvector` gives transactional safety.
3. **Evaluation is a first-class citizen.** Retrieval is gated in CI, generation quality is measured locally.
4. **Fail gracefully.** LLMs fail, so the generator has a fallback chain, the embedder retries with backoff and a timeout, and the app refuses rather than guesses.
5. **Make slow work visible.** Long imports are background jobs with progress, and every answer logs its own latency breakdown.

## Core guarantees

| Guarantee | Mechanism |
| :--- | :--- |
| No cross-user data leakage | Every query joins `documents` on `user_id = current_user.id`. Another user's ids return 404. |
| No duplicate ingestion per user | `UNIQUE(user_id, content_hash)` on `documents`. Two users can still import the same file independently. |
| The AI cites its sources | The prompt requires `[1]`, `[2]` citations, and each citation is a snapshot that survives later edits or deletion. |
| No confident guessing | Below the relevance threshold the app refuses and skips generation. |
| The API survives LLM outages | The generator loops through a model fallback chain. The embedder retries transient errors and timeouts. |
| Editing never loses data | New text is chunked and embedded *before* old chunks are deleted, then swapped in one transaction. |
| Imports survive restarts cleanly | Jobs interrupted by a restart are marked failed on startup instead of hanging as "running". |
| Type safety | `mypy --strict` passes on all source files. |
| CI won't merge retrieval regressions | The `eval-gate` job fails if `recall_at_k < 0.7`. |

## Security and multi-tenancy

| Layer | Mechanism |
| :--- | :--- |
| **Authentication** | Self-hosted JWT (HS256), Argon2 password hashing via `pwdlib`. |
| **Sessions** | HttpOnly cookie, 7-day expiry. Each login creates a revocable session row whose id is inside the JWT and checked on every request. A rejected session is also cleared from the browser. |
| **Session control** | Account settings list devices and sign any of them out. Changing or resetting a password signs out every other device. |
| **Email verification** | Email/password accounts must verify before signing in. Single-use links, 24h expiry, only a SHA-256 hash stored. |
| **Password reset** | Single-use link, 30 min expiry, identical response whether or not the account exists. |
| **Google sign-in** | Server-side OAuth code flow with a state cookie. Accounts link by email only when Google reports it verified. |
| **Account deletion** | Requires the email (and password) as confirmation, then removes the user's chunks, documents, chats, shares, imports and sessions. |
| **Route protection** | Next.js `proxy.ts` verifies the JWT before rendering protected routes. |
| **API key** | All data endpoints require `X-API-Key`, held only by the Next.js server. |
| **SSRF guard** | URL import validates every redirect hop, resolves the host once, refuses non-public addresses and pins the connection to the validated IP. |
| **Rate limiting** | SlowAPI, **per signed-in user** (not per shared proxy IP). Unauthenticated routes are limited per visitor address, which the web app forwards and the API trusts only alongside the API key. See the table below. |
| **Upload limits** | 10 MB per file at the API, 4 MB through the web app (Vercel's request body cap), 500,000 characters of extracted text, zip-bomb checks on DOCX/PPTX. |

| Route | Limit |
| :--- | :--- |
| `POST /query` | 5 per minute per user |
| `POST /ingest/jobs` | 10 per minute, at most 3 active imports per user |
| `PATCH /documents/{id}` | 10 per minute (each content edit re-embeds) |
| `/auth/login`, `/auth/register` | 10 per minute per visitor |
| `/auth/forgot-password`, `/auth/resend-verification` | 5 per minute per visitor |
| `POST /account/password` | 5 per minute |
| `POST /account/delete` | 3 per minute |

## Observability

- **Request ids.** Every request gets an id (the web app sends one, otherwise the API generates it). It is on every log line and returned in the `X-Request-ID` response header.
- **Structured logs.** JSON in production (`LOG_FORMAT=json`), readable text in development. Each request logs method, path, status and `duration_ms` once the response, including a streamed one, has finished.
- **Per-answer latency.** Each answer logs an `answer_complete` line with `timings_ms` (rewrite, retrieve, rerank, generate, total), the refusal flag, the best rerank score and the number of sources. The same `timings_ms` is sent to the client in the stream's `done` event.

## Design decisions

| Decision | Why | Trade-off |
| :--- | :--- | :--- |
| **Postgres + pgvector** | One database, transactional rollbacks, per-user filtering in SQL. | You manage a Postgres instance. |
| **Self-hosted JWT + session rows** | No external dependency, and sessions can still be revoked. | One extra lookup per request. |
| **Argon2, not bcrypt** | OWASP-recommended, no 72-byte limit, GPU-resistant. | Slightly slower hashing. |
| **Hybrid search (BM25 + vector) with RRF** | Dense vectors miss exact keywords (SKUs, names, acronyms). | A `tsvector` column and GIN index. |
| **Cross-encoder reranker** | Bi-encoders are fast but imprecise. Cross-encoders are accurate. | Needs CPU, so the model is pre-loaded at startup. |
| **Refuse below a score threshold** | A wrong confident answer is worse than "not found". | The threshold needs tuning (`REFUSAL_MIN_SCORE`). |
| **Background import jobs** | Embedding a large file can take minutes. | A small in-process worker pool (2 workers), not a distributed queue. |
| **SSE streaming** | Perceived latency drops from seconds to milliseconds. | The Next.js route must proxy without buffering. |
| **Pure ASGI request middleware** | `BaseHTTPMiddleware` interferes with streaming responses. | Slightly more code. |

## API overview

All endpoints require `X-API-Key` and the auth cookie unless noted, and are scoped to the current user.

| Area | Endpoints |
| :--- | :--- |
| **Auth** (no API key) | `POST /auth/register`, `login`, `logout`, `verify-email`, `resend-verification`, `forgot-password`, `reset-password`, `oauth/exchange`, `GET /auth/google/login`, `/auth/google/callback` |
| **Account** | `GET /account`, `POST /account/password`, `POST /account/delete`, `GET /account/sessions`, `DELETE /account/sessions/{id}`, `POST /account/sessions/revoke-others` |
| **Query** | `POST /query` (SSE; optional `conversation_id`, `collection_id`, `top_k`) |
| **Imports** | `POST /ingest/jobs` (JSON text or URL, or multipart file), `GET /ingest/jobs`, `GET /ingest/jobs/{id}` |
| **Documents** | `GET /documents` (`collection_id`, `unfiled`, `q`), `GET/PATCH/DELETE /documents/{id}`, `PUT /documents/{id}/collection` |
| **Collections** | `GET/POST /collections`, `PATCH/DELETE /collections/{id}` (`?delete_documents=true`) |
| **Chats** | `GET/POST /conversations`, `GET/PATCH/DELETE /conversations/{id}`, `POST /conversations/import`, `GET /search/conversations?q=` |
| **Feedback** | `PUT/DELETE /conversations/{id}/messages/{message_id}/feedback` |
| **Sharing** | `GET/POST/DELETE /conversations/{id}/share`, `GET /shared/{token}` (read-only, API key only) |
| **Usage** | `GET /usage` |

## The evaluation harness

`eval/gold_set/qa_pairs.json` holds **51 curated questions**: direct lookups, paraphrases, multi-fact questions and unanswerable ones (used to test refusal).

### Retrieval (runs in CI)

`EvalRunner` calculates **Recall@K** and **MRR** over the 45 answerable questions.

| Metric | Score |
| :--- | :--- |
| **Recall@3** | 0.77 (77%) |
| **MRR** | 0.65 (65%) |
| **Questions evaluated** | 45 (6 unanswerable skipped) |

CI replays **recorded real Gemini embeddings** from `eval/fixtures/embeddings.json`, so the gate is deterministic and needs no API quota. Regenerate the fixtures whenever the gold set or chunking changes:

```bash
python -m rag.eval.generate_fixtures   # needs GEMINI_API_KEY, paces itself under the free tier
python -m rag.eval.run_eval            # same check CI runs; exits 1 if recall < 0.7
```

### Generation quality (runs locally)

`run_generation_eval` scores faithfulness (share of answer claims supported by the retrieved context), answer relevance (1-5, rescaled to 0-1) with an LLM judge, plus false-refusal and correct-refusal rates:

```bash
python -m rag.eval.run_generation_eval --limit 10 --sleep 6
```

Results are written to `eval/results/generation_latest.json` after every question, a question that hangs is abandoned after `--question-timeout` seconds, and `--scores-only` tunes the refusal threshold without any generation calls. It costs several Gemini calls per question, so it is not part of CI. Published numbers are pending a full run.

<!-- generation-eval:start -->
### Generation eval results

Last run on 2026-11-21 against the -question gold set (`python -m rag.eval.run_generation_eval`) with a refusal threshold of -8. Answers were generated by `gemini-3.5-flash-lite` and judged by `gemini-3.5-flash-lite` (the models that responded quickly at run time). Per-question results: [`eval/results/generation_2026-11-21.json`](./eval/results/generation_2026-11-21.json).

| Metric | Result |
| :--- | :--- |
| Faithfulness (mean, 30 answers judged) | 0.99 |
| Answer relevance (mean, 31 answers judged) | 0.83 |
| Answerable questions refused | 16% |
| Unanswerable questions refused | 100% |

The scores come from a Gemini judge, so treat them as indicative: the judge belongs to the same model family as the generator, and a free-tier run can skip judgments when the API is busy (the counts above show how many were judged).
<!-- generation-eval:end -->

## Quick start

**Prerequisites:** Python 3.11+, Docker Desktop, Node.js 20+, a Google Gemini API key.

```bash
git clone https://github.com/shaurya-10000/rag-evals.git
cd rag-evals

# Backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
docker compose up -d db
alembic upgrade head

# Frontend
cd web && npm install && cd ..
```

1. Create `.env` in the repo root (see `.env.example` for every option):
   ```env
   DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/rag_evals
   GEMINI_API_KEY=your-key-here
   RAG_API_KEY=<random-32-char-string>
   JWT_SECRET=<random-32-char-string>
   ```
2. Create `web/.env.local`:
   ```env
   NEXT_PUBLIC_BACKEND_URL=http://127.0.0.1:8000
   RAG_API_KEY=<same-as-RAG_API_KEY>
   JWT_SECRET=<same-as-JWT_SECRET>
   ```
3. Start the backend: `uvicorn rag.api.main:app --reload`
4. Start the frontend: `cd web && npm run dev`

Open [http://localhost:3000](http://localhost:3000), choose "Create one" and sign up. Without a Brevo key, verification and reset links are printed in the backend console.

## Environment variables

| Variable | Scope | Required | Purpose |
| :--- | :--- | :---: | :--- |
| `DATABASE_URL` | Backend | Yes | Postgres connection string |
| `GEMINI_API_KEY` | Backend | Yes | Embeddings, vision, generation, titles, query rewriting |
| `RAG_API_KEY` | Backend + web | Yes | Shared secret between the web server and the API (must match) |
| `JWT_SECRET` | Backend + web | Yes | Signs and verifies auth tokens (must match) |
| `NEXT_PUBLIC_BACKEND_URL` / `BACKEND_URL` | Web | Yes | Backend URL (`BACKEND_URL` is server-only and preferred) |
| `ENVIRONMENT` | Backend | Prod | `production` rejects the dev default secrets and switches logs to JSON |
| `FRONTEND_URL`, `BACKEND_PUBLIC_URL` | Backend | Prod | Public URLs for email links and the Google OAuth redirect |
| `BREVO_API_KEY`, `EMAIL_FROM_ADDRESS` | Backend | Prod | Verification and reset emails |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Backend | Optional | Enables Google sign-in |
| `REFUSAL_MIN_SCORE` | Backend | Optional | Reranker score below which the app refuses (default -8.0) |
| `RERANK_ENABLED`, `RERANK_CANDIDATES` | Backend | Optional | Turn the reranker off, or change how many candidates it scores |
| `LOG_FORMAT`, `LOG_LEVEL` | Backend | Optional | `json` or `text`, and the log level |
| `EMBED_TIMEOUT_MS` | Backend | Optional | Per-request embedding timeout before a retry (default 30000) |

## Deployment

- **Backend (Render, Docker).** The container runs `alembic upgrade head` before starting `uvicorn`, so a deploy that adds a migration applies it automatically and a failed migration stops the deploy instead of serving a broken schema. If the service has a custom Start Command, include the same `alembic upgrade head &&` prefix. Set `ENVIRONMENT=production` and the variables above.
- **Frontend (Vercel).** Set `BACKEND_URL`, `RAG_API_KEY` and `JWT_SECRET`. Vercel rejects request bodies above about 4.5 MB, which is why the web app limits uploads to 4 MB.
- **CI.** Three jobs: Python lint/types/unit tests, integration tests plus the retrieval eval gate against a pgvector service, and web lint/build/type-check.

## Testing

```bash
pytest tests/unit          # fast, no database
pytest tests/integration   # real Postgres, mocked AI

# Pre-flight before pushing
ruff check . && ruff format --check . && mypy src
cd web && npm run lint && npm run build && npx tsc --noEmit
```

## Project structure

```text
.
|-- .github/workflows/ci.yml     # lint, types, tests, eval gate, web build
|-- eval/gold_set/               # 51 curated Q&A pairs
|-- eval/fixtures/               # recorded embeddings for a deterministic CI eval
|-- src/rag/
|   |-- api/                     # routes: auth, account, query, ingest_jobs, documents, conversations,
|   |                            #   feedback, search, shares, usage, title; deps and rate-limit keys
|   |-- auth/                    # JWT, Argon2, single-use tokens, revocable sessions, Google OAuth
|   |-- eval/                    # retrieval metrics, generation metrics (LLM judge), runners, fixtures
|   |-- generate/                # streaming generator, query rewriter, reranker, relevance gate
|   |-- ingest/                  # extractors, SSRF-guarded web fetch, chunking, background jobs
|   |-- retrieve/                # embedder (timeout + retry) and hybrid retriever
|   |-- migrations/              # Alembic
|   |-- observability.py         # request ids, JSON logs, request timing
|   `-- repository.py, chat_repository.py, share_repository.py, usage.py
|-- web/                         # Next.js frontend
|   |-- src/app/                 # pages (chat, sign-in, settings, shared chats) and API proxies
|   |-- src/components/          # chat, ingest, documents, usage, user menu
|   `-- src/lib/                 # backend/auth/account proxies, SSE, citations, export
`-- tests/                       # unit and integration tests
```

## Known limitations

- **Cold starts on Render.** The free tier spins down after 15 minutes, so the first request takes about 30 seconds.
- **Free-tier Gemini quotas.** Embedding, generation and judging have daily limits. CI avoids them with recorded embeddings.
- **Uploads through the web app are capped at 4 MB** by Vercel's request body limit. Larger files need splitting, pasting as text, or importing from a URL (up to 10 MB).
- **Rate limits are in memory.** They reset on restart and are not shared between instances. Moving to a shared store (for example Redis) is needed before scaling out.
- **Sessions are tracked from the release that introduced them.** Older cookies keep working until they expire but do not appear in the session list.
- **Edits re-embed the whole document**, which costs embedding calls.
- **Email limits.** Brevo's free tier allows about 300 emails per day from one verified sender, so messages may land in spam.

## Roadmap

- [x] Streaming answers, clickable citations, source panel
- [x] Multi-modal and multi-format import: PDF, DOCX, PPTX, CSV, images, web pages
- [x] Background imports with progress
- [x] Query rewriting and a refusal threshold
- [x] Answer feedback, chat search and export, share links, usage tab
- [x] Persistent chats, document library and collections
- [x] Self-hosted auth: email verification, password reset, Google sign-in
- [x] Account settings: change password, active sessions, delete account
- [x] Per-user rate limits
- [x] Request ids, structured logs and per-answer latency
- [x] Generation metrics script (faithfulness, answer relevance)
- [ ] Publish a full generation-metrics run and tune the refusal threshold from it
- [ ] Direct-to-backend uploads for files above 4 MB
- [ ] Shared rate-limit store for multi-instance deploys

---

<div align="center">

**RAG Evals** | built by [@shaurya-10000](https://github.com/shaurya-10000)

</div>
