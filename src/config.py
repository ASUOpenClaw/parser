from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PARSER_", extra="ignore")

    nats_url: str = "nats://localhost:4222"

    # S3 — shared vars (no PARSER_ prefix); same credentials as the API service
    s3_endpoint: str = Field("http://localhost:3900", validation_alias=AliasChoices("S3_ENDPOINT_URL", "PARSER_S3_ENDPOINT"))
    s3_access_key: str = Field("", validation_alias=AliasChoices("S3_ACCESS_KEY_ID", "PARSER_S3_ACCESS_KEY"))
    s3_secret_key: str = Field("", validation_alias=AliasChoices("S3_SECRET_ACCESS_KEY", "PARSER_S3_SECRET_KEY"))
    s3_bucket: str = Field("openclaw", validation_alias=AliasChoices("S3_BUCKET", "PARSER_S3_BUCKET"))
    s3_region: str = Field("us-east-1", validation_alias=AliasChoices("S3_REGION", "PARSER_S3_REGION"))

    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "chunks"

    # OpenAI-compatible embeddings endpoint (LiteLLM in front of Ollama)
    embedding_url: str = "http://localhost:4000/v1"
    embedding_model: str = "text-embedding-qwen3"
    embedding_api_key: str = "sk-local-dev"
    docling_url: str = "http://localhost:5001"

    ocr_languages: str = "ru,en"
    max_file_size_mb: int = 100

    # NATS — indexing
    nats_stream: str = "INDEXING"
    nats_subject: str = "indexing.jobs"
    nats_durable: str = "parser"
    nats_max_retries: int = 3
    nats_retry_delay_s: int = 30
    nats_ack_wait_s: int = 600  # 10 min — large PDFs take time

    # NATS — transcription
    transcription_nats_stream: str = "TRANSCRIPTION"
    transcription_nats_subject: str = "transcription.jobs"
    transcription_nats_durable: str = "transcriber"
    transcription_ack_wait_s: int = 600

    # Speaches (Whisper)
    speaches_url: str = "http://localhost:8014"
    speaches_model: str = "Systran/faster-whisper-large-v3"
    speaches_timeout_s: int = 300


settings = Settings()
