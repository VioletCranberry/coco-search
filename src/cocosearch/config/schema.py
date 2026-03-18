"""Configuration schema for CocoSearch using Pydantic."""

from pydantic import BaseModel, ConfigDict, Field, model_validator

VALID_EMBEDDING_PROVIDERS = ("ollama", "openai", "openrouter")

_PROVIDER_DEFAULT_MODELS: dict[str, str] = {
    "ollama": "nomic-embed-text",
    "openai": "text-embedding-3-small",
    "openrouter": "openai/text-embedding-3-small",
}


def default_model_for_provider(provider: str) -> str:
    """Return the default embedding model for a given provider."""
    return _PROVIDER_DEFAULT_MODELS.get(provider, "nomic-embed-text")


class ConfigError(Exception):
    """Exception raised for configuration errors."""

    pass


class IndexingSection(BaseModel):
    """Configuration for code indexing."""

    model_config = ConfigDict(extra="forbid", strict=True)

    includePatterns: list[str] = Field(default_factory=list)
    excludePatterns: list[str] = Field(default_factory=list)
    chunkSize: int = Field(default=1000, gt=0)
    chunkOverlap: int = Field(default=300, ge=0)


class SearchSection(BaseModel):
    """Configuration for search behavior."""

    model_config = ConfigDict(extra="forbid", strict=True)

    resultLimit: int = Field(default=10, gt=0)
    minScore: float = Field(default=0.3, ge=0.0, le=1.0)


class EmbeddingSection(BaseModel):
    """Configuration for embedding model and provider."""

    model_config = ConfigDict(extra="forbid", strict=True)

    provider: str = Field(default="ollama")
    model: str | None = Field(default=None)
    outputDimension: int | None = Field(default=None)
    baseUrl: str | None = Field(default=None)

    @model_validator(mode="after")
    def _validate_provider_and_defaults(self) -> "EmbeddingSection":
        if self.provider not in VALID_EMBEDDING_PROVIDERS:
            raise ValueError(
                f"Invalid embedding provider '{self.provider}'. "
                f"Must be one of: {', '.join(VALID_EMBEDDING_PROVIDERS)}"
            )
        if self.model is None:
            self.model = default_model_for_provider(self.provider)
        return self


class LoggingSection(BaseModel):
    """Configuration for logging behavior."""

    model_config = ConfigDict(extra="forbid", strict=True)

    file: bool = Field(default=False)


class CocoSearchConfig(BaseModel):
    """Root configuration model for CocoSearch."""

    model_config = ConfigDict(extra="forbid", strict=True)

    indexName: str | None = Field(default=None)
    linkedIndexes: list[str] = Field(default_factory=list)
    indexing: IndexingSection = Field(default_factory=IndexingSection)
    search: SearchSection = Field(default_factory=SearchSection)
    embedding: EmbeddingSection = Field(default_factory=EmbeddingSection)
    logging: LoggingSection = Field(default_factory=LoggingSection)
