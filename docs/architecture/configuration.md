# Configuration Conventions

All services use environment variables parsed into typed Pydantic settings objects.

## Required Variables

| Variable | Description | Default (local) |
|----------|-------------|-----------------|
| `APP_ENV` | Environment name | `development` |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://mip:mip_dev_password@localhost:5432/market_intelligence` |
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka brokers | `localhost:9092` |
| `REDIS_URL` | Redis connection | `redis://localhost:6379/0` |
| `S3_ENDPOINT_URL` | Object storage endpoint | `http://localhost:9000` |
| `S3_BUCKET_RAW` | Raw document bucket | `mip-raw` |
| `OPENSEARCH_URL` | OpenSearch endpoint | `http://localhost:9200` |
| `MODEL_GATEWAY_URL` | Model gateway service | `http://localhost:8001` |

See `.env.example` for the complete list.
