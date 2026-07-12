"""Scheduled connector ingestion runner."""

import asyncio
import logging
from datetime import UTC, datetime

logger = logging.getLogger(__name__)

CONNECTORS = [
    ("fed", "mip_connector_fed.runner", "run_fed_connector"),
    ("fred", "mip_connector_fred.runner", "run_fred_connector"),
    ("sec-edgar", "mip_connector_sec_edgar.runner", "run_sec_edgar_connector"),
    ("gdelt", "mip_connector_gdelt.runner", "run_gdelt_connector"),
]


async def run_scheduled_ingestion(connector_names: list[str] | None = None) -> dict:
    import importlib

    names = connector_names or [c[0] for c in CONNECTORS]
    results = {}

    for name, module_path, func_name in CONNECTORS:
        if name not in names:
            continue
        try:
            module = importlib.import_module(module_path)
            runner = getattr(module, func_name)
            logger.info("Running connector: %s", name)
            results[name] = await runner()
        except Exception as e:
            logger.exception("Connector %s failed: %s", name, e)
            results[name] = {"error": str(e)}

    return results


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    results = asyncio.run(run_scheduled_ingestion())
    print(f"Scheduled ingestion completed at {datetime.now(UTC).isoformat()}: {results}")


if __name__ == "__main__":
    main()
