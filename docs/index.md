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
| 8   | Structured logging | Replace prints with structured, correlatable JSON logs; every request carries a `request_id` you can grep end to end. | [day_008.md](day_008.md) |
| 9   | Token counting & cost tracking | Log prompt/completion tokens and estimated cost on every LLM call; expose a per-request running total via HTTP. | [day_009.md](day_009.md) |
| 10  | Foundations capstone | Tie Days 1–9 into one clean service: composition root, layered package, end-to-end integration test. No new features. | [day_010.md](day_010.md) |
| 11  | Define a tool schema | Describe a `get_current_time` tool to the model in JSON-schema form, derived from a single Pydantic args model. | [day_011.md](day_011.md) |
| 12  | Single tool call round-trip | Get the model to request a tool call. Pass the schema in, log the `tool_use` block, don't execute yet — that's Day 13. | [day_012.md](day_012.md) |
| 13  | Execute the tool & feed the result back | Close the loop: tiny tool registry + an agent loop that runs the requested tool, replies to the model, and returns a populated `CourseOutline`. | [day_013.md](day_013.md) |
| 14  | Multiple tools / tool selection | Register 3+ tools; let the model pick `create_title → create_schedule → review_course` for a single topic. Boundary-validated request models per tool. | [day_014.md](day_014.md) |
| 15  | The agent loop (think → act → observe) | Extract the loop into a reusable `Agent` + `AgentTool[TParams]` ABC under `use_cases/shared/agents/`; surface a typed `AgentLoopExhaustedError`; redesign streaming for the multi-call shape. | [day_015.md](day_015.md) |
| 16  | Stop conditions & max iterations | Three budgets — step count, cost, wall clock — checked at the top of every loop iteration via a shared helper. `AgentResult` carries `stop_reason`; the REST handler exposes it in the response body. | [day_016.md](day_016.md) |
| 17  | Parallel tool calls | Fan multiple `tool_calls` from one assistant turn through `asyncio.gather`. Per-call error envelopes (tied to `tool_call_id`) replace `return_exceptions=True` so one failure can't cancel siblings or leave the next turn missing a response. | [day_017.md](day_017.md) |
