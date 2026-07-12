from typing import Any

import httpx
from pydantic import BaseModel


class EmbedRequest(BaseModel):
    texts: list[str]
    model: str = "default"


class EmbedResponse(BaseModel):
    embeddings: list[list[float]]
    model_version: str


class ModelGatewayClient:
    def __init__(self, base_url: str, timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=timeout)

    async def embed(self, texts: list[str], model: str = "default") -> EmbedResponse:
        response = await self.client.post(
            "/v1/inference/embed",
            json={"texts": texts, "model": model},
        )
        response.raise_for_status()
        return EmbedResponse(**response.json())

    async def extract(
        self,
        text: str,
        schema: dict[str, Any],
        *,
        model: str = "default",
        prompt_version: str = "1.0",
    ) -> dict[str, Any]:
        response = await self.client.post(
            "/v1/inference/extract",
            json={
                "text": text,
                "schema": schema,
                "model": model,
                "prompt_version": prompt_version,
            },
        )
        response.raise_for_status()
        return response.json()

    async def close(self) -> None:
        await self.client.aclose()
