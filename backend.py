from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

from assistant_logic import build_assistant_response
from db import init_db
from gigachat import choose_tool


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


app = FastAPI(title="City Assistant MVP", lifespan=lifespan)


class AssistantRequest(BaseModel):
    message: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/assistant")
def assistant(payload: AssistantRequest) -> dict[str, Any]:
    return build_assistant_response(payload.message, choose_tool)
