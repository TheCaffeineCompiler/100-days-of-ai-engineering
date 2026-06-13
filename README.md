# CourseSmith

A 100-day AI engineering challenge project. The app generates structured
course outlines from a single topic string by calling an LLM through
[LiteLLM](https://docs.litellm.ai/), validating the response against a
[Pydantic](https://docs.pydantic.dev/) schema, and serving it over HTTP via
[FastAPI](https://fastapi.tiangolo.com/). The underlying provider and model
can be swapped by editing `.env` only — no code changes.

See [`docs/index.md`](docs/index.md) for the day-by-day log of what each
challenge added.

## Requirements

- Python `>= 3.12`
- [`uv`](https://docs.astral.sh/uv/) for dependency and environment management
- An API key for at least one LLM provider supported by LiteLLM (OpenAI,
  Anthropic, Gemini, etc.)

## Setup

1. Clone the repo and `cd` into it.
2. Install dependencies (creates `.venv` automatically):

   ```sh
   uv sync
   ```

3. Install the git pre-commit hooks (one-time):

   ```sh
   uv run pre-commit install
   ```

4. Create your local `.env` from the sample and fill in the values:

   ```sh
   cp .env.sample .env
   ```

   Then edit `.env`:

   ```sh
   LITELLM_MODEL=openai/gpt-4o-mini
   LITELLM_API_KEY=sk-...
   LITELLM_RETRIES=3
   LITELLM_TIMEOUT=60
   COURSE_OUTLINE_PROMPT_VERSION=2
   CREATE_TITLE_PROMPT_VERSION=1
   CREATE_SCHEDULE_PROMPT_VERSION=1
   REVIEW_COURSE_PROMPT_VERSION=1
   LOG_JSON_ENABLED=true
   LOG_LEVEL=INFO
   ```

   `LITELLM_MODEL` uses LiteLLM's `provider/model` format. Examples:

   - `openai/gpt-4o-mini`
   - `anthropic/claude-haiku-4-5`
   - `gemini/gemini-2.0-flash`

   See the [LiteLLM provider list](https://docs.litellm.ai/docs/providers) for
   the full set.

   `LITELLM_RETRIES` and `LITELLM_TIMEOUT` (seconds) control LiteLLM's
   `Router` resilience: retries with backoff on 429/5xx, and a per-call
   timeout that translates to a typed `LlmTimeoutError` (HTTP 504). Rate
   limits exhausted past `LITELLM_RETRIES` surface as `LlmRateLimitError`
   (HTTP 429). See [Day 6](docs/day_006.md).

   `COURSE_OUTLINE_PROMPT_VERSION` selects which prompt template under
   `resources/prompts/course_outline/v<N>.prompt.txt` the service uses. v1
   is the single-call template; v2 is the tool-using planner introduced
   in Day 14. The `CREATE_TITLE_PROMPT_VERSION`,
   `CREATE_SCHEDULE_PROMPT_VERSION`, and `REVIEW_COURSE_PROMPT_VERSION`
   vars do the same job for the three LLM-backed tools the planner
   dispatches to. See [Prompts](#prompts) below.

   `LOG_JSON_ENABLED` (bool) toggles between JSON (production) and a
   colourised console renderer (local dev). `LOG_LEVEL` is one of `DEBUG`,
   `INFO`, `WARNING`, `ERROR`, `CRITICAL`. Every request carries a
   `request_id` (from the inbound `X-Request-ID` header or freshly minted)
   on every log line — including third-party libraries' stdlib logs — so a
   single request can be grepped end to end. See [Day 8](docs/day_008.md).

   All variables are required — `Settings` is a `pydantic-settings`
   `BaseSettings` with no defaults, so a missing var raises a clear
   `ValidationError` at startup rather than failing later in the call.

## Run

Start the API:

```sh
uv run fastapi dev coursesmith/app.py
```

(Or `uv run uvicorn coursesmith.app:app --reload` if you prefer uvicorn
directly.)

- Swagger UI: <http://localhost:8000/docs>
- Generate a course outline (single JSON response):

  ```sh
  curl -X POST http://localhost:8000/courses \
       -H 'Content-Type: application/json' \
       -d '{"topic": "AI engineering for backend developers"}'
  ```

  Dispatches to `CourseOutlineService.create(...)`, which asks the LLM for a
  multi-day outline in structured-output mode and validates the response into
  a `CourseOutline` Pydantic model. The validated object is returned as JSON.

  If the model returns JSON that doesn't match the schema,
  `pydantic.ValidationError` propagates and FastAPI turns it into a 500 — no
  silent fallbacks.

- Query token/cost totals for a request (by `X-Request-ID`):

  ```sh
  curl -X POST http://localhost:8000/courses \
       -H 'Content-Type: application/json' \
       -H 'X-Request-ID: my-run-1' \
       -d '{"topic": "..."}'
  curl http://localhost:8000/courses/usage/my-run-1
  ```

  Returns `{ "prompt": ..., "completion": ..., "cost": ... }` accumulating
  every LLM call made under that `request_id` (multi-call agent runs roll
  up to one number). Unknown ids return HTTP 404. In-memory and
  process-local — resets on restart. See [Day 9](docs/day_009.md).

- Stream the response as SSE (use `curl -N` to disable buffering):

  ```sh
  curl -N -X POST http://localhost:8000/courses/stream \
       -H 'Content-Type: application/json' \
       -d '{"topic": "AI engineering for backend developers"}'
  ```

  Dispatches to `CourseOutlineService.create_stream(...)`, which forwards
  each LLM delta as a `text/event-stream` event: `event: token / data:
  "<token>"` per chunk, followed by `event: done / data: [DONE]` when the
  stream completes. Tokens arrive incrementally rather than after the full
  response. There is no schema enforcement on this path — streaming and
  structured-output guarantees are mutually exclusive.

## Swap providers

To switch to a different provider/model, edit `.env`:

```sh
LITELLM_MODEL=anthropic/claude-haiku-4-5
LITELLM_API_KEY=sk-ant-...
```

Restart the server — no code changes required.

## Prompts

Prompts live as plain text files under `resources/prompts/<name>/v<version>.prompt.txt`,
addressed by `(name, version)` through a small port/adapter pair:

- **`PromptsPort`** (`coursesmith/use_cases/shared/ports/prompts_port.py`) — the
  interface use-case services depend on.
- **`PromptsAdapter`** (`coursesmith/infrastructure/shared/adapters/outbound/prompts_adapter.py`) —
  the file-backed implementation. Resolves `(name, version)` to
  `<base_path>/<name>/v<version>.prompt.txt`.

Each service owns its prompt *name* as a class constant; the *version* comes
from configuration. To roll out a new prompt revision:

1. Add `resources/prompts/<name>/v<N+1>.prompt.txt`.
2. Bump the corresponding env var (e.g. `COURSE_OUTLINE_PROMPT_VERSION=2`).
3. Re-run — no `.py` edits.

The old version stays on disk, so swaps are reversible.

## Architecture

The package follows a hexagonal (ports & adapters) layout under `coursesmith/`:

- **`use_cases/`** — application logic. Each feature is a folder containing
  a service, its Pydantic models, and any feature-private interfaces.
  Cross-feature interfaces live under `use_cases/shared/ports/`.
- **`infrastructure/adapters/inbound/<transport>/`** — handlers that translate
  incoming traffic into use-case calls (today: `rest/`).
- **`infrastructure/shared/adapters/outbound/`** — outbound adapters that
  implement use-case ports (today: file-backed prompts, LiteLLM).
- **`infrastructure/shared/observability/`** — cross-cutting telemetry
  components (today: in-memory usage tracker).
- **`composition.py`** — the composition root. Every `Depends`-target
  factory lives here; routes import from it. The dependency graph reads
  top-to-bottom in one file.
- **`settings.py`** — env-driven configuration via `pydantic-settings`,
  reading from `.env` automatically.
- **`app.py`** — FastAPI ASGI entry point. Mounts inbound routers,
  configures logging, registers exception handlers.

## Tests

```sh
uv run pytest
```

Test files mirror the package layout under `tests/`. Pytest is configured in
`pyproject.toml` (`pythonpath = ["."]`, `testpaths = ["tests"]`), so no build
backend is required to make the project importable from tests.

## Code quality

Four gates run locally (via pre-commit) and in CI:

- **Ruff** (`uv run ruff check`, `uv run ruff format`) — lint + format with a
  strong rule set (`E, W, F, I, N, UP, B, A, C4, SIM, PTH, RUF, S, TID, PT,
  RET, ARG`). Config in `pyproject.toml`.
- **Mypy** (`uv run mypy coursesmith`) — `strict = true`, plus
  `warn_unreachable`, `warn_redundant_casts`, `warn_unused_ignores`, and the
  `pydantic.mypy` plugin so `BaseSettings` constructors type-check correctly.
- **Pytest** (`uv run pytest`) — unit and contract tests under `tests/`.
- **Standard pre-commit hooks** — trailing whitespace, EOF newline, YAML/TOML
  syntax, large-file guard, merge-conflict markers, private-key detection.

Run everything against the whole repo:

```sh
uv run pre-commit run --all-files
uv run pytest
```

The GitHub Action at `.github/workflows/ci.yml` runs all four gates on every
push and pull request. Gates are independent — a failure in one doesn't skip
the rest, so a single CI run surfaces every problem at once. Each run
produces a job summary with a pass/fail table and the full output of each
gate (failing gates auto-expanded).

## Project layout

```
.
├── coursesmith/
│   ├── __init__.py                       # Exports RESOURCES_DIR (repo-relative)
│   ├── app.py                            # FastAPI ASGI entry point; configures logging at import
│   ├── composition.py                    # Composition root: every Depends-target factory in one place
│   ├── settings.py                       # pydantic-settings BaseSettings (.env-aware) + module-level singleton
│   ├── config/
│   │   └── logging_config.py             # structlog ↔ stdlib bridge; JSON or pretty console output
│   ├── use_cases/
│   │   ├── shared/
│   │   │   ├── agents/
│   │   │   │   ├── agent.py              # Agent loop (run + stream) with step/cost/time budgets; AgentResult + AgentLoopExhaustedError (Day 15/16)
│   │   │   │   └── agent_tool.py         # AgentTool[TParams] ABC: schema build + boundary validation (Day 15)
│   │   │   └── ports/
│   │   │       ├── prompts_port.py       # PromptsPort interface
│   │   │       └── llm_port.py           # LlmPort + typed errors (LlmError/Timeout/RateLimit)
│   │   └── create_course_outline/
│   │       ├── course_outline_service.py # Thin wrapper over Agent.run / Agent.stream + JSON validation
│   │       ├── models/
│   │       │   └── course_outline.py     # CourseOutline + DayItem Pydantic models
│   │       └── tools/
│   │           ├── create_title_tool.py         # AgentTool: topic → course title (Day 14/15)
│   │           ├── create_schedule_tool.py      # AgentTool: title → multi-day schedule (Day 14/15)
│   │           └── review_course_tool.py        # AgentTool: title + content → improved CourseOutline (Day 14/15)
│   └── infrastructure/
│       ├── adapters/
│       │   └── inbound/
│       │       └── rest/
│       │           ├── create_course_outline_adapter.py  # POST /courses + POST /courses/stream + GET /courses/usage/{id}
│       │           └── middleware.py     # Raw-ASGI LoggingMiddleware; binds request_id to structlog contextvars
│       └── shared/
│           ├── adapters/
│           │   └── outbound/
│           │       ├── prompts_adapter.py    # File-backed PromptsPort
│           │       └── lite_llm_adapter.py   # LlmPort impl; Router with retries+timeout, typed error translation, per-call cost logging
│           └── observability/
│               └── usage_tracker.py      # Per-request token/cost accumulator keyed by request_id from structlog contextvar
├── resources/
│   └── prompts/
│       ├── course_outline/
│       │   ├── v1.prompt.txt             # Single-call template (no tools)
│       │   └── v2.prompt.txt             # Tool-using planner prompt (Day 14)
│       ├── course_title/
│       │   └── v1.prompt.txt             # Prompt for the create_title tool (Day 14)
│       ├── course_schedule/
│       │   └── v1.prompt.txt             # Prompt for the create_schedule tool (Day 14)
│       └── review_course/
│           └── v1.prompt.txt             # Prompt for the review_course tool (Day 14)
├── tests/                                # Mirrors the package layout
│   ├── integration/
│   │   └── test_create_course_outline_endpoint.py  # End-to-end: real composition graph + stub LlmPort → CourseOutline
│   ├── infrastructure/adapters/inbound/rest/
│   │   ├── test_create_course_outline_adapter.py
│   │   └── test_create_course_outline_stream.py
│   ├── infrastructure/shared/adapters/
│   │   ├── test_prompts_adapter.py
│   │   └── test_lite_llm_adapter.py      # Typed-error translation for complete + stream
│   └── use_cases/
│       ├── create_course_outline/tools/
│       │   ├── test_create_title_tool.py     # Schema shape + execute → LLM plumbing
│       │   ├── test_create_schedule_tool.py  # Schema shape + execute → LLM plumbing
│       │   └── test_review_course_tool.py    # Schema shape + execute with response_format=CourseOutline
│       └── shared/agents/
│           ├── test_agent.py             # run/stream loop: tool dispatch, exhaustion, streaming after tool rounds
│           └── test_agent_tool.py        # ABC template-method behavior: schema build + boundary validation
├── docs/
│   ├── index.md                          # Challenge index
│   ├── day_001.md                        # Day 1 write-up
│   ├── day_002.md                        # Day 2 write-up
│   ├── day_003.md                        # Day 3 write-up
│   ├── day_004.md                        # Day 4 write-up
│   ├── day_005.md                        # Day 5 write-up
│   ├── day_006.md                        # Day 6 write-up
│   ├── day_007.md                        # Day 7 write-up
│   ├── day_008.md                        # Day 8 write-up
│   ├── day_009.md                        # Day 9 write-up
│   ├── day_010.md                        # Day 10 write-up
│   ├── day_011.md                        # Day 11 write-up
│   ├── day_012.md                        # Day 12 write-up
│   ├── day_013.md                        # Day 13 write-up
│   ├── day_014.md                        # Day 14 write-up
│   ├── day_015.md                        # Day 15 write-up
│   └── day_016.md                        # Day 16 write-up
├── .github/workflows/
│   └── ci.yml                            # Lint + format + types + tests on push/PR
├── .pre-commit-config.yaml
├── .env.sample                           # Template for local .env (gitignored)
├── pyproject.toml
└── README.md
```

Each new day's work goes under `coursesmith/use_cases/<feature_name>/` (plus
any new ports/adapters in the corresponding `shared/` or
`inbound/<transport>/` trees) so the package grows by addition rather than
edits to a single file.
