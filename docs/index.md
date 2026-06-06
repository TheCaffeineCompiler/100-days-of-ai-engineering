# Challenges

Index of the 100-day AI engineering challenges. Each entry lists the day's
objective and links to the per-day write-up.

| Day | Title | Objective | Notes |
|----:|-------|-----------|-------|
| 1   | Router-ready project skeleton | Stand up the repo and make one LLM call through a LiteLLM router you can swap models on without code changes. | [day_001.md](day_001.md) |
| 2   | Structured outputs with Pydantic | Force the model to return a validated `CourseOutline` object instead of free text. | [day_002.md](day_002.md) |
| 3   | Prompt templating & versioning | Move prompts out of f-strings into versioned, testable templates. | [day_003.md](day_003.md) |
| 4   | First FastAPI endpoint | Expose course generation over HTTP via `POST /courses`. | [day_004.md](day_004.md) |
| 5   | Streaming responses | Stream tokens to the client over SSE via `POST /courses/stream`. | [day_005.md](day_005.md) |
| 6   | Retries, timeouts & error handling | Make a single LLM call survive transient failures; surface a typed error to the caller. | [day_006.md](day_006.md) |
| 7   | Config & secrets management | Centralize all configuration into one typed settings object that loads from env/.env and fails fast on missing keys. | [day_007.md](day_007.md) |
