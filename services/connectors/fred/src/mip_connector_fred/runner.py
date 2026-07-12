"""FRED connector runner."""

import asyncio
import logging

from mip_connector_fed.runner import run_connector
from mip_connector_fred.connector import FredConnector
from mip_database.config import get_settings

logger = logging.getLogger(__name__)


async def run_fred_connector() -> dict:
    settings = get_settings()
    return await run_connector(
        FredConnector(),
        source_id="fred",
        kafka_topic="raw.economic-data.v1",
        tenant_id=settings.default_tenant_id,
    )


def main() -> None:
    result = asyncio.run(run_fred_connector())
    print(f"FRED connector completed: {result}")


if __name__ == "__main__":
    main()
