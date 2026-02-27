"""Tests for the Markdown documentation dependency extractor."""

import pytest

from cocosearch.deps.extractors.markdown import MarkdownDocExtractor
from cocosearch.deps.models import DepType


@pytest.fixture
def extractor():
    """Create a MarkdownDocExtractor instance."""
    return MarkdownDocExtractor()


# ============================================================================
# Tests: LANGUAGES attribute
# ============================================================================


class TestLanguages:
    """Tests for MarkdownDocExtractor.LANGUAGES."""

    def test_languages_contains_md(self, extractor):
        assert "md" in extractor.LANGUAGES

    def test_languages_contains_mdx(self, extractor):
        assert "mdx" in extractor.LANGUAGES


# ============================================================================
# Tests: Frontmatter depends: field
# ============================================================================


class TestFrontmatter:
    """Tests for YAML frontmatter depends: extraction."""

    def test_depends_field_extracts_paths(self, extractor):
        content = (
            "---\n"
            "title: Architecture\n"
            "depends:\n"
            "  - src/cli.py\n"
            "  - src/search/engine.py\n"
            "---\n"
            "\n"
            "# Architecture\n"
        )
        edges = extractor.extract("docs/architecture.md", content)
        fm_edges = [e for e in edges if e.metadata.get("kind") == "doc_frontmatter"]
        assert len(fm_edges) == 2
        modules = {e.metadata["module"] for e in fm_edges}
        assert modules == {"src/cli.py", "src/search/engine.py"}

    def test_depends_directory_ref(self, extractor):
        content = "---\ndepends:\n  - src/search/\n---\n\nContent here.\n"
        edges = extractor.extract("docs/guide.md", content)
        fm_edges = [e for e in edges if e.metadata.get("kind") == "doc_frontmatter"]
        assert len(fm_edges) == 1
        assert fm_edges[0].metadata["module"] == "src/search/"
        assert fm_edges[0].metadata["is_directory"] is True

    def test_file_ref_is_not_directory(self, extractor):
        content = "---\ndepends:\n  - src/cli.py\n---\n"
        edges = extractor.extract("docs/guide.md", content)
        fm_edges = [e for e in edges if e.metadata.get("kind") == "doc_frontmatter"]
        assert fm_edges[0].metadata["is_directory"] is False

    def test_missing_depends_key(self, extractor):
        content = "---\ntitle: Guide\nauthor: Someone\n---\n\n# Guide\n"
        edges = extractor.extract("docs/guide.md", content)
        fm_edges = [e for e in edges if e.metadata.get("kind") == "doc_frontmatter"]
        assert len(fm_edges) == 0

    def test_invalid_yaml_returns_empty(self, extractor):
        content = "---\ninvalid: yaml: : :\n  - [broken\n---\n"
        edges = extractor.extract("docs/broken.md", content)
        fm_edges = [e for e in edges if e.metadata.get("kind") == "doc_frontmatter"]
        assert len(fm_edges) == 0

    def test_non_list_depends_ignored(self, extractor):
        content = "---\ndepends: src/cli.py\n---\n"
        edges = extractor.extract("docs/guide.md", content)
        fm_edges = [e for e in edges if e.metadata.get("kind") == "doc_frontmatter"]
        assert len(fm_edges) == 0


# ============================================================================
# Tests: Inline links
# ============================================================================


class TestLinks:
    """Tests for inline link extraction."""

    def test_relative_link(self, extractor):
        content = "See [the CLI](src/cli.py) for details.\n"
        edges = extractor.extract("docs/guide.md", content)
        link_edges = [e for e in edges if e.metadata.get("kind") == "doc_link"]
        assert len(link_edges) == 1
        assert link_edges[0].metadata["module"] == "src/cli.py"

    def test_dot_relative_link(self, extractor):
        content = "Check [utils](./utils.py) here.\n"
        edges = extractor.extract("docs/guide.md", content)
        link_edges = [e for e in edges if e.metadata.get("kind") == "doc_link"]
        assert len(link_edges) == 1
        assert link_edges[0].metadata["module"] == "./utils.py"

    def test_parent_relative_link(self, extractor):
        content = "See [the source](../src/cli.py) for details.\n"
        edges = extractor.extract("docs/guide.md", content)
        link_edges = [e for e in edges if e.metadata.get("kind") == "doc_link"]
        assert len(link_edges) == 1
        assert link_edges[0].metadata["module"] == "../src/cli.py"

    def test_url_skipped(self, extractor):
        content = "Visit [the site](https://example.com) for more.\n"
        edges = extractor.extract("docs/guide.md", content)
        link_edges = [e for e in edges if e.metadata.get("kind") == "doc_link"]
        assert len(link_edges) == 0

    def test_anchor_only_skipped(self, extractor):
        content = "See [section](#overview) above.\n"
        edges = extractor.extract("docs/guide.md", content)
        link_edges = [e for e in edges if e.metadata.get("kind") == "doc_link"]
        assert len(link_edges) == 0

    def test_fragment_stripped(self, extractor):
        content = "See [the function](src/cli.py#L42) for details.\n"
        edges = extractor.extract("docs/guide.md", content)
        link_edges = [e for e in edges if e.metadata.get("kind") == "doc_link"]
        assert len(link_edges) == 1
        assert link_edges[0].metadata["module"] == "src/cli.py"

    def test_mailto_skipped(self, extractor):
        content = "Contact [us](mailto:test@example.com).\n"
        edges = extractor.extract("docs/guide.md", content)
        link_edges = [e for e in edges if e.metadata.get("kind") == "doc_link"]
        assert len(link_edges) == 0


# ============================================================================
# Tests: Inline code spans
# ============================================================================


