# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AntiTrade is a multi-asset financial dashboard with embedded TradingView charts and AI-powered technical analysis. Monorepo with a Vite+React frontend and FastAPI backend.

## Commands

### Frontend (from `frontend/`)

```bash
npm install              # install dependencies
npm run dev              # dev server on :5173, proxies /api to :8000
npm run build            # typecheck (tsc -b) + production build
npm run lint             # ESLint
```

### Backend (from `backend/`)

Always use the project venv — do not use system Python:

```bash
docker compose up -d db                                              # start local Postgres (host port 5433)
./.venv/bin/alembic upgrade head                                     # create/upgrade DB schema
./.venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000   # run server
./.venv/bin/python -m pytest                                          # run all tests (requires Docker — testcontainers spins up an ephemeral Postgres)
./.venv/bin/python -m pytest tests/test_analyze_router.py             # single test file
./.venv/bin/python -m pytest tests/test_analyze_router.py::test_name -v  # single test
./.venv/bin/python -m py_compile main.py                              # quick syntax check
```

### Verification before claiming completion

- Frontend: `cd frontend && npm run build`
- Backend: `cd backend && ./.venv/bin/python -m py_compile <changed_file>.py`

## Architecture

### Frontend (`frontend/src/`)

- **React 19 + TypeScript + Tailwind v4** with shadcn/ui-style open-code primitives in `components/ui/`
- **Single-page app**: only `/` route → `MultiChart.tsx` (draggable multi-chart workspace with AI analysis)
- **Layout**: `AppShell.tsx` wraps `Sidebar.tsx` + page content; draggable grid via react-grid-layout (`DraggableWorkspace.tsx`)
- **Charts**: Embedded TradingView iframes (`ChartPanel.tsx`)
- **AI Analysis**: Job-based — creates job via POST, polls status, displays Markdown result in `AnalysisDrawer.tsx` (sheet drawer)
- **State**: React Context for theme/i18n/toast/sidebar; localStorage for all persisted UI state (no backend persistence)
  - `state/ui-storage.ts` — chart selections, workspace layout, sidebar collapsed
  - `theme/theme-storage.ts` — light/dark/system mode, accent color, recent colors
  - `i18n/i18n-storage.ts` — language mode (system/zh/en)
- **API client** (`api/client.ts`): Axios wrapper that unwraps `{code, data, message}` responses; only analyze endpoints (`createAnalyzeJob`, `getAnalyzeJob`, `fetchLatestAnalysis`)
- **i18n**: i18next + react-i18next; Simplified Chinese + English; translations in `i18n/messages.ts`
- **Notifications**: Toast system (`components/Toast.tsx`) via context
- **Path alias**: `@/*` maps to `src/*`

### Backend (`backend/`)

- **FastAPI** entry at `main.py` with lifespan (init DB)
- **Single router** in `routers/analyze.py` — 3 endpoints under `/api/analyze`:
  - `POST /jobs` — create analysis job (symbol, exchange, interval, lang, force_refresh)
  - `GET /jobs/{job_id}` — poll job status and result
  - `GET /latest` — fetch cached analysis for a symbol
- **Single service** in `services/analyzer.py`:
  - `fetch_ohlcv()` — fetches OHLCV data from TradingView via `tvdatafeed`
  - `calculate_indicators()` — TA-Lib indicators (EMA, SMA, ATR, Bollinger, RSI, MACD)
  - `build_analysis_prompt()` — constructs localized LLM prompt with indicators and k-line data
  - Job queue and analysis cache are **in-memory** (lost on restart)
