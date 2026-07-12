"""SEC EDGAR connector runner."""

import asyncio
import os

from mip_connector_fed.shared_runner import run_connector
from mip_connector_sec_edgar.connector import SecEdgarConnector


async def run_sec_edgar_connector(*, tenant_id: str) -> dict:
    if not tenant_id:
        raise ValueError("tenant_id is required for sec-edgar ingestion")
    return await run_connector(
        SecEdgarConnector(),
        source_id="sec-edgar",
        kafka_topic="raw.filings.v1",
        tenant_id=tenant_id,
    )


def main() -> None:
    tenant_id = os.environ.get("CONNECTOR_TENANT_ID", "").strip()
    if not tenant_id:
        raise RuntimeError("CONNECTOR_TENANT_ID must be set")
    result = asyncio.run(run_sec_edgar_connector(tenant_id=tenant_id))
    print(f"SEC EDGAR connector completed: {result}")


if __name__ == "__main__":
    main()
