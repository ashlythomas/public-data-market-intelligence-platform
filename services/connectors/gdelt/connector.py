"""GDELT connector - placeholder for Phase 1 implementation."""

from mip_connector_fed.base import BaseConnector

class GdeltConnector(BaseConnector):
    connector_name = "gdelt"
    connector_version = "0.1.0"
    source_id = "gdelt"

    async def discover(self, checkpoint=None):  # type: ignore[no-untyped-def]
        if False:
            yield  # pragma: no cover

    async def fetch(self, item):  # type: ignore[no-untyped-def]
        raise NotImplementedError("GDELT connector pending implementation")
