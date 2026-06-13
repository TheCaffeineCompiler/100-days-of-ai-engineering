from fastapi import FastAPI, Request
from starlette.responses import JSONResponse

from coursesmith.config.logging_config import configure_logging
from coursesmith.infrastructure.adapters.inbound.rest import create_course_outline_adapter
from coursesmith.infrastructure.adapters.inbound.rest.middleware import LoggingMiddleware
from coursesmith.settings import settings
from coursesmith.use_cases.shared.agents.agent import AgentLoopExhaustedError, AgentResult
from coursesmith.use_cases.shared.ports.llm_port import LlmRateLimitError, LlmTimeoutError

configure_logging(json_logs=settings.log_json_enabled, log_level=settings.log_level)
app = FastAPI()
app.add_middleware(LoggingMiddleware)
app.include_router(router=create_course_outline_adapter.router)


@app.exception_handler(LlmTimeoutError)
async def llm_timeout_handler(_request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=504, content={"detail": str(exc)})


@app.exception_handler(LlmRateLimitError)
async def llm_rate_limit_handler(_request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=429, content={"detail": str(exc)})


@app.exception_handler(AgentLoopExhaustedError)
async def agent_loop_exhausted(_request: Request, exc: Exception) -> JSONResponse:
    payload = exc.args[0] if exc.args else None
    if isinstance(payload, AgentResult):
        return JSONResponse(
            status_code=502,
            content={"detail": "agent loop exhausted", "stop_reason": payload.stop_reason},
        )
    return JSONResponse(status_code=502, content={"detail": str(exc)})
