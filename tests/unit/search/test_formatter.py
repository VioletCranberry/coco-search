"""Tests for cocosearch.search.formatter module.

Tests JSON and pretty output formatters with mocked file operations.
"""

import io
import json
from unittest.mock import patch

import pytest
from rich.console import Console

from cocosearch.search.formatter import (
    format_json,
    format_pretty,
    EXTENSION_LANG_MAP,
    _get_display_language,
    _get_annotation,
)


class TestFormatJson:
    """Tests for format_json function."""

    def test_returns_valid_json(self, make_search_result):
        """Output should be parseable JSON."""
        results = [make_search_result(filename="/test/file.py", score=0.85)]

        with patch("cocosearch.search.formatter.byte_to_line", return_value=1):
            with patch("cocosearch.search.formatter.read_chunk_content", return_value="code"):
                with patch("cocosearch.search.formatter.get_context_lines", return_value=([], [])):
                    output = format_json(results)

        # Should parse without error
        parsed = json.loads(output)
        assert isinstance(parsed, list)
        assert len(parsed) == 1

    def test_includes_file_info(self, make_search_result):
        """JSON should contain file_path, start_line, end_line, score."""
        results = [make_search_result(filename="/test/file.py", score=0.85)]

        with patch("cocosearch.search.formatter.byte_to_line", side_effect=[10, 20]):
            with patch("cocosearch.search.formatter.read_chunk_content", return_value="code"):
                with patch("cocosearch.search.formatter.get_context_lines", return_value=([], [])):
                    output = format_json(results)

        parsed = json.loads(output)
        item = parsed[0]

        assert item["file_path"] == "/test/file.py"
        assert item["start_line"] == 10
        assert item["end_line"] == 20
        assert item["score"] == 0.85

    def test_includes_content(self, make_search_result):
        """JSON should contain code content when include_content is True."""
        results = [make_search_result()]
        code_content = "def hello():\n    return 'world'"

        with patch("cocosearch.search.formatter.byte_to_line", return_value=1):
            with patch("cocosearch.search.formatter.read_chunk_content", return_value=code_content):
                with patch("cocosearch.search.formatter.get_context_lines", return_value=([], [])):
                    output = format_json(results, include_content=True)

        parsed = json.loads(output)
        assert parsed[0]["content"] == code_content

    def test_excludes_content_when_disabled(self, make_search_result):
        """JSON should not contain content when include_content is False."""
        results = [make_search_result()]

        with patch("cocosearch.search.formatter.byte_to_line", return_value=1):
            with patch("cocosearch.search.formatter.read_chunk_content", return_value="code"):
                output = format_json(results, include_content=False)

        parsed = json.loads(output)
        assert "content" not in parsed[0]

    def test_includes_context_lines(self, make_search_result):
        """JSON should contain context_before and context_after as strings."""
        from unittest.mock import MagicMock

        results = [make_search_result()]

        mock_expander = MagicMock()
        mock_expander.get_context_lines.return_value = (
            [(3, "# Line before 1"), (4, "# Line before 2")],  # before
            [(5, "code")],  # match
            [(6, "# Line after 1")],  # after
            False, False
        )

        with patch("cocosearch.search.formatter.ContextExpander", return_value=mock_expander):
            with patch("cocosearch.search.formatter.byte_to_line", return_value=5):
                with patch("cocosearch.search.formatter.read_chunk_content", return_value="code"):
                    output = format_json(results, context_lines=2)

        parsed = json.loads(output)
        # Context is now newline-separated string, not list
        assert "# Line before 1" in parsed[0]["context_before"]
        assert "# Line before 2" in parsed[0]["context_before"]
        assert "# Line after 1" in parsed[0]["context_after"]

    def test_no_context_when_disabled(self, make_search_result):
        """JSON should have empty context when smart_context=False and no lines requested."""
        from unittest.mock import MagicMock

        results = [make_search_result()]

        mock_expander = MagicMock()
        mock_expander.get_context_lines.return_value = ([], [], [], False, False)

        with patch("cocosearch.search.formatter.ContextExpander", return_value=mock_expander):
            with patch("cocosearch.search.formatter.byte_to_line", return_value=1):
                with patch("cocosearch.search.formatter.read_chunk_content", return_value="code"):
                    # With smart_context=False and context=0, minimal context
                    output = format_json(results, context_lines=0, smart_context=False)

        parsed = json.loads(output)
        # Context fields are present but empty
        assert parsed[0]["context_before"] == ""
        assert parsed[0]["context_after"] == ""

    def test_multiple_results(self, sample_search_results):
        """Should handle multiple results."""
        with patch("cocosearch.search.formatter.byte_to_line", return_value=1):
            with patch("cocosearch.search.formatter.read_chunk_content", return_value="code"):
                with patch("cocosearch.search.formatter.get_context_lines", return_value=([], [])):
                    output = format_json(sample_search_results)

        parsed = json.loads(output)
        assert len(parsed) == 3

    def test_empty_results(self):
        """Should handle empty results list."""
        output = format_json([])
        parsed = json.loads(output)
        assert parsed == []

    def test_score_rounding(self, make_search_result):
        """Score should be rounded to 4 decimal places."""
        results = [make_search_result(score=0.85678901234)]

        with patch("cocosearch.search.formatter.byte_to_line", return_value=1):
            with patch("cocosearch.search.formatter.read_chunk_content", return_value="code"):
                with patch("cocosearch.search.formatter.get_context_lines", return_value=([], [])):
                    output = format_json(results)

        parsed = json.loads(output)
        assert parsed[0]["score"] == 0.8568  # Rounded to 4 decimals