- **LLM providers** in `providers/`: pluggable via `LLM_PROVIDER` env var — `demo` (deterministic mock), `openai` (default; native tool calling), `anthropic` (native tool calling). All AI features (chart analysis, journal diagnosis, daily-review assist, AI assistant) run on the configured provider; there is no CLI fallback.
- **AI assistant** (`routers/chat.py` + `services/chat.py`): conversation-based, Postgres-persisted (`chat_conversations`, `chat_messages`). Answers Journal/Portfolio/Strategies questions via native tool calling (`services/agent.py` — user-scoped tools, `user_id` injected server-side, never exposed to the LLM). Endpoints under `/api/chat/conversations`.
- **i18n** (`i18n.py`): centralized backend translations for prompts, intervals, errors; language detected from `Accept-Language` header
- **Database**: PostgreSQL via SQLAlchemy 2.0 ORM (sync) + Alembic. Engine/session/`get_db()` dependency in `db.py`; ORM models for all tables in `models.py`; migrations in `alembic/`. Services take a `Session` (`__init__(self, session)`); routers inject it via `Depends(get_db)`. Local dev DB via `docker-compose.yml` (image `pgvector/pgvector:pg16`, host port 5433); tests use `testcontainers` (ephemeral `pgvector/pgvector:pg16`, Docker required). The pgvector extension must be enabled (`CREATE EXTENSION IF NOT EXISTS vector`) — the migration and test conftest both do this automatically.
- **AI assistant tools** (`services/agent.py`): 8 user-scoped tools (`@function_tool`) attached to an **OpenAI Agents SDK** `Agent`; `services/chat.py` drives it via `Runner.run_streamed` and forwards `ResponseTextDeltaEvent` deltas to SSE. `create_model()` returns an `OpenAIChatCompletionsModel` wrapping `AsyncOpenAI(base_url=LLM_BASE_URL)` for `openai`/`anthropic` (both via OpenAI-compatible endpoint), or an offline `_DemoModel` for `demo`. No LangChain/LangGraph in this path. The 8th tool is `search_knowledge(query, scope, top_k)` — semantic RAG search over the user's own strategies (`scope="mine"`) and a shared knowledge corpus (`scope="shared"`) via pgvector cosine similarity (`strategy_embeddings` + `knowledge_chunks` tables). Strategies are re-embedded inline on create/patch (best-effort, never blocks the write).
- **RAG CLIs** (run from `backend/`):
  - `scripts/reindex_strategies.py [--user <id>]` — re-embeds all (or one user's) strategies into `strategy_embeddings`
  - `scripts/ingest_knowledge.py <dir> [--replace]` — ingests `.md`/`.txt` files from a directory into `knowledge_chunks` (shared corpus)

### API Response Contract

All endpoints return `{code: 0, data: {}, message: "ok"}`. Frontend `client.ts` unwraps this — when changing API contracts, update both sides together.

### Environment Variables (backend)

- `LLM_PROVIDER` — `demo` | `openai` | `anthropic` (default: `openai`)
- `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` — provider configuration. `openai` is OpenAI-compatible: point `LLM_BASE_URL` at any compatible endpoint (DeepSeek, GLM/Zhipu, Kimi, OpenRouter, local Ollama/vLLM …). The Agents SDK assistant needs a model that supports tool calling.
- `EMBEDDINGS_PROVIDER` — `demo` | `openai` (default: `openai`; use `demo` for offline/test — deterministic hashing fake, no network)
- `EMBEDDINGS_MODEL` — embeddings model name (default: `text-embedding-3-small`)
- `EMBEDDINGS_BASE_URL`, `EMBEDDINGS_API_KEY` — decouple the embeddings endpoint from chat (e.g. chat on DeepSeek which has no embeddings, embeddings on OpenAI/GLM). When unset, fall back to `LLM_BASE_URL` / `LLM_API_KEY`.
- `DATABASE_URL` — PostgreSQL connection string (default `postgresql+psycopg://antitrade:antitrade@localhost:5433/antitrade`)

## Conventions

- Dark theme base is neutral `#181818` — never cold-blue
- Default accent color: `#b88352` (warm brown); theme tokens in `index.css`
- Frontend theming uses shadcn/Tailwind v4 CSS variables in `frontend/src/index.css`
- Theme mode is applied by toggling the `.dark` class on the root element; do not switch back to `data-theme="dark"` patterns
- Prefer semantic Tailwind color utilities (`bg-popover`, `text-foreground`, `border-border`, `text-muted-foreground`, `bg-primary`, etc.) over hardcoded color values in TSX
- Typography is centrally tokenized in `frontend/src/index.css`
  - Base tokens: `--font-heading`, `--font-subheading`, `--font-body`, `--font-ui`, `--font-caption`, `--font-micro`
  - Tailwind utilities: `text-heading`, `text-subheading`, `text-body`, `text-ui`, `text-caption`, `text-micro`
- Shared/default UI font sizes should use those semantic text utilities instead of ad hoc `text-[12px]` or `text-[13px]`
- Default UI icon sizes are centrally tokenized in `frontend/src/index.css` with `--icon-xs`, `--icon-sm`, `--icon-md`, `--icon-lg`
- For default primitive icon sizing, prefer token-driven sizing such as `size-[var(--icon-sm)]`; keep business one-off icon sizes local unless they become a repeated system pattern
- If a new shared size is needed, add a token in `index.css` first instead of introducing more scattered pixel literals
- The current preferred UI composition style is compact shadcn composition, not wrapper-heavy custom controls. Reach first for `Button`, `Input`, `Select`, `Popover`, `SheetFooter`, `DialogFooter`, `ToggleGroup`, `Table`, and related shared primitives.
- Replace legacy custom control shells instead of stacking more override classes on top of them. If a page has redundant wrappers or CSS duplicating a shared primitive, prefer refactoring to the primitive and deleting the old code.
- Control text hierarchy should remain consistent:
  - action buttons and entered/selected values use `ui`
  - placeholders, helper text, and secondary metadata use `caption`
  - dialog/panel titles use `subheading`
- Compact control scale defaults should stay aligned with the current Journal/Charts direction:
  - standard page and form actions: `sm`
  - toolbar icon-only actions: `icon-sm`
  - dense chart/panel icon actions: `icon-xs`
- **All form controls (Input, SelectTrigger, ToggleGroupItem, Button) must explicitly set `style={{ fontSize: "var(--font-ui)" }}`** or use a page-level `inputStyle`/`btnStyle` object. The shadcn defaults may not match the project's compact 13px sizing. Every new page should define these style objects from its `*-ui-config.ts` and apply them consistently to every form element — do not rely on class-based `text-ui` alone as it may be overridden by component internals.
- For dialogs and drawers with clear primary/secondary actions, prefer footer actions like `Close` + primary action instead of tiny bespoke icon controls in the header.
- Page-specific UI sizing rules should live close to the page layer in small `*-ui-config.ts` files under `frontend/src/pages/` when they are not truly shared across multiple feature domains.
- Avoid introducing or preserving thin architecture layers such as `frontend/src/features/` unless a real multi-file feature boundary exists. One or two page-local config files do not justify an extra layer.
- UI should feel compact and tool-like, not marketing-site-like
- TradingView chart locale must stay in sync with app language
- Analysis drawer shows symbol suffix only (e.g. `XAUUSD` not `COMEX:XAUUSD`)
- Do not expose raw provider/CLI errors to users
- Do not remove i18next, provider configurability, or revert to cold-blue theme
- Prefer small, local changes over wide refactors unless explicitly requested
- Chart reloads should not cause full-page reloads
