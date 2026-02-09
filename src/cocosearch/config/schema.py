"""Configuration schema for CocoSearch using Pydantic."""

from pydantic import BaseModel, ConfigDict, Field


class ConfigError(Exception):
    """Exception raised for configuration errors."""

    pass


class IndexingSection(BaseModel):
    """Configuration for code indexing."""

    model_config = ConfigDict(extra="forbid", strict=True)

    includePatterns: list[str] = Field(default_factory=list)
    excludePatterns: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    chunkSize: int = Field(default=1000, gt=0)
    chunkOverlap: int = Field(default=300, ge=0)


class SearchSection(BaseModel):
    """Configuration for search behavior."""

    model_config = ConfigDict(extra="forbid", strict=True)

    resultLimit: int = Field(default=10, gt=0)
    minScore: float = Field(default=0.3, ge=0.0, le=1.0)


class EmbeddingSection(BaseModel):
    """Configuration for embedding model."""

    model_config = ConfigDict(extra="forbid", strict=True)

    model: str = Field(default="nomic-embed-text")


class CocoSearchConfig(BaseModel):
    """Root configuration model for CocoSearch."""

    model_config = ConfigDict(extra="forbid", strict=True)

    indexName: str | None = Field(default=None)
    indexing: IndexingSection = Field(default_factory=IndexingSection)
    search: SearchSection = Field(default_factory=SearchSection)
    embedding: EmbeddingSection = Field(default_factory=EmbeddingSection)