class TestFormatPretty:
    """Tests for format_pretty function."""

    def _make_console(self) -> tuple[Console, io.StringIO]:
        """Create a Rich Console that captures output to a StringIO."""
        output = io.StringIO()
        console = Console(file=output, force_terminal=True, width=100)
        return console, output

    def test_outputs_to_console(self, make_search_result, tmp_path):
        """Should write to Rich console without error."""
        results = [make_search_result()]
        console, output = self._make_console()

        with patch("cocosearch.search.formatter.byte_to_line", return_value=1):
            with patch("cocosearch.search.formatter.read_chunk_content", return_value="def hello(): pass"):
                # format_pretty should not raise
                format_pretty(results, console=console)

        # Should have written something
        assert len(output.getvalue()) > 0

    def test_shows_filename(self, make_search_result, tmp_path):
        """Output should contain filename."""
        # Create a real file so os.path.exists returns True
        test_file = tmp_path / "testfile.py"
        test_file.write_text("code content")

        results = [make_search_result(filename=str(test_file))]
        console, output = self._make_console()

        with patch("cocosearch.search.formatter.byte_to_line", return_value=1):
            with patch("cocosearch.search.formatter.read_chunk_content", return_value="code"):
                format_pretty(results, console=console)

        captured = output.getvalue()
        # Should contain the filename (may be relative path)
        assert "testfile.py" in captured

    def test_shows_score(self, make_search_result):
        """Output should contain similarity score."""
        results = [make_search_result(score=0.85)]
        console, output = self._make_console()

        with patch("cocosearch.search.formatter.byte_to_line", return_value=1):
            with patch("cocosearch.search.formatter.read_chunk_content", return_value="code"):
                format_pretty(results, console=console)

        captured = output.getvalue()
        assert "0.85" in captured

    def test_shows_line_numbers(self, make_search_result):
        """Output should show line range."""
        results = [make_search_result()]
        console, output = self._make_console()

        with patch("cocosearch.search.formatter.byte_to_line", side_effect=[10, 25]):
            with patch("cocosearch.search.formatter.read_chunk_content", return_value="code"):
                format_pretty(results, console=console)

        captured = output.getvalue()
        # Should show line range
        assert "10" in captured
        assert "25" in captured

    def test_no_results_message(self):
        """Should show 'No results found' for empty results."""
        console, output = self._make_console()

        format_pretty([], console=console)

        captured = output.getvalue()
        assert "No results found" in captured

    def test_groups_by_file(self, make_search_result):
        """Results from same file should be grouped together."""
        results = [
            make_search_result(filename="/project/auth.py", start_byte=0, end_byte=50, score=0.9),
            make_search_result(filename="/project/auth.py", start_byte=100, end_byte=150, score=0.7),
        ]
        console, output = self._make_console()

        with patch("cocosearch.search.formatter.byte_to_line", return_value=1):
            with patch("cocosearch.search.formatter.read_chunk_content", return_value="code"):
                format_pretty(results, console=console)

        captured = output.getvalue()
        # File path should appear (grouped, not repeated for each result)
        assert "auth.py" in captured

    def test_result_count_header(self, sample_search_results):
        """Should show total result count."""
        console, output = self._make_console()

        with patch("cocosearch.search.formatter.byte_to_line", return_value=1):
            with patch("cocosearch.search.formatter.read_chunk_content", return_value="code"):
                format_pretty(sample_search_results, console=console)

        captured = output.getvalue()
        # Check for key parts (ANSI codes may break exact string matching)
        assert "Found" in captured
        assert "3" in captured
        assert "results" in captured


