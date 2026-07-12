"""SEC EDGAR connector runner."""

import asyncio

from mip_database.config import get_settings
from mip_connector_fed.runner import run_connector
from mip_connector_sec_edgar.connector import SecEdgarConnector


async def run_sec_edgar_connector() -> dict:
    settings = get_settings()
    return await run_connector(
        SecEdgarConnector(),
        source_id="sec-edgar",
        kafka_topic="raw.filings.v1",
        tenant_id=settings.default_tenant_id,
    )


def main() -> None:
    result = asyncio.run(run_sec_edgar_connector())
    print(f"SEC EDGAR connector completed: {result}")


if __name__ == "__main__":
    main()
