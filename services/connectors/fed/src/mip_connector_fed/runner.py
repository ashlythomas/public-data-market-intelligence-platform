"""Federal Reserve connector runner."""

import asyncio

from mip_connector_fed.connector import FedConnector
from mip_connector_fed.shared_runner import run_connector


async def run_fed_connector() -> dict:
    return await run_connector(
        FedConnector(),
        source_id="fed",
        kafka_topic="raw.central-bank.v1",
    )


def main() -> None:
    result = asyncio.run(run_fed_connector())
    print(f"Fed connector completed: {result}")


if __name__ == "__main__":
    main()