class TestExtensionLangMap:
    """Tests for EXTENSION_LANG_MAP constant."""

    def test_python_mapping(self):
        """Python extensions should map to 'python'."""
        assert EXTENSION_LANG_MAP["py"] == "python"
        assert EXTENSION_LANG_MAP["pyw"] == "python"
        assert EXTENSION_LANG_MAP["pyi"] == "python"

    def test_javascript_mapping(self):
        """JavaScript extensions should map to 'javascript'."""
        assert EXTENSION_LANG_MAP["js"] == "javascript"
        assert EXTENSION_LANG_MAP["mjs"] == "javascript"

    def test_typescript_mapping(self):
        """TypeScript extensions should map to 'typescript'."""
        assert EXTENSION_LANG_MAP["ts"] == "typescript"
        assert EXTENSION_LANG_MAP["tsx"] == "typescript"

    def test_common_extensions_present(self):
        """Common file extensions should be present."""
        expected = ["py", "js", "ts", "go", "rs", "java", "rb", "cpp", "c"]
        for ext in expected:
            assert ext in EXTENSION_LANG_MAP


class TestFormatJsonMetadata:
    """Tests for metadata fields in format_json output."""

    def test_json_includes_metadata_fields(self, make_search_result):
        """JSON output should include block_type, hierarchy, language_id for DevOps results."""
        results = [make_search_result(
            filename="/infra/main.tf",
            score=0.9,
            block_type="resource",
            hierarchy="resource.aws_s3_bucket.data",
            language_id="hcl",
        )]

        with patch("cocosearch.search.formatter.byte_to_line", return_value=1):
            with patch("cocosearch.search.formatter.read_chunk_content", return_value="resource {}"):
                with patch("cocosearch.search.formatter.get_context_lines", return_value=([], [])):
                    output = format_json(results)

        parsed = json.loads(output)
        item = parsed[0]
        assert item["block_type"] == "resource"
        assert item["hierarchy"] == "resource.aws_s3_bucket.data"
        assert item["language_id"] == "hcl"

    def test_json_empty_metadata_for_non_devops(self, make_search_result):
        """Non-DevOps results should have empty string metadata fields."""
        results = [make_search_result(filename="/test/file.py", score=0.85)]

        with patch("cocosearch.search.formatter.byte_to_line", return_value=1):
            with patch("cocosearch.search.formatter.read_chunk_content", return_value="code"):
                with patch("cocosearch.search.formatter.get_context_lines", return_value=([], [])):
                    output = format_json(results)

        parsed = json.loads(output)
        item = parsed[0]
        assert item["block_type"] == ""
        assert item["hierarchy"] == ""
        assert item["language_id"] == ""

    def test_json_metadata_consistent_shape(self, make_search_result):
        """DevOps and non-DevOps results should have identical key sets."""
        devops_result = make_search_result(
            filename="/infra/main.tf",
            block_type="resource",
            hierarchy="resource.aws_s3_bucket.data",
            language_id="hcl",
        )
        non_devops_result = make_search_result(filename="/test/file.py")

        with patch("cocosearch.search.formatter.byte_to_line", return_value=1):
            with patch("cocosearch.search.formatter.read_chunk_content", return_value="code"):
                with patch("cocosearch.search.formatter.get_context_lines", return_value=([], [])):
                    devops_output = format_json([devops_result])
                    non_devops_output = format_json([non_devops_result])

        devops_keys = set(json.loads(devops_output)[0].keys())
        non_devops_keys = set(json.loads(non_devops_output)[0].keys())
        assert devops_keys == non_devops_keys


