from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "production"
    allow_dev_auth: bool = False
    app_name: str = "market-intelligence-api"
    log_level: str = "INFO"
    database_url: str = (
        "postgresql+asyncpg://mip:mip_dev_password@localhost:5432/market_intelligence"
    )
    kafka_bootstrap_servers: str = "localhost:9092"
    redis_url: str = "redis://localhost:6379/0"
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket_raw: str = "mip-raw"
    opensearch_url: str = "http://localhost:9200"
    clickhouse_url: str = "http://localhost:8123"
    mlflow_tracking_uri: str = "http://localhost:5000"
    model_gateway_url: str = "http://localhost:8001"
    oidc_issuer_url: str = ""
    oidc_client_id: str = ""
    default_tenant_id: str = "00000000-0000-0000-0000-000000000001"


@lru_cache
def get_settings() -> Settings:
    return Settings()
