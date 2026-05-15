# BrowseComp Agent Eval Harness

A local-first evaluation system for running and scoring web-browsing agents on the [BrowseComp](https://openai.com/index/browsecomp/) benchmark. Built around Temporal for durable orchestration, Postgres for persistence, and a clean agent-agnostic interface so new agents can be dropped in without touching the harness.

## What it does

Run a browsing agent against a set of hard web-research questions, capture the full research trace, grade each answer, and produce a summary report:

```
BrowseComp Eval Run Complete

Tasks evaluated: 10
Correct: 2
Incorrect: 8
Accuracy: 20.0%

Average:
  Runtime:      184s
  Search calls: 14.2
  Pages opened: 22.7
  Tool errors:  0.3

Artifacts saved in database under run ID: <uuid>
```

Every task run stores the question, final answer, expected answer, correctness, per-step trace, and usage stats — all queryable via a REST API or the `show_eval_run.py` script.

## Architecture

```
CLI / API
    │
    ▼
BrowseCompEvalWorkflow (Temporal)
    │  fan-out with bounded concurrency
    ├── BrowseCompTaskWorkflow
    │       ├── LoadTaskActivity
    │       ├── CreateTaskRunActivity
    │       ├── RunBrowseAgentActivity  ◄── BrowseResearchAgentV1
    │       │                                  │  explore → verify → answer loop
    │       │                                  ├── search_web (Brave Search)
    │       │                                  ├── open_webpage (httpx + BS4)
    │       │                                  └── extract_relevant_passages
    │       ├── GradeAnswerActivity
    │       ├── PersistTraceActivity
    │       └── PersistResultActivity
    └── ... (one per task, up to max_concurrency)
         │
         ▼
    FinalizeEvalRunActivity → metrics aggregated in Postgres
```

**Stack:** Python 3.11, FastAPI, SQLAlchemy (async), Alembic, Temporal, Postgres, httpx, BeautifulSoup, Anthropic SDK, uv.

## Repository layout

```
.
├── apps/api/
│   ├── main.py               # FastAPI app
│   ├── api/v1/               # REST endpoints
│   ├── db/                   # SQLAlchemy models, session, Alembic migrations
│   ├── workers/              # Temporal worker process
│   └── settings.py           # Pydantic settings (env vars)
│
├── packages/
│   ├── eval_core/            # Domain models, grading, metrics, trace schema
│   ├── browsecomp/           # Dataset loader, normalization, schemas
│   ├── agents/               # AgentAdapter protocol + BrowseResearchAgentV1
│   ├── web_tools/            # search_web, open_webpage, extract_relevant_passages
│   └── temporal_workflows/   # Workflows and activities
│
├── datasets/browsecomp/      # Dataset files (not committed — see below)
├── infra/                    # Docker Compose, Dockerfile, Temporal config
├── scripts/                  # load_browsecomp, run_eval, show_eval_run, seed_dev_db
└── tests/                    # Unit + integration tests, fixtures
```

## Prerequisites

- Docker + Docker Compose
- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (`pip install uv`)
- An [Anthropic API key](https://console.anthropic.com/)
- A [Brave Search API key](https://brave.com/search/api/) (free tier available; falls back to mock results if absent)

## Quick start

### 1. Install dependencies

```bash
uv pip install -e ".[dev]"
```

### 2. Configure environment

```bash
cp .env.example .env   # or create .env manually
```

`.env` variables:

```ini
ANTHROPIC_API_KEY=sk-ant-...
BRAVE_SEARCH_API_KEY=BSA...       # optional — omit for mock search results
DATABASE_URL=postgresql+asyncpg://eval:eval@localhost:5432/eval_db
TEMPORAL_HOST=localhost:7233
```

### 3. Start infrastructure

```bash
make up-infra   # starts Postgres, Temporal server, and Temporal UI
```

Temporal UI is available at http://localhost:8080.

### 4. Run database migrations

```bash
make migrate
```

### 5. Load the BrowseComp dataset

**Option A — real dataset** (recommended):

Download `browsecomp.jsonl` from the [openai/simple-evals](https://github.com/openai/simple-evals) repository and place it at `datasets/browsecomp/browsecomp.jsonl`.

```bash
make load-browsecomp
# Loaded 1266 BrowseComp tasks
# Inserted: 1266 / Skipped: 0
```

**Option B — synthetic mini dataset** (no download needed, for local development):

```bash
python scripts/seed_dev_db.py   # writes 5 synthetic tasks
make load-browsecomp
```

### 6. Start the Temporal worker

```bash
make worker
```

Keep this running in a separate terminal for the duration of any eval run.

### 7. Run an evaluation

```bash
make eval-browsecomp TASK_COUNT=10
```

Or with the script directly for more options:

```bash
python scripts/run_eval.py \
  --benchmark browsecomp \
  --task-count 5 \
  --sampling random \
  --model-name claude-sonnet-4-6

# Run specific tasks:
python scripts/run_eval.py \
  --benchmark browsecomp \
  --task-ids browsecomp_0001 browsecomp_0002 browsecomp_0003
```

### 8. Inspect results

```bash
python scripts/show_eval_run.py --eval-run-id <uuid>
```

Or via the API (start with `make api`):

```bash
# List task runs for a run
curl http://localhost:8000/v1/eval-runs/<run-id>/task-runs | jq

# Get full trace for one task
curl http://localhost:8000/v1/task-runs/<task-run-id>/trace | jq
```

## Make targets

| Target | Description |
|--------|-------------|
| `make up` | Start all Docker services (infra + api + worker) |
| `make up-infra` | Start Postgres + Temporal only |
| `make down` | Stop all Docker services |
| `make migrate` | Run Alembic migrations |
| `make load-browsecomp` | Seed eval_tasks table |
| `make eval-browsecomp TASK_COUNT=N` | Run N tasks through the eval pipeline |
| `make worker` | Start the Temporal worker process |
| `make api` | Start the FastAPI dev server |
| `make test` | Run the test suite |
| `make lint` | Run ruff linter |
| `make fmt` | Run ruff formatter |
| `make show-run RUN_ID=<uuid>` | Print run summary |

## REST API

All endpoints are under `/v1`.

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/eval-runs` | Start a new eval run |
| `GET` | `/eval-runs/{id}` | Run status and metrics |
| `GET` | `/eval-runs/{id}/task-runs` | List all task runs for a batch |
| `GET` | `/task-runs/{id}` | Full task run detail (answer, stats, errors) |
| `GET` | `/task-runs/{id}/trace` | Ordered trace events for a task |

**Start a run:**

```bash
curl -X POST http://localhost:8000/v1/eval-runs \
  -H "Content-Type: application/json" \
  -d '{
    "benchmark": "browsecomp",
    "task_count": 10,
    "agent_name": "browse-research-agent",
    "model_name": "claude-sonnet-4-6",
    "config": {"max_searches": 30, "max_pages": 60, "max_runtime_seconds": 600}
  }'
```

## The browsing agent

`BrowseResearchAgentV1` runs a stateful explore → verify → answer loop:

1. Parse question into search clues
2. Plan and execute searches (Brave Search API)
3. Open promising pages and extract relevant passages
4. Build and rank candidate answers
5. Switch to verification mode once a strong candidate emerges
6. Finalize when ≥2 independent sources agree, or answer best candidate on budget exhaustion

**Finalization rule:** a candidate is finalized when `support_count ≥ 2` and `confidence ≥ 0.7` with no contradicting evidence.

**Budget limits** (configurable per run):

| Limit | Default |
|-------|---------|
| Max search calls | 30 |
| Max pages opened | 60 |
| Max agent steps | 50 |
| Max runtime | 600s |

All limits are enforced in code, not by prompt.

## Adding a new agent

Implement the `AgentAdapter` protocol:

```python
from agents.base import AgentAdapter, RunContext
from eval_core.models import AgentResult, EvalTask

class MyAgent:
    name = "my-agent"
    version = "v1"

    async def run_task(self, task: EvalTask, ctx: RunContext) -> AgentResult:
        # use ctx.record(...) to emit trace events
        # check ctx.budget for limits
        ...
        return AgentResult(final_answer="...", stats=...)
```

Pass `agent_name` when starting a run via the API or CLI to route to your agent. (Phase 2 will wire this routing automatically.)

## Grading

Phase 1 uses deterministic grading:

1. **Normalize** both predicted and expected answers: lowercase, strip punctuation and accents, collapse whitespace, remove articles, expand aliases (US/UK/etc.)
2. **Exact match** on normalized strings
3. **Containment fallback** for slight truncation (`"The answer is Paris"` → correct for `"Paris"`)

No LLM judge in Phase 1.

## Database schema

Four tables: `eval_tasks → eval_runs → task_runs → trace_events`. Run `make migrate` to apply the Alembic migration that creates them.

Key indexes: `task_runs(eval_run_id)`, `trace_events(task_run_id, step_index)`, `eval_runs(created_at DESC)`.

## Running tests

```bash
make test
```

The suite covers:

- **Unit:** grading (8 cases), normalization, research state policies, trace event construction, dataset loader (JSONL parsing, ID assignment, sampling), web tool extract/find_in_page
- **Integration:** full task pipeline with mock agents (always-correct, always-wrong, budget-exhausted)
- **Fixtures:** `tests/fixtures/browsecomp_mini.json` — 5 curated tasks covering easy, medium, alias edge case, impossible-under-budget, and easy scenarios

Integration tests do not require a running database or Temporal server.

## Configuration reference

All settings are in `apps/api/settings.py` and read from environment variables (or `.env`):

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://eval:eval@localhost:5432/eval_db` | Async Postgres URL |
| `TEMPORAL_HOST` | `localhost:7233` | Temporal frontend address |
| `TEMPORAL_NAMESPACE` | `default` | Temporal namespace |
| `TEMPORAL_TASK_QUEUE` | `browsecomp-eval` | Worker task queue |
| `ANTHROPIC_API_KEY` | — | Required for the real agent |
| `BRAVE_SEARCH_API_KEY` | — | Optional; mock results used if absent |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
