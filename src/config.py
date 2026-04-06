from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PARSER_", extra="ignore")

    nats_url: str = "nats://localhost:4222"

    s3_endpoint: str = "http://localhost:3900"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_bucket: str = "openclaw"
    s3_region: str = "us-east-1"

    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "chunks"

    tei_url: str = "http://localhost:8080"
    docling_url: str = "http://localhost:5001"

    ocr_languages: str = "ru,en"
    max_file_size_mb: int = 100

    # NATS stream/consumer
    nats_stream: str = "INDEXING"
    nats_subject: str = "indexing.jobs"
    nats_durable: str = "parser"
    nats_max_retries: int = 3
    nats_retry_delay_s: int = 30
    nats_ack_wait_s: int = 600  # 10 min — large PDFs take time


settings = Settings()
