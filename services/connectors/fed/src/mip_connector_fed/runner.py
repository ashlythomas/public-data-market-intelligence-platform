"""Federal Reserve connector runner."""

import asyncio
import os

from mip_connector_fed.connector import FedConnector
from mip_connector_fed.shared_runner import run_connector


async def run_fed_connector(*, tenant_id: str) -> dict:
    if not tenant_id:
        raise ValueError("tenant_id is required for fed ingestion")
    return await run_connector(
        FedConnector(),
        source_id="fed",
        kafka_topic="raw.central-bank.v1",
        tenant_id=tenant_id,
    )


def main() -> None:
    tenant_id = os.environ.get("CONNECTOR_TENANT_ID", "").strip()
    if not tenant_id:
        raise RuntimeError("CONNECTOR_TENANT_ID must be set")
    result = asyncio.run(run_fed_connector(tenant_id=tenant_id))
    print(f"Fed connector completed: {result}")


if __name__ == "__main__":
    main()
