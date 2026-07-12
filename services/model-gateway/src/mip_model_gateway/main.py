"""Model gateway - centralized LLM and embedding access."""

import hashlib
from typing import Any

import numpy as np
from fastapi import FastAPI
from mip_observability import setup_logging
from pydantic import BaseModel, Field

EMBEDDING_DIM = 384
MODEL_VERSION = "mock-embed-v0.1.0"


class ChatRequest(BaseModel):
    messages: list[dict[str, str]]
    model: str = "default"
    temperature: float = 0.0


class ExtractRequest(BaseModel):
    text: str
    schema_: dict[str, Any] = Field(alias="schema")
    model: str = "default"
    prompt_version: str = "1.0"


class EmbedRequest(BaseModel):
    texts: list[str]
    model: str = "default"


class ClassifyRequest(BaseModel):
    text: str
    labels: list[str]
    model: str = "default"


def _mock_embed(text: str) -> list[float]:
    """Deterministic mock embedding for local development."""
    seed = int(hashlib.sha256(text.encode()).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed)
    vec = rng.standard_normal(EMBEDDING_DIM)
    vec = vec / np.linalg.norm(vec)
    return vec.tolist()


def create_app() -> FastAPI:
    setup_logging()
    app = FastAPI(title="Model Gateway", version="0.1.0")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "healthy"}

    @app.post("/v1/inference/chat")
    async def chat(request: ChatRequest) -> dict[str, Any]:
        last_message = request.messages[-1]["content"] if request.messages else ""
        return {
            "content": f"[mock response to: {last_message[:100]}]",
            "model": request.model,
            "model_version": MODEL_VERSION,
            "tokens_used": len(last_message.split()),
        }

    @app.post("/v1/inference/extract")
    async def extract(request: ExtractRequest) -> dict[str, Any]:
        return {
            "extracted": {
                "events": [
                    {
                        "event_type": "policy_announcement",
                        "action": "announced",
                        "confidence": 0.85,
                    }
                ]
            },
            "model": request.model,
            "model_version": MODEL_VERSION,
            "prompt_version": request.prompt_version,
        }

    @app.post("/v1/inference/embed")
    async def embed(request: EmbedRequest) -> dict[str, Any]:
        embeddings = [_mock_embed(text) for text in request.texts]
        return {
            "embeddings": embeddings,
            "model_version": MODEL_VERSION,
        }

    @app.post("/v1/inference/classify")
    async def classify(request: ClassifyRequest) -> dict[str, Any]:
        scores = {label: 0.1 for label in request.labels}
        if request.labels:
            scores[request.labels[0]] = 0.7
        return {
            "labels": scores,
            "model_version": MODEL_VERSION,
        }

    return app


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run("mip_model_gateway.main:app", host="0.0.0.0", port=8001)
