from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    nim_api_key: str | None = Field(default=None, alias="NIM_API_KEY")
    nim_base_url: str = Field(default="https://integrate.api.nvidia.com/v1", alias="NIM_BASE_URL")

    database_url: str = Field(default="sqlite:///./compliance_ai.db", alias="DATABASE_URL")

    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_db: str = Field(default="compliance_ai", alias="POSTGRES_DB")
    postgres_user: str = Field(default="postgres", alias="POSTGRES_USER")
    postgres_password: str = Field(default="your_secure_password", alias="POSTGRES_PASSWORD")

    neo4j_uri: str = Field(default="bolt://localhost:7687", alias="NEO4J_URI")
    neo4j_user: str = Field(default="neo4j", alias="NEO4J_USER")
    neo4j_password: str = Field(default="your_neo4j_password", alias="NEO4J_PASSWORD")

    qdrant_host: str = Field(default="localhost", alias="QDRANT_HOST")
    qdrant_port: int = Field(default=6333, alias="QDRANT_PORT")

    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    sec_edgar_user_agent: str = Field(default="ComplianceBot contact@example.com", alias="SEC_EDGAR_USER_AGENT")
    finra_api_key: str | None = Field(default=None, alias="FINRA_API_KEY")
    mas_api_key: str | None = Field(default=None, alias="MAS_API_KEY")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    environment: str = Field(default="development", alias="ENVIRONMENT")
    max_workers: int = Field(default=4, alias="MAX_WORKERS")
    scraping_interval_hours: int = Field(default=6, alias="SCRAPING_INTERVAL_HOURS")

    enable_vector_search: bool = Field(default=True, alias="ENABLE_VECTOR_SEARCH")
    enable_graph_search: bool = Field(default=True, alias="ENABLE_GRAPH_SEARCH")

    mapping_provider: str = Field(default="nvidia_nim", alias="MAPPING_PROVIDER")
    mapping_model: str | None = Field(default="meta/llama-3.1-8b-instruct", alias="MAPPING_MODEL")

    @property
    def sqlalchemy_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


def get_settings() -> Settings:
    return Settings()
