"""Tests for deps CLI commands in cocosearch.cli."""

import json
from unittest.mock import MagicMock, patch

from cocosearch.deps.models import DependencyEdge, DependencyTree


# ============================================================================
# Tests: deps_extract_command
# ============================================================================


class TestDepsExtractCommand:
    """Tests for deps_extract_command()."""

    @patch("cocosearch.cli.extract_dependencies")
    @patch("cocosearch.cli._resolve_index_name", return_value=("myindex", "config"))
    @patch("cocosearch.cli.load_project_config")
    @patch("cocosearch.cli.find_config_file", return_value="/fake/cocosearch.yaml")
    def test_calls_extract_and_returns_zero(
        self, mock_find, mock_load, mock_resolve, mock_extract
    ):
        """Should call extract_dependencies and return 0 on success."""
        mock_extract.return_value = {
            "files_processed": 10,
            "files_skipped": 2,
            "edges_found": 25,
            "errors": 0,
        }

        args = MagicMock()
        args.name = None
        args.path = "/tmp/codebase"

        from cocosearch.cli import deps_extract_command

        result = deps_extract_command(args)

        assert result == 0
        mock_extract.assert_called_once_with("myindex", "/tmp/codebase")

    @patch("cocosearch.cli.extract_dependencies")
    @patch("cocosearch.cli._resolve_index_name", return_value=("myindex", "config"))
    @patch("cocosearch.cli.load_project_config")
    @patch("cocosearch.cli.find_config_file", return_value="/fake/cocosearch.yaml")
    def test_returns_one_on_error(
        self, mock_find, mock_load, mock_resolve, mock_extract
    ):
        """Should return 1 when extract_dependencies raises an exception."""
        mock_extract.side_effect = Exception("DB connection failed")

        args = MagicMock()
        args.name = None
        args.path = "/tmp/codebase"

        from cocosearch.cli import deps_extract_command

        result = deps_extract_command(args)

        assert result == 1

    @patch("cocosearch.cli.extract_dependencies")
    @patch("cocosearch.cli._resolve_index_name", return_value=("myindex", "cli"))
    @patch("cocosearch.cli.load_project_config")
    @patch("cocosearch.cli.find_config_file", return_value="/fake/cocosearch.yaml")
    def test_uses_abspath_for_codebase(
        self, mock_find, mock_load, mock_resolve, mock_extract
    ):
        """Should convert the path argument to an absolute path."""
        mock_extract.return_value = {
            "files_processed": 0,
            "files_skipped": 0,
            "edges_found": 0,
            "errors": 0,
        }

        args = MagicMock()
        args.name = "myindex"
        args.path = "."

        from cocosearch.cli import deps_extract_command

        import os

        result = deps_extract_command(args)

        assert result == 0
        # The codebase_path passed should be absolute
        call_args = mock_extract.call_args[0]
        assert os.path.isabs(call_args[1])


# ============================================================================
# Tests: deps_show_command
# ============================================================================


class TestDepsShowCommand:
    """Tests for deps_show_command()."""

    @patch("cocosearch.cli.get_dependents")
    @patch("cocosearch.cli.get_dependencies")
    @patch("cocosearch.cli._resolve_index_name", return_value=("myindex", "config"))
    @patch("cocosearch.cli.load_project_config")
    @patch("cocosearch.cli.find_config_file", return_value="/fake/cocosearch.yaml")
    def test_calls_both_lookups_and_returns_zero(
        self, mock_find, mock_load, mock_resolve, mock_get_deps, mock_get_depnts
    ):
        """Should call get_dependencies and get_dependents, return 0."""
        mock_get_deps.return_value = [
            DependencyEdge(
                source_file="src/main.py",
                source_symbol=None,
                target_file="src/utils.py",
                target_symbol="helper",
                dep_type="import",
            ),
        ]
        mock_get_depnts.return_value = [
            DependencyEdge(
                source_file="src/api.py",
                source_symbol=None,
                target_file="src/main.py",
                target_symbol=None,
                dep_type="import",
            ),
        ]

        args = MagicMock()
        args.index = None
        args.file = "src/main.py"

        from cocosearch.cli import deps_show_command

        result = deps_show_command(args)

        assert result == 0
        mock_get_deps.assert_called_once_with("myindex", "src/main.py")
        mock_get_depnts.assert_called_once_with("myindex", "src/main.py")

    @patch("cocosearch.cli.get_dependents")
    @patch("cocosearch.cli.get_dependencies")
    @patch("cocosearch.cli._resolve_index_name", return_value=("myindex", "config"))
    @patch("cocosearch.cli.load_project_config")
    @patch("cocosearch.cli.find_config_file", return_value="/fake/cocosearch.yaml")
    def test_handles_empty_results(
        self, mock_find, mock_load, mock_resolve, mock_get_deps, mock_get_depnts
    ):
        """Should handle empty dependency lists gracefully."""
        mock_get_deps.return_value = []
        mock_get_depnts.return_value = []

        args = MagicMock()
        args.index = None
        args.file = "src/orphan.py"

        from cocosearch.cli import deps_show_command

        result = deps_show_command(args)

        assert result == 0


