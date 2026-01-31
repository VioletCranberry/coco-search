"""Unit tests for config schema validation."""

import pytest
from pydantic import ValidationError

from cocosearch.config import (
    CocoSearchConfig,
    EmbeddingSection,
    IndexingSection,
    SearchSection,
)


class TestIndexingSection:
    """Test IndexingSection model."""

    def test_default_values(self):
        """Test that default values are set correctly."""
        section = IndexingSection()
        assert section.includePatterns == []
        assert section.excludePatterns == []
        assert section.languages == []
        assert section.chunkSize == 1000
        assert section.chunkOverlap == 300

    def test_valid_config(self):
        """Test valid configuration with all fields specified."""
        section = IndexingSection(
            includePatterns=["*.py", "*.js"],
            excludePatterns=["*.test.js"],
            languages=["python", "javascript"],
            chunkSize=2000,
            chunkOverlap=500,
        )
        assert section.includePatterns == ["*.py", "*.js"]
        assert section.excludePatterns == ["*.test.js"]
        assert section.languages == ["python", "javascript"]
        assert section.chunkSize == 2000
        assert section.chunkOverlap == 500

    def test_unknown_field_rejected(self):
        """Test that unknown fields are rejected (extra='forbid')."""
        with pytest.raises(ValidationError) as exc_info:
            IndexingSection(unknownField="value")
        assert "Extra inputs are not permitted" in str(exc_info.value)

    def test_type_validation_strict(self):
        """Test strict type validation (string '10' rejected for int)."""
        with pytest.raises(ValidationError) as exc_info:
            IndexingSection(chunkSize="10")
        # In strict mode, string is not coerced to int
        assert "Input should be a valid integer" in str(exc_info.value)

    def test_chunk_size_must_be_positive(self):
        """Test that chunkSize must be greater than 0."""
        with pytest.raises(ValidationError) as exc_info:
            IndexingSection(chunkSize=0)
        assert "Input should be greater than 0" in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            IndexingSection(chunkSize=-100)
        assert "Input should be greater than 0" in str(exc_info.value)

    def test_chunk_overlap_must_be_non_negative(self):
        """Test that chunkOverlap must be >= 0."""
        # Zero is valid
        section = IndexingSection(chunkOverlap=0)
        assert section.chunkOverlap == 0

        # Negative is not
        with pytest.raises(ValidationError) as exc_info:
            IndexingSection(chunkOverlap=-1)
        assert "Input should be greater than or equal to 0" in str(exc_info.value)


class TestSearchSection:
    """Test SearchSection model."""

    def test_default_values(self):
        """Test that default values are set correctly."""
        section = SearchSection()
        assert section.resultLimit == 10
        assert section.minScore == 0.3

    def test_valid_config(self):
        """Test valid configuration with all fields specified."""
        section = SearchSection(resultLimit=50, minScore=0.7)
        assert section.resultLimit == 50
        assert section.minScore == 0.7

    def test_unknown_field_rejected(self):
        """Test that unknown fields are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            SearchSection(unknownField="value")
        assert "Extra inputs are not permitted" in str(exc_info.value)

    def test_result_limit_must_be_positive(self):
        """Test that resultLimit must be greater than 0."""
        with pytest.raises(ValidationError) as exc_info:
            SearchSection(resultLimit=0)
        assert "Input should be greater than 0" in str(exc_info.value)

    def test_min_score_range(self):
        """Test that minScore must be between 0.0 and 1.0."""
        # Valid values
        section = SearchSection(minScore=0.0)
        assert section.minScore == 0.0

        section = SearchSection(minScore=1.0)
        assert section.minScore == 1.0

        # Below range
        with pytest.raises(ValidationError) as exc_info:
            SearchSection(minScore=-0.1)
        assert "Input should be greater than or equal to 0" in str(exc_info.value)

        # Above range
        with pytest.raises(ValidationError) as exc_info:
            SearchSection(minScore=1.1)
        assert "Input should be less than or equal to 1" in str(exc_info.value)


class TestEmbeddingSection:
    """Test EmbeddingSection model."""

    def test_default_values(self):
        """Test that default values are set correctly."""
        section = EmbeddingSection()
        assert section.model == "nomic-embed-text"

    def test_valid_config(self):
        """Test valid configuration with custom model."""
        section = EmbeddingSection(model="custom-model")
        assert section.model == "custom-model"

    def test_unknown_field_rejected(self):
        """Test that unknown fields are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            EmbeddingSection(unknownField="value")
        assert "Extra inputs are not permitted" in str(exc_info.value)


class TestCocoSearchConfig:
    """Test root CocoSearchConfig model."""

    def test_default_values(self):
        """Test that default values are set correctly."""
        config = CocoSearchConfig()
        assert config.indexName is None
        assert isinstance(config.indexing, IndexingSection)
        assert isinstance(config.search, SearchSection)
        assert isinstance(config.embedding, EmbeddingSection)

    def test_valid_config_all_fields(self):
        """Test valid configuration with all fields specified."""
        config = CocoSearchConfig(
            indexName="my-index",
            indexing={"chunkSize": 2000, "chunkOverlap": 400},
            search={"resultLimit": 20, "minScore": 0.5},
            embedding={"model": "my-model"},
        )
        assert config.indexName == "my-index"
        assert config.indexing.chunkSize == 2000
        assert config.indexing.chunkOverlap == 400
        assert config.search.resultLimit == 20
        assert config.search.minScore == 0.5
        assert config.embedding.model == "my-model"

    def test_partial_config(self):
        """Test partial configuration (only some sections)."""
        config = CocoSearchConfig(
            indexName="test-index",
            search={"resultLimit": 25},
        )
        assert config.indexName == "test-index"
        assert config.search.resultLimit == 25
        # Other fields use defaults
        assert config.indexing.chunkSize == 1000
        assert config.embedding.model == "nomic-embed-text"

    def test_unknown_field_rejected_root(self):
        """Test that unknown fields are rejected at root level."""
        with pytest.raises(ValidationError) as exc_info:
            CocoSearchConfig(unknownField="value")
        assert "Extra inputs are not permitted" in str(exc_info.value)

    def test_unknown_field_rejected_nested(self):
        """Test that unknown fields are rejected in nested sections."""
        with pytest.raises(ValidationError) as exc_info:
            CocoSearchConfig(indexing={"unknownField": "value"})
        # The error comes from IndexingSection validation
        assert "Extra inputs are not permitted" in str(exc_info.value)

    def test_model_dump_serialization(self):
        """Test that model_dump produces correct dictionary."""
        config = CocoSearchConfig()
        data = config.model_dump()
        assert isinstance(data, dict)
        assert "indexName" in data
        assert "indexing" in data
        assert "search" in data
        assert "embedding" in data
        assert isinstance(data["indexing"], dict)
