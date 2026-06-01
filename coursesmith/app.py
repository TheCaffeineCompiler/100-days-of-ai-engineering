from fastapi import FastAPI

from coursesmith.infrastructure.adapters.inbound.rest import create_course_outline_adapter

app = FastAPI()
app.include_router(router=create_course_outline_adapter.router)