class TestFormatPrettyAnnotation:
    """Tests for annotation prefix in format_pretty output."""

    def _make_console(self) -> tuple[Console, io.StringIO]:
        """Create a Rich Console that captures plain text (no ANSI codes)."""
        output = io.StringIO()
        console = Console(file=output, no_color=True, width=100)
        return console, output

    def test_shows_language_annotation(self, make_search_result):
        """Pretty output should show [language] hierarchy annotation."""
        results = [make_search_result(
            filename="/infra/main.tf",
            language_id="hcl",
            hierarchy="resource.aws_s3_bucket.data",
        )]
        console, output = self._make_console()

        with patch("cocosearch.search.formatter.byte_to_line", return_value=1):
            with patch("cocosearch.search.formatter.read_chunk_content", return_value="resource {}"):
                format_pretty(results, console=console)

        captured = output.getvalue()
        assert "[hcl] resource.aws_s3_bucket.data" in captured

    def test_shows_language_only_without_hierarchy(self, make_search_result):
        """When hierarchy is empty, show only [language] annotation."""
        results = [make_search_result(
            filename="/infra/main.tf",
            language_id="hcl",
            hierarchy="",
        )]
        console, output = self._make_console()

        with patch("cocosearch.search.formatter.byte_to_line", return_value=1):
            with patch("cocosearch.search.formatter.read_chunk_content", return_value="code"):
                format_pretty(results, console=console)

        captured = output.getvalue()
        assert "[hcl]" in captured
        assert "resource" not in captured

    def test_non_devops_shows_extension_language(self, make_search_result):
        """Non-DevOps files should show extension-derived language tag."""
        results = [make_search_result(filename="/test/file.py")]
        console, output = self._make_console()

        with patch("cocosearch.search.formatter.byte_to_line", return_value=1):
            with patch("cocosearch.search.formatter.read_chunk_content", return_value="def test(): pass"):
                format_pretty(results, console=console)

        captured = output.getvalue()
        assert "[python]" in captured

    def test_dockerfile_syntax_highlighting_uses_docker_lexer(self, make_search_result):
        """Dockerfile with language_id should render without error (uses docker lexer)."""
        results = [make_search_result(
            filename="/app/Dockerfile",
            language_id="dockerfile",
        )]
        console, output = self._make_console()

        with patch("cocosearch.search.formatter.byte_to_line", return_value=1):
            with patch("cocosearch.search.formatter.read_chunk_content", return_value="FROM ubuntu:22.04"):
                format_pretty(results, console=console)

        captured = output.getvalue()
        # Should render content without crashing
        assert len(captured) > 0
        assert "[dockerfile]" in captured


class TestExtensionLangMapDevOps:
    """Tests for DevOps entries in EXTENSION_LANG_MAP."""

    def test_hcl_extensions(self):
        """HCL/Terraform extensions should map to 'hcl'."""
        assert EXTENSION_LANG_MAP["tf"] == "hcl"
        assert EXTENSION_LANG_MAP["hcl"] == "hcl"
        assert EXTENSION_LANG_MAP["tfvars"] == "hcl"


class TestFormatJsonHybridFields:
    """Tests for hybrid search fields in format_json output."""

    def test_format_json_includes_match_type(self, make_search_result):
        """JSON output should include match_type when set."""
        results = [make_search_result(
            filename="/test/file.py",
            score=0.85,
            match_type="both",
            vector_score=0.82,
            keyword_score=0.45,
        )]

        with patch("cocosearch.search.formatter.byte_to_line", return_value=1):
            with patch("cocosearch.search.formatter.read_chunk_content", return_value="code"):
                with patch("cocosearch.search.formatter.get_context_lines", return_value=([], [])):
                    output = format_json(results)

        parsed = json.loads(output)
        item = parsed[0]
        assert item["match_type"] == "both"

    def test_format_json_includes_score_breakdown(self, make_search_result):
        """JSON output should include vector_score and keyword_score when set."""
        results = [make_search_result(
            filename="/test/file.py",
            score=0.85,
            match_type="both",
            vector_score=0.82345678,
            keyword_score=0.45678901,
        )]

        with patch("cocosearch.search.formatter.byte_to_line", return_value=1):
            with patch("cocosearch.search.formatter.read_chunk_content", return_value="code"):
                with patch("cocosearch.search.formatter.get_context_lines", return_value=([], [])):
                    output = format_json(results)

        parsed = json.loads(output)
        item = parsed[0]
        # Scores should be rounded to 4 decimal places
        assert item["vector_score"] == 0.8235
        assert item["keyword_score"] == 0.4568

    def test_format_json_omits_none_scores(self, make_search_result):
        """JSON output should omit vector_score and keyword_score when None."""
        results = [make_search_result(
            filename="/test/file.py",
            score=0.85,
            # match_type and scores left at defaults (empty string, None)
        )]

        with patch("cocosearch.search.formatter.byte_to_line", return_value=1):
            with patch("cocosearch.search.formatter.read_chunk_content", return_value="code"):
                with patch("cocosearch.search.formatter.get_context_lines", return_value=([], [])):
                    output = format_json(results)

        parsed = json.loads(output)
        item = parsed[0]
        # None values should be omitted, not included as null
        assert "match_type" not in item
        assert "vector_score" not in item
        assert "keyword_score" not in item

    def test_format_json_backward_compat_no_hybrid_fields(self, make_search_result):
        """JSON output should maintain backward compatible structure for non-hybrid results."""
        results = [make_search_result(
            filename="/test/file.py",
            score=0.85,
            block_type="function",
            hierarchy="module.function",
            language_id="python",
        )]

        with patch("cocosearch.search.formatter.byte_to_line", return_value=1):
            with patch("cocosearch.search.formatter.read_chunk_content", return_value="def test(): pass"):
                with patch("cocosearch.search.formatter.get_context_lines", return_value=([], [])):
                    output = format_json(results)

        parsed = json.loads(output)
        item = parsed[0]

        # Standard fields should be present
        assert item["file_path"] == "/test/file.py"
        assert item["score"] == 0.85
        assert item["block_type"] == "function"
        assert item["hierarchy"] == "module.function"
        assert item["language_id"] == "python"

        # Hybrid fields should not be present (backward compat)
        assert "match_type" not in item
        assert "vector_score" not in item
        assert "keyword_score" not in item