class TestInlineCode:
    """Tests for inline code span path detection."""

    def test_path_like_span(self, extractor):
        content = "The entry point is `src/cli.py` in the project.\n"
        edges = extractor.extract("docs/guide.md", content)
        code_edges = [e for e in edges if e.metadata.get("kind") == "doc_inline_code"]
        assert len(code_edges) == 1
        assert code_edges[0].metadata["module"] == "src/cli.py"

    def test_directory_span(self, extractor):
        content = "Look in `src/search/` for the engine.\n"
        edges = extractor.extract("docs/guide.md", content)
        code_edges = [e for e in edges if e.metadata.get("kind") == "doc_inline_code"]
        assert len(code_edges) == 1
        assert code_edges[0].metadata["module"] == "src/search/"

    def test_non_path_span_skipped(self, extractor):
        """Non-path code spans like True, None, etc. are skipped."""
        content = "Set `True` to enable. Use `None` for default.\n"
        edges = extractor.extract("docs/guide.md", content)
        code_edges = [e for e in edges if e.metadata.get("kind") == "doc_inline_code"]
        assert len(code_edges) == 0

    def test_command_span_skipped(self, extractor):
        """CLI commands with spaces are skipped."""
        content = "Run `uv run pytest -v` to test.\n"
        edges = extractor.extract("docs/guide.md", content)
        code_edges = [e for e in edges if e.metadata.get("kind") == "doc_inline_code"]
        assert len(code_edges) == 0

    def test_expression_span_skipped(self, extractor):
        """Code expressions with operators are skipped."""
        content = "Use `len(items)` to get the count.\n"
        edges = extractor.extract("docs/guide.md", content)
        code_edges = [e for e in edges if e.metadata.get("kind") == "doc_inline_code"]
        assert len(code_edges) == 0

    def test_file_with_extension_no_slash(self, extractor):
        """A filename with a known extension is detected as a path."""
        content = "Edit `config.yaml` to change settings.\n"
        edges = extractor.extract("docs/guide.md", content)
        code_edges = [e for e in edges if e.metadata.get("kind") == "doc_inline_code"]
        assert len(code_edges) == 1
        assert code_edges[0].metadata["module"] == "config.yaml"


# ============================================================================
# Tests: Code blocks
# ============================================================================


class TestCodeBlocks:
    """Tests for fenced code block path extraction."""

    def test_path_in_comment(self, extractor):
        content = "```bash\n# Edit src/cocosearch/cli.py\necho done\n```\n"
        edges = extractor.extract("docs/guide.md", content)
        cb_edges = [e for e in edges if e.metadata.get("kind") == "doc_code_block"]
        assert len(cb_edges) == 1
        assert cb_edges[0].metadata["module"] == "src/cocosearch/cli.py"
        assert cb_edges[0].metadata["confidence"] == "low"

    def test_path_in_double_slash_comment(self, extractor):
        content = "```js\n// See src/search/engine.py for details\nconst x = 1;\n```\n"
        edges = extractor.extract("docs/guide.md", content)
        cb_edges = [e for e in edges if e.metadata.get("kind") == "doc_code_block"]
        assert len(cb_edges) == 1
        assert cb_edges[0].metadata["module"] == "src/search/engine.py"

    def test_non_comment_lines_skipped(self, extractor):
        content = "```python\nfrom cocosearch import cli\ncli.main()\n```\n"
        edges = extractor.extract("docs/guide.md", content)
        cb_edges = [e for e in edges if e.metadata.get("kind") == "doc_code_block"]
        assert len(cb_edges) == 0


# ============================================================================
# Tests: Edge fields
# ============================================================================


class TestEdgeFields:
    """Tests for DependencyEdge field values."""

    def test_source_file_is_empty(self, extractor):
        content = "See [cli](src/cli.py) here.\n"
        edges = extractor.extract("docs/guide.md", content)
        assert len(edges) >= 1
        for edge in edges:
            assert edge.source_file == ""

    def test_dep_type_is_reference(self, extractor):
        content = "See [cli](src/cli.py) here.\n"
        edges = extractor.extract("docs/guide.md", content)
        assert len(edges) >= 1
        for edge in edges:
            assert edge.dep_type == DepType.REFERENCE

    def test_line_numbers_present(self, extractor):
        content = "See [cli](src/cli.py) here.\n"
        edges = extractor.extract("docs/guide.md", content)
        assert len(edges) >= 1
        for edge in edges:
            assert "line" in edge.metadata
            assert isinstance(edge.metadata["line"], int)
            assert edge.metadata["line"] >= 1

    def test_target_file_is_none(self, extractor):
        content = "See [cli](src/cli.py) here.\n"
        edges = extractor.extract("docs/guide.md", content)
        for edge in edges:
            assert edge.target_file is None


# ============================================================================
# Tests: Empty and edge cases
# ============================================================================


class TestEmptyAndEdgeCases:
    """Tests for empty files and edge cases."""

    def test_empty_file(self, extractor):
        assert extractor.extract("docs/empty.md", "") == []

    def test_no_references(self, extractor):
        content = "# Just a heading\n\nSome plain text with no references.\n"
        edges = extractor.extract("docs/plain.md", content)
        assert len(edges) == 0

    def test_mixed_reference_types(self, extractor):
        content = (
            "---\n"
            "depends:\n"
            "  - src/cli.py\n"
            "---\n"
            "\n"
            "See [engine](src/search/engine.py) and `src/config/schema.py` for details.\n"
        )
        edges = extractor.extract("docs/guide.md", content)
        kinds = {e.metadata["kind"] for e in edges}
        assert "doc_frontmatter" in kinds
        assert "doc_link" in kinds
        assert "doc_inline_code" in kinds
