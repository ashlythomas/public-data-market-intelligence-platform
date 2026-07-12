"""GDELT connector runner."""

import asyncio

from mip_connector_fed.shared_runner import run_connector
from mip_connector_gdelt.connector import GdeltConnector


async def run_gdelt_connector() -> dict:
    return await run_connector(
        GdeltConnector(),
        source_id="gdelt",
        kafka_topic="raw.news.v1",
    )


def main() -> None:
    result = asyncio.run(run_gdelt_connector())
    print(f"GDELT connector completed: {result}")


if __name__ == "__main__":
    main()
