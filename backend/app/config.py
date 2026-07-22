from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Trippi-AI"
    api_host: str = "0.0.0.0"
    api_port: int = 8080
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # LLM: heuristic | openrouter | anthropic | openai
    # Recommended free path: LLM_PROVIDER=openrouter + OPENROUTER_API_KEY + openrouter/free
    # Recommended cheap quality: LLM_PROVIDER=anthropic + ANTHROPIC_API_KEY + claude-haiku
    llm_provider: str = "heuristic"
    llm_model: str = ""

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-4-5"

    openrouter_api_key: str = ""
    openrouter_model: str = "openrouter/free"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_site_url: str = "https://github.com/ankitpatil3003/Trippi-AI"

    aws_region: str = "us-east-1"
    bedrock_model_id: str = ""

    mcp_server_url: str = "http://127.0.0.1:8000/mcp"
    mcp_stub: bool = True
    mcp_stub_rainy: bool = False
    mcp_retries: int = 3

    database_url: str = ""
    neo4j_uri: str = ""
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""

    date_shift_rain_ratio: float = 0.6
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