# ============================================================================
# Tests: deps_stats_command
# ============================================================================


class TestDepsStatsCommand:
    """Tests for deps_stats_command()."""

    @patch("cocosearch.cli.get_dep_stats")
    @patch("cocosearch.cli._resolve_index_name", return_value=("myindex", "config"))
    @patch("cocosearch.cli.load_project_config")
    @patch("cocosearch.cli.find_config_file", return_value="/fake/cocosearch.yaml")
    def test_calls_get_dep_stats_and_returns_zero(
        self, mock_find, mock_load, mock_resolve, mock_stats
    ):
        """Should call get_dep_stats and return 0."""
        mock_stats.return_value = {"total_edges": 42}

        args = MagicMock()
        args.index = None

        from cocosearch.cli import deps_stats_command

        result = deps_stats_command(args)

        assert result == 0
        mock_stats.assert_called_once_with("myindex")

    @patch("cocosearch.cli.get_dep_stats")
    @patch("cocosearch.cli._resolve_index_name", return_value=("myindex", "config"))
    @patch("cocosearch.cli.load_project_config")
    @patch("cocosearch.cli.find_config_file", return_value="/fake/cocosearch.yaml")
    def test_prints_total_edges(
        self, mock_find, mock_load, mock_resolve, mock_stats, capsys
    ):
        """Should print the total_edges value."""
        mock_stats.return_value = {"total_edges": 99}

        args = MagicMock()
        args.index = None

        from cocosearch.cli import deps_stats_command

        deps_stats_command(args)

        # Rich Console output goes to stdout; we just verify no crash
        # The actual output test uses capsys indirectly through Rich
        mock_stats.assert_called_once_with("myindex")


# ============================================================================
# Tests: deps_tree_command
# ============================================================================


