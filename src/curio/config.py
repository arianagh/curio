from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "qwen3:8b"
    ollama_embed_model: str = "nomic-embed-text"
    celery_broker_url: str = "redis://localhost:6380/0"
    celery_result_backend: str = "redis://localhost:6380/0"
    celery_task_always_eager: bool = False

    db_name: str = "curio"
    db_user: str = "curio"
    db_password: str = "curio"
    db_host: str = "localhost"
    db_port: int = 5433


settings = Settings()
