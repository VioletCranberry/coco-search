"""Tests for cocosearch.deps.registry module."""

from cocosearch.deps.models import DependencyEdge
from cocosearch.deps.registry import (
    _is_dependency_extractor,
    get_extractor,
    get_registered_extractors,
)


# ============================================================================
# Test helpers: valid and invalid extractor-like classes
# ============================================================================


class _ValidExtractor:
    """A valid extractor with LANGUAGES and extract()."""

    LANGUAGES = {"py"}

    def extract(self, file_path: str, content: str) -> list[DependencyEdge]:
        return []


class _MultiLanguageExtractor:
    """An extractor claiming multiple languages."""

    LANGUAGES = {"go", "rust"}

    def extract(self, file_path: str, content: str) -> list[DependencyEdge]:
        return []


class _EmptyLanguagesExtractor:
    """An extractor with empty LANGUAGES set (should be skipped)."""

    LANGUAGES: set[str] = set()

    def extract(self, file_path: str, content: str) -> list[DependencyEdge]:
        return []


class _MissingLanguages:
    """A class without LANGUAGES attribute."""

    def extract(self, file_path: str, content: str) -> list[DependencyEdge]:
        return []


class _MissingExtract:
    """A class without extract method."""

    LANGUAGES = {"java"}


class _ExtractNotCallable:
    """A class where extract is not callable."""

    LANGUAGES = {"java"}
    extract = "not a method"


class _PlainClass:
    """A plain class with neither LANGUAGES nor extract."""

    pass


# ============================================================================
# Tests: _is_dependency_extractor
# ============================================================================


class TestIsDependencyExtractor:
    """Tests for _is_dependency_extractor duck-type check."""

    def test_valid_extractor(self):
        """Class with LANGUAGES and callable extract is recognized."""
        assert _is_dependency_extractor(_ValidExtractor) is True

    def test_multi_language_extractor(self):
        """Class claiming multiple languages is recognized."""
        assert _is_dependency_extractor(_MultiLanguageExtractor) is True

    def test_empty_languages_extractor(self):
        """Class with empty LANGUAGES is still a valid extractor structurally."""
        assert _is_dependency_extractor(_EmptyLanguagesExtractor) is True

    def test_missing_languages(self):
        """Class without LANGUAGES is not an extractor."""
        assert _is_dependency_extractor(_MissingLanguages) is False

    def test_missing_extract(self):
        """Class without extract method is not an extractor."""
        assert _is_dependency_extractor(_MissingExtract) is False

    def test_extract_not_callable(self):
        """Class with non-callable extract attribute is not an extractor."""
        assert _is_dependency_extractor(_ExtractNotCallable) is False

    def test_plain_class(self):
        """Plain class without protocol attributes is not an extractor."""
        assert _is_dependency_extractor(_PlainClass) is False

    def test_none_input(self):
        """None is not an extractor."""
        assert _is_dependency_extractor(None) is False

    def test_string_input(self):
        """String is not an extractor."""
        assert _is_dependency_extractor("not a class") is False


# ============================================================================
# Tests: get_extractor
# ============================================================================


class TestGetExtractor:
    """Tests for get_extractor()."""

    def test_returns_none_for_unknown_language(self):
        """Unknown language_id returns None."""
        assert get_extractor("unknown_language_xyz") is None

    def test_returns_none_for_empty_string(self):
        """Empty string returns None."""
        assert get_extractor("") is None


# ============================================================================
# Tests: get_registered_extractors
# ============================================================================


class TestGetRegisteredExtractors:
    """Tests for get_registered_extractors()."""

    def test_returns_list(self):
        """Should return a list."""
        result = get_registered_extractors()
        assert isinstance(result, list)

    def test_returns_unique_instances(self):
        """All instances in the list should be unique objects."""
        result = get_registered_extractors()
        ids = [id(ext) for ext in result]
        assert len(ids) == len(set(ids))

    def test_all_have_languages_and_extract(self):
        """All registered extractors have LANGUAGES and extract."""
        for ext in get_registered_extractors():
            assert hasattr(ext, "LANGUAGES")
            assert callable(getattr(ext, "extract"))
            assert len(ext.LANGUAGES) > 0


# ============================================================================
# Tests: Python extractor registration
# ============================================================================


class TestPythonExtractorRegistered:
    """Tests for Python extractor being auto-registered."""

    def test_python_extractor_registered(self):
        """Python extractor should be discoverable by language_id."""
        ext = get_extractor("py")
        assert ext is not None

    def test_python_in_registered_list(self):
        """Python extractor should appear in registered list."""
        extractors = get_registered_extractors()
        languages = set()
        for ext in extractors:
            languages.update(ext.LANGUAGES)
        assert "py" in languages