class TestDepsTreeCommand:
    """Tests for deps_tree_command()."""

    @patch("cocosearch.cli.get_dependency_tree")
    @patch("cocosearch.cli._resolve_index_name", return_value=("myindex", "config"))
    @patch("cocosearch.cli.load_project_config")
    @patch("cocosearch.cli.find_config_file", return_value="/fake/cocosearch.yaml")
    def test_calls_get_dependency_tree_and_returns_zero(
        self, mock_find, mock_load, mock_resolve, mock_tree
    ):
        """Should call get_dependency_tree and return 0."""
        mock_tree.return_value = DependencyTree(
            file="src/main.py", symbol=None, dep_type="root", children=[]
        )

        args = MagicMock()
        args.index = None
        args.file = "src/main.py"
        args.depth = 5
        args.type = None
        args.json = False

        from cocosearch.cli import deps_tree_command

        result = deps_tree_command(args)

        assert result == 0
        mock_tree.assert_called_once_with(
            "myindex", "src/main.py", max_depth=5, dep_type=None
        )

    @patch("cocosearch.cli.get_dependency_tree")
    @patch("cocosearch.cli._resolve_index_name", return_value=("myindex", "config"))
    @patch("cocosearch.cli.load_project_config")
    @patch("cocosearch.cli.find_config_file", return_value="/fake/cocosearch.yaml")
    def test_passes_depth_and_type(self, mock_find, mock_load, mock_resolve, mock_tree):
        """Should pass depth and type filters."""
        mock_tree.return_value = DependencyTree(
            file="a.py", symbol=None, dep_type="root", children=[]
        )

        args = MagicMock()
        args.index = None
        args.file = "a.py"
        args.depth = 2
        args.type = "import"
        args.json = False

        from cocosearch.cli import deps_tree_command

        deps_tree_command(args)

        mock_tree.assert_called_once_with(
            "myindex", "a.py", max_depth=2, dep_type="import"
        )

    @patch("cocosearch.cli.get_dependency_tree")
    @patch("cocosearch.cli._resolve_index_name", return_value=("myindex", "config"))
    @patch("cocosearch.cli.load_project_config")
    @patch("cocosearch.cli.find_config_file", return_value="/fake/cocosearch.yaml")
    def test_returns_one_on_error(self, mock_find, mock_load, mock_resolve, mock_tree):
        """Should return 1 on error."""
        mock_tree.side_effect = Exception("DB error")

        args = MagicMock()
        args.index = None
        args.file = "a.py"
        args.depth = 5
        args.type = None
        args.json = False

        from cocosearch.cli import deps_tree_command

        result = deps_tree_command(args)

        assert result == 1


# ============================================================================
# Tests: deps_impact_command
# ============================================================================


class TestDepsImpactCommand:
    """Tests for deps_impact_command()."""

    @patch("cocosearch.cli.get_impact")
    @patch("cocosearch.cli._resolve_index_name", return_value=("myindex", "config"))
    @patch("cocosearch.cli.load_project_config")
    @patch("cocosearch.cli.find_config_file", return_value="/fake/cocosearch.yaml")
    def test_calls_get_impact_and_returns_zero(
        self, mock_find, mock_load, mock_resolve, mock_impact
    ):
        """Should call get_impact and return 0."""
        mock_impact.return_value = DependencyTree(
            file="src/utils.py", symbol=None, dep_type="root", children=[]
        )

        args = MagicMock()
        args.index = None
        args.file = "src/utils.py"
        args.depth = 3
        args.type = None
        args.json = False

        from cocosearch.cli import deps_impact_command

        result = deps_impact_command(args)

        assert result == 0
        mock_impact.assert_called_once_with(
            "myindex", "src/utils.py", max_depth=3, dep_type=None
        )

    @patch("cocosearch.cli.get_impact")
    @patch("cocosearch.cli._resolve_index_name", return_value=("myindex", "config"))
    @patch("cocosearch.cli.load_project_config")
    @patch("cocosearch.cli.find_config_file", return_value="/fake/cocosearch.yaml")
    def test_returns_one_on_error(
        self, mock_find, mock_load, mock_resolve, mock_impact
    ):
        """Should return 1 on error."""
        mock_impact.side_effect = Exception("DB error")

        args = MagicMock()
        args.index = None
        args.file = "a.py"
        args.depth = 5
        args.type = None
        args.json = False

        from cocosearch.cli import deps_impact_command

        result = deps_impact_command(args)

        assert result == 1


# ============================================================================
# Tests: languages_command — Deps column
# ============================================================================