class TestFormatPrettyHybridMatchType:
    """Tests for hybrid search match type indicators in format_pretty."""

    def _make_console(self) -> tuple[Console, io.StringIO]:
        """Create a Rich Console that captures plain text (no ANSI codes)."""
        output = io.StringIO()
        console = Console(file=output, no_color=True, width=100)
        return console, output

    def test_format_pretty_semantic_match_type(self, make_search_result):
        """Pretty output should show [semantic] indicator in cyan for vector-only matches."""
        results = [make_search_result(
            filename="/test/file.py",
            score=0.85,
            match_type="semantic",
        )]
        console, output = self._make_console()

        with patch("cocosearch.search.formatter.byte_to_line", return_value=1):
            with patch("cocosearch.search.formatter.read_chunk_content", return_value="code"):
                format_pretty(results, console=console)

        captured = output.getvalue()
        # Should contain [semantic] indicator (Rich escapes brackets)
        assert "[semantic]" in captured

    def test_format_pretty_keyword_match_type(self, make_search_result):
        """Pretty output should show [keyword] indicator in green for keyword-only matches."""
        results = [make_search_result(
            filename="/test/file.py",
            score=0.85,
            match_type="keyword",
        )]
        console, output = self._make_console()

        with patch("cocosearch.search.formatter.byte_to_line", return_value=1):
            with patch("cocosearch.search.formatter.read_chunk_content", return_value="code"):
                format_pretty(results, console=console)

        captured = output.getvalue()
        # Should contain [keyword] indicator
        assert "[keyword]" in captured

    def test_format_pretty_both_match_type(self, make_search_result):
        """Pretty output should show [both] indicator in yellow for double matches."""
        results = [make_search_result(
            filename="/test/file.py",
            score=0.90,
            match_type="both",
        )]
        console, output = self._make_console()

        with patch("cocosearch.search.formatter.byte_to_line", return_value=1):
            with patch("cocosearch.search.formatter.read_chunk_content", return_value="code"):
                format_pretty(results, console=console)

        captured = output.getvalue()
        # Should contain [both] indicator
        assert "[both]" in captured

    def test_format_pretty_no_match_type_backward_compat(self, make_search_result):
        """Pretty output should not show match indicator for non-hybrid results."""
        # Default match_type is empty string (backward compat)
        results = [make_search_result(
            filename="/test/file.py",
            score=0.85,
        )]
        console, output = self._make_console()

        with patch("cocosearch.search.formatter.byte_to_line", return_value=1):
            with patch("cocosearch.search.formatter.read_chunk_content", return_value="code"):
                format_pretty(results, console=console)

        captured = output.getvalue()
        # Should NOT contain any match type indicators
        assert "[semantic]" not in captured
        assert "[keyword]" not in captured
        assert "[both]" not in captured
