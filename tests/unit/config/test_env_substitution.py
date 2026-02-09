"""Unit tests for environment variable substitution in config."""

from cocosearch.config.env_substitution import substitute_env_vars


class TestSubstituteEnvVars:
    """Tests for substitute_env_vars function."""

    class TestBasicSubstitution:
        """Test basic ${VAR} substitution."""

        def test_substitutes_env_var_when_set(self, monkeypatch):
            """${VAR} with VAR set returns VAR value, empty missing list."""
            monkeypatch.setenv("MY_VAR", "my_value")

            result, missing = substitute_env_vars("${MY_VAR}")

            assert result == "my_value"
            assert missing == []

        def test_returns_original_and_missing_when_var_unset(self):
            """${VAR} with VAR unset returns original ${VAR}, [VAR] in missing."""
            result, missing = substitute_env_vars("${UNDEFINED_VAR_12345}")

            assert result == "${UNDEFINED_VAR_12345}"
            assert "UNDEFINED_VAR_12345" in missing

        def test_empty_env_var_substitutes_to_empty_string(self, monkeypatch):
            """${VAR} with VAR="" returns empty string, not missing."""
            monkeypatch.setenv("EMPTY_VAR", "")

            result, missing = substitute_env_vars("${EMPTY_VAR}")

            assert result == ""
            assert missing == []

    class TestDefaultValueSubstitution:
        """Test ${VAR:-default} substitution."""

        def test_uses_default_when_var_unset(self):
            """${VAR:-fallback} with VAR unset returns 'fallback', empty missing."""
            result, missing = substitute_env_vars("${UNDEFINED_VAR_12345:-fallback}")

            assert result == "fallback"
            assert missing == []

        def test_uses_var_value_when_set(self, monkeypatch):
            """${VAR:-fallback} with VAR set returns VAR value, empty missing."""
            monkeypatch.setenv("MY_VAR", "actual_value")

            result, missing = substitute_env_vars("${MY_VAR:-fallback}")

            assert result == "actual_value"
            assert missing == []

        def test_empty_default_when_var_unset(self):
            """${VAR:-} with VAR unset returns empty string."""
            result, missing = substitute_env_vars("${UNDEFINED_VAR_12345:-}")

            assert result == ""
            assert missing == []

        def test_empty_var_overrides_default(self, monkeypatch):
            """${VAR:-default} with VAR="" returns empty string (VAR is set)."""
            monkeypatch.setenv("EMPTY_VAR", "")

            result, missing = substitute_env_vars("${EMPTY_VAR:-default}")

            assert result == ""
            assert missing == []

    class TestPartialSubstitution:
        """Test substitution within larger strings."""

        def test_prefix_and_suffix_preserved(self, monkeypatch):
            """prefix_${VAR}_suffix substitutes correctly."""
            monkeypatch.setenv("MY_VAR", "value")

            result, missing = substitute_env_vars("prefix_${MY_VAR}_suffix")

            assert result == "prefix_value_suffix"
            assert missing == []

        def test_multiple_vars_in_one_string(self, monkeypatch):
            """Multiple ${} in one string all substituted."""
            monkeypatch.setenv("HOST", "localhost")
            monkeypatch.setenv("PORT", "8080")

            result, missing = substitute_env_vars("http://${HOST}:${PORT}/api")

            assert result == "http://localhost:8080/api"
            assert missing == []

        def test_mixed_set_and_unset_vars(self, monkeypatch):
            """Mix of set and unset vars in one string."""
            monkeypatch.setenv("HOST", "localhost")

            result, missing = substitute_env_vars(
                "http://${HOST}:${UNDEFINED_PORT_12345}/api"
            )

            assert result == "http://localhost:${UNDEFINED_PORT_12345}/api"
            assert "UNDEFINED_PORT_12345" in missing

    class TestRecursiveSubstitution:
        """Test substitution in nested data structures."""

        def test_nested_dict_substitution(self, monkeypatch):
            """Nested dict values are substituted recursively."""
            monkeypatch.setenv("DB_HOST", "localhost")
            monkeypatch.setenv("DB_NAME", "mydb")

            data = {
                "database": {
                    "host": "${DB_HOST}",
                    "name": "${DB_NAME}",
                }
            }

            result, missing = substitute_env_vars(data)

            assert result == {
                "database": {
                    "host": "localhost",
                    "name": "mydb",
                }
            }
            assert missing == []

        def test_list_substitution(self, monkeypatch):
            """List elements are substituted."""
            monkeypatch.setenv("PATTERN1", "*.py")
            monkeypatch.setenv("PATTERN2", "*.ts")

            data = ["${PATTERN1}", "${PATTERN2}", "*.md"]

            result, missing = substitute_env_vars(data)

            assert result == ["*.py", "*.ts", "*.md"]
            assert missing == []

        def test_mixed_nested_structure(self, monkeypatch):
            """Complex nested structure with dicts and lists."""
            monkeypatch.setenv("INDEX_NAME", "my-index")
            monkeypatch.setenv("MODEL", "nomic-embed-text")

            data = {
                "indexName": "${INDEX_NAME}",
                "embedding": {"model": "${MODEL}"},
                "indexing": {
                    "includePatterns": ["${INDEX_NAME}/**/*.py", "src/**/*.ts"]
                },
            }

            result, missing = substitute_env_vars(data)

            assert result["indexName"] == "my-index"
            assert result["embedding"]["model"] == "nomic-embed-text"
            assert result["indexing"]["includePatterns"] == [
                "my-index/**/*.py",
                "src/**/*.ts",
            ]
            assert missing == []

    class TestNonStringValues:
        """Test that non-string values pass through unchanged."""

        def test_integer_unchanged(self):
            """Integer values pass through unchanged."""
            result, missing = substitute_env_vars(42)

            assert result == 42
            assert missing == []

        def test_float_unchanged(self):
            """Float values pass through unchanged."""
            result, missing = substitute_env_vars(3.14)

            assert result == 3.14
            assert missing == []

        def test_bool_unchanged(self):
            """Boolean values pass through unchanged."""
            result, missing = substitute_env_vars(True)

            assert result is True
            assert missing == []

        def test_none_unchanged(self):
            """None values pass through unchanged."""
            result, missing = substitute_env_vars(None)

            assert result is None
            assert missing == []

        def test_dict_with_non_string_values(self, monkeypatch):
            """Dict with mixed string and non-string values."""
            monkeypatch.setenv("NAME", "test")

            data = {
                "name": "${NAME}",
                "count": 10,
                "ratio": 0.5,
                "enabled": True,
                "extra": None,
            }

            result, missing = substitute_env_vars(data)

            assert result["name"] == "test"
            assert result["count"] == 10
            assert result["ratio"] == 0.5
            assert result["enabled"] is True
            assert result["extra"] is None
            assert missing == []

    class TestMissingVarCollection:
        """Test that missing vars are collected correctly."""

        def test_deduplicates_missing_vars(self):
            """Same missing var referenced multiple times appears once."""
            data = {
                "a": "${MISSING_12345}",
                "b": "${MISSING_12345}",
                "c": "${MISSING_12345}",
            }

            result, missing = substitute_env_vars(data)

            assert missing.count("MISSING_12345") == 1

        def test_collects_multiple_different_missing_vars(self):
            """Multiple different missing vars are all collected."""
            data = {
                "a": "${MISSING_A_12345}",
                "b": "${MISSING_B_12345}",
            }

            result, missing = substitute_env_vars(data)

            assert "MISSING_A_12345" in missing
            assert "MISSING_B_12345" in missing
            assert len(missing) == 2

        def test_vars_with_defaults_not_in_missing(self):
            """Vars with defaults (${VAR:-default}) never appear in missing."""
            data = "${UNDEFINED_12345:-default}"

            result, missing = substitute_env_vars(data)

            assert "UNDEFINED_12345" not in missing
            assert missing == []

    class TestEdgeCases:
        """Test edge cases and boundary conditions."""

        def test_empty_string_unchanged(self):
            """Empty string passes through unchanged."""
            result, missing = substitute_env_vars("")

            assert result == ""
            assert missing == []

        def test_string_without_vars_unchanged(self):
            """String with no ${} pattern passes through unchanged."""
            result, missing = substitute_env_vars("just a regular string")

            assert result == "just a regular string"
            assert missing == []

        def test_empty_dict_unchanged(self):
            """Empty dict passes through unchanged."""
            result, missing = substitute_env_vars({})

            assert result == {}
            assert missing == []

        def test_empty_list_unchanged(self):
            """Empty list passes through unchanged."""
            result, missing = substitute_env_vars([])

            assert result == []
            assert missing == []

        def test_deeply_nested_structure(self, monkeypatch):
            """Deeply nested structure is handled correctly."""
            monkeypatch.setenv("DEEP_VAR", "found")

            data = {"level1": {"level2": {"level3": {"level4": "${DEEP_VAR}"}}}}

            result, missing = substitute_env_vars(data)

            assert result["level1"]["level2"]["level3"]["level4"] == "found"
            assert missing == []
