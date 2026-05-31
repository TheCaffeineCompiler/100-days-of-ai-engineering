# CourseSmith

A 100-day AI engineering challenge project. The app generates structured
course outlines from a single topic string by calling an LLM through
[LiteLLM](https://docs.litellm.ai/) and validating the response against a
[Pydantic](https://docs.pydantic.dev/) schema. The underlying provider and
model can be swapped by editing `.env` only — no code changes.

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
   COURSE_OUTLINE_PROMPT_VERSION=1
   ```

   `LITELLM_MODEL` uses LiteLLM's `provider/model` format. Examples:

   - `openai/gpt-4o-mini`
   - `anthropic/claude-haiku-4-5`
   - `gemini/gemini-2.0-flash`

   See the [LiteLLM provider list](https://docs.litellm.ai/docs/providers) for
   the full set.

   `COURSE_OUTLINE_PROMPT_VERSION` selects which prompt template under
   `resources/prompts/course_outline/v<N>.prompt.txt` the service uses. See
   [Prompts](#prompts) below.

   All three variables are required — `Settings` is a `pydantic-settings`
   `BaseSettings` with no defaults, so a missing var raises a clear
   `ValidationError` at startup rather than failing later in the call.

## Run

Generate a course outline for a topic:

```sh
uv run python -m coursesmith.hello "AI engineering for backend developers"
```

The CLI calls `CourseOutlineService.create(...)`, which asks the LLM for a
multi-day outline in structured-output mode and validates the response into a
`CourseOutline` Pydantic model. The validated object is printed to stdout.

If the model returns JSON that doesn't match the schema, `pydantic.ValidationError`
propagates up with field-level details — no silent fallbacks.

## Swap providers

To switch to a different provider/model, edit `.env`:

```sh
LITELLM_MODEL=anthropic/claude-haiku-4-5
LITELLM_API_KEY=sk-ant-...
```

Re-run the same command — no code changes required.

## Prompts

Prompts live as plain text files under `resources/prompts/<name>/v<version>.prompt.txt`,
addressed by `(name, version)` through a small port/adapter pair:

- **`PromptsPort`** (`coursesmith/use_cases/shared/ports/prompts_port.py`) — the
  interface use-case services depend on.
- **`PromptsAdapter`** (`coursesmith/infrastructure/shared/adapters/prompts_adapter.py`) —
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
- **`infrastructure/`** — concrete implementations of the ports
  (file system, HTTP, LLM providers, …). Cross-feature adapters live under
  `infrastructure/shared/adapters/`.
- **`settings.py`** — env-driven configuration via `pydantic-settings`.
- **`hello.py`** — CLI entry point. Wires settings, adapters, and the service
  together; everything else only depends on ports.

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
│   ├── hello.py                          # CLI entry: python -m coursesmith.hello "<topic>"
│   ├── settings.py                       # pydantic-settings BaseSettings
│   ├── use_cases/
│   │   ├── shared/
│   │   │   └── ports/
│   │   │       └── prompts_port.py       # PromptsPort interface
│   │   └── create_course_outline/
│   │       ├── course_outline_service.py # LiteLLM call + Pydantic validation
│   │       └── models/
│   │           └── course_outline.py     # CourseOutline + DayItem Pydantic models
│   └── infrastructure/
│       └── shared/
│           └── adapters/
│               └── prompts_adapter.py    # File-backed PromptsPort
├── resources/
│   └── prompts/
│       └── course_outline/
│           └── v1.prompt.txt             # Versioned prompt templates
├── tests/                                # Mirrors the package layout
│   └── infrastructure/shared/adapters/
│       └── test_prompts_adapter.py
├── docs/
│   ├── index.md                          # Challenge index
│   ├── day_001.md                        # Day 1 write-up
│   ├── day_002.md                        # Day 2 write-up
│   └── day_003.md                        # Day 3 write-up
├── .github/workflows/
│   └── ci.yml                            # Lint + format + types on push/PR
├── .pre-commit-config.yaml
├── .env.sample                           # Template for local .env (gitignored)
├── pyproject.toml
└── README.md
```

Each new day's work goes under `coursesmith/use_cases/<feature_name>/` (plus
any new ports/adapters in the corresponding `shared/` trees) so the package
grows by addition rather than edits to a single file.