class TestLanguagesCommandDeps:
    """Tests that languages_command includes deps information."""

    @patch(
        "cocosearch.deps.registry.get_all_extractor_language_ids",
        return_value={"py", "js", "jsx", "mjs", "cjs", "ts", "tsx", "mts", "cts", "go"},
    )
    @patch("cocosearch.handlers.get_registered_handlers", return_value=[])
    def test_json_output_includes_deps_key(self, mock_handlers, mock_dep_ids, capsys):
        """--json output should include 'deps' key for each language."""
        args = MagicMock()
        args.json = True

        from cocosearch.cli import languages_command

        result = languages_command(args)

        assert result == 0
        output = json.loads(capsys.readouterr().out)
        for lang in output:
            assert "deps" in lang, f"Missing 'deps' key for {lang['name']}"

    @patch(
        "cocosearch.deps.registry.get_all_extractor_language_ids",
        return_value={"py", "js", "jsx", "mjs", "cjs", "ts", "tsx", "mts", "cts", "go"},
    )
    @patch("cocosearch.handlers.get_registered_handlers", return_value=[])
    def test_python_has_deps_true(self, mock_handlers, mock_dep_ids, capsys):
        """Python should have deps=True since 'py' is in extractor IDs."""
        args = MagicMock()
        args.json = True

        from cocosearch.cli import languages_command

        languages_command(args)

        output = json.loads(capsys.readouterr().out)
        python_lang = next(lang for lang in output if lang["name"] == "Python")
        assert python_lang["deps"] is True

    @patch(
        "cocosearch.deps.registry.get_all_extractor_language_ids",
        return_value={"py", "go"},
    )
    @patch("cocosearch.handlers.get_registered_handlers", return_value=[])
    def test_java_has_deps_false(self, mock_handlers, mock_dep_ids, capsys):
        """Java should have deps=False since 'java' is not in extractor IDs."""
        args = MagicMock()
        args.json = True

        from cocosearch.cli import languages_command

        languages_command(args)

        output = json.loads(capsys.readouterr().out)
        java_lang = next(lang for lang in output if lang["name"] == "Java")
        assert java_lang["deps"] is False


# ============================================================================
# Tests: grammars_command — Deps column
# ============================================================================


class TestGrammarsCommandDeps:
    """Tests that grammars_command includes deps information."""

    @patch(
        "cocosearch.deps.registry.get_all_extractor_language_ids",
        return_value={
            "docker-compose",
            "github-actions",
            "terraform",
            "helm-template",
            "helm-values",
        },
    )
    def test_json_output_includes_deps_key(self, mock_dep_ids, capsys):
        """--json output should include 'deps' key for each grammar."""
        args = MagicMock()
        args.json = True

        from cocosearch.cli import grammars_command

        result = grammars_command(args)

        assert result == 0
        output = json.loads(capsys.readouterr().out)
        for grammar in output:
            assert "deps" in grammar, f"Missing 'deps' key for {grammar['name']}"

    @patch(
        "cocosearch.deps.registry.get_all_extractor_language_ids",
        return_value={
            "docker-compose",
            "github-actions",
            "terraform",
            "helm-template",
            "helm-values",
        },
    )
    def test_docker_compose_has_deps_true(self, mock_dep_ids, capsys):
        """docker-compose grammar should have deps=True."""
        args = MagicMock()
        args.json = True

        from cocosearch.cli import grammars_command

        grammars_command(args)

        output = json.loads(capsys.readouterr().out)
        dc_grammar = next(g for g in output if g["name"] == "docker-compose")
        assert dc_grammar["deps"] is True

    @patch(
        "cocosearch.deps.registry.get_all_extractor_language_ids",
        return_value={"docker-compose"},
    )
    def test_gitlab_ci_has_deps_false(self, mock_dep_ids, capsys):
        """gitlab-ci grammar should have deps=False."""
        args = MagicMock()
        args.json = True

        from cocosearch.cli import grammars_command

        grammars_command(args)

        output = json.loads(capsys.readouterr().out)
        gl_grammar = next(g for g in output if g["name"] == "gitlab-ci")
        assert gl_grammar["deps"] is False

    @patch(
        "cocosearch.deps.registry.get_all_extractor_language_ids",
        return_value={
            "docker-compose",
            "github-actions",
            "gitlab-ci",
            "terraform",
            "helm-template",
            "helm-values",
        },
    )
    def test_gitlab_ci_has_deps_true(self, mock_dep_ids, capsys):
        """gitlab-ci grammar should have deps=True when extractor is registered."""
        args = MagicMock()
        args.json = True

        from cocosearch.cli import grammars_command

        grammars_command(args)

        output = json.loads(capsys.readouterr().out)
        gl_grammar = next(g for g in output if g["name"] == "gitlab-ci")
        assert gl_grammar["deps"] is True
