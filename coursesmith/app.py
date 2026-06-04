from fastapi import FastAPI, Request
from starlette.responses import JSONResponse

from coursesmith.infrastructure.adapters.inbound.rest import create_course_outline_adapter
from coursesmith.use_cases.shared.ports.llm_port import LlmRateLimitError, LlmTimeoutError

app = FastAPI()
app.include_router(router=create_course_outline_adapter.router)


@app.exception_handler(LlmTimeoutError)
async def llm_timeout_handler(_request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=504, content={"detail": str(exc)})


@app.exception_handler(LlmRateLimitError)
async def llm_rate_limit_handler(_request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=429, content={"detail": str(exc)})
