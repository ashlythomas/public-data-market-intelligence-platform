import logging
import sys
from typing import Any

import structlog
from prometheus_client import Counter, Gauge, Histogram, generate_latest


def setup_logging(level: str = "INFO") -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> Any:
    return structlog.get_logger(name)


REQUEST_COUNT = Counter(
    "mip_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

REQUEST_LATENCY = Histogram(
    "mip_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"],
)

PROCESSING_LATENCY = Histogram(
    "mip_processing_duration_seconds",
    "Processing pipeline latency",
    ["service", "stage"],
)

DLQ_COUNT = Counter(
    "mip_dlq_messages_total",
    "Dead letter queue messages",
    ["topic"],
)

CONNECTOR_LAG = Gauge(
    "mip_connector_lag_seconds",
    "Connector ingestion lag",
    ["source_id"],
)

DOCUMENT_THROUGHPUT = Counter(
    "mip_documents_processed_total",
    "Documents processed",
    ["service", "status"],
)


def metrics_response() -> bytes:
    return generate_latest()
