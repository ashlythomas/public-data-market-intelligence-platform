"""ClickHouse analytics schema initialization."""

import logging

logger = logging.getLogger(__name__)

SIGNAL_TIMESERIES_DDL = """
CREATE TABLE IF NOT EXISTS signal_timeseries (
    signal_id UUID,
    signal_type String,
    entity_id Nullable(UUID),
    score Float64,
    confidence Float64,
    generated_at DateTime,
    calculation_version String
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(generated_at)
ORDER BY (signal_type, generated_at);
"""

EVENT_TIMESERIES_DDL = """
CREATE TABLE IF NOT EXISTS event_timeseries (
    event_id UUID,
    event_type String,
    document_id UUID,
    confidence Float64,
    event_time Nullable(DateTime),
    created_at DateTime DEFAULT now()
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY (event_type, created_at);
"""

NARRATIVE_METRICS_DDL = """
CREATE TABLE IF NOT EXISTS narrative_metrics (
    narrative_id UUID,
    velocity_score Float64,
    novelty_score Float64,
    sentiment_score Float64,
    recorded_at DateTime DEFAULT now()
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(recorded_at)
ORDER BY (narrative_id, recorded_at);
"""


async def init_clickhouse(url: str) -> None:
    import httpx

    async with httpx.AsyncClient() as client:
        for ddl in [SIGNAL_TIMESERIES_DDL, EVENT_TIMESERIES_DDL, NARRATIVE_METRICS_DDL]:
            response = await client.post(url, content=ddl)
            if response.status_code not in (200, 204):
                logger.warning(
                    "ClickHouse DDL response: %s %s", response.status_code, response.text
                )
