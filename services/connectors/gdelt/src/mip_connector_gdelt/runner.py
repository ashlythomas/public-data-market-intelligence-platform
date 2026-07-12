"""GDELT connector runner."""

import asyncio
import os

from mip_connector_fed.shared_runner import run_connector
from mip_connector_gdelt.connector import GdeltConnector


async def run_gdelt_connector(*, tenant_id: str) -> dict:
    if not tenant_id:
        raise ValueError("tenant_id is required for gdelt ingestion")
    return await run_connector(
        GdeltConnector(),
        source_id="gdelt",
        kafka_topic="raw.news.v1",
        tenant_id=tenant_id,
    )


def main() -> None:
    tenant_id = os.environ.get("CONNECTOR_TENANT_ID", "").strip()
    if not tenant_id:
        raise RuntimeError("CONNECTOR_TENANT_ID must be set")
    result = asyncio.run(run_gdelt_connector(tenant_id=tenant_id))
    print(f"GDELT connector completed: {result}")


if __name__ == "__main__":
    main()
