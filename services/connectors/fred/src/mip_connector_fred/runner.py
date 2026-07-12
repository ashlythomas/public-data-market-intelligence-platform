"""FRED connector runner."""

import asyncio
import logging
import os

from mip_connector_fed.shared_runner import run_connector
from mip_connector_fred.connector import FredConnector

logger = logging.getLogger(__name__)


async def run_fred_connector(*, tenant_id: str) -> dict:
    if not tenant_id:
        raise ValueError("tenant_id is required for fred ingestion")
    return await run_connector(
        FredConnector(),
        source_id="fred",
        kafka_topic="raw.economic-data.v1",
        tenant_id=tenant_id,
    )


def main() -> None:
    tenant_id = os.environ.get("CONNECTOR_TENANT_ID", "").strip()
    if not tenant_id:
        raise RuntimeError("CONNECTOR_TENANT_ID must be set")
    result = asyncio.run(run_fred_connector(tenant_id=tenant_id))
    print(f"FRED connector completed: {result}")


if __name__ == "__main__":
    main()
