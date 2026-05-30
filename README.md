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
   ```

   `LITELLM_MODEL` uses LiteLLM's `provider/model` format. Examples:

   - `openai/gpt-4o-mini`
   - `anthropic/claude-haiku-4-5`
   - `gemini/gemini-2.0-flash`

   See the [LiteLLM provider list](https://docs.litellm.ai/docs/providers) for
   the full set.

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

## Code quality

Three gates run locally (via pre-commit) and in CI:

- **Ruff** (`uv run ruff check`, `uv run ruff format`) — lint + format with a
  strong rule set (`E, W, F, I, N, UP, B, A, C4, SIM, PTH, RUF, S, TID, PT,
  RET, ARG`). Config in `pyproject.toml`.
- **Mypy** (`uv run mypy coursesmith`) — `strict = true`, plus
  `warn_unreachable`, `warn_redundant_casts`, `warn_unused_ignores`.
- **Standard pre-commit hooks** — trailing whitespace, EOF newline, YAML/TOML
  syntax, large-file guard, merge-conflict markers, private-key detection.

Run everything against the whole repo:

```sh
uv run pre-commit run --all-files
```

The GitHub Action at `.github/workflows/ci.yml` runs the same three gates on
every push and pull request.

## Project layout

```
.
├── coursesmith/
│   ├── __init__.py
│   ├── hello.py                          # CLI entry: python -m coursesmith.hello "<topic>"
│   └── use_cases/
│       └── create_course_outline/
│           ├── course_outline_service.py # LiteLLM call + Pydantic validation
│           └── models/
│               └── course_outline.py     # CourseOutline + DayItem Pydantic models
├── docs/
│   ├── index.md                          # Challenge index
│   ├── day_001.md                        # Day 1 write-up
│   └── day_002.md                        # Day 2 write-up
├── .github/workflows/
│   └── ci.yml                            # Lint + format + types on push/PR
├── .pre-commit-config.yaml
├── .env.sample                           # Template for local .env (gitignored)
├── pyproject.toml
└── README.md
```

Each new day's work goes under `coursesmith/use_cases/<feature_name>/` so the
package grows by addition rather than edits to a single file.
