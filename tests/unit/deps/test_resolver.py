"""Tests for cocosearch.deps.resolver module."""

from cocosearch.deps.models import DependencyEdge, DepType
from cocosearch.deps.resolver import (
    GoResolver,
    JavaScriptResolver,
    PythonResolver,
    get_resolver,
    get_resolvers,
)


def _make_edge(source_file, module, target_file=None):
    return DependencyEdge(
        source_file=source_file,
        source_symbol=None,
        target_file=target_file,
        target_symbol=None,
        dep_type=DepType.IMPORT,
        metadata={"module": module, "line": 1},
    )


# ============================================================================
# Tests: PythonResolver.build_index
# ============================================================================


class TestPythonResolverBuildIndex:
    """Tests for PythonResolver.build_index()."""

    def test_regular_python_file(self):
        resolver = PythonResolver()
        files = [("src/cocosearch/exceptions.py", "py")]
        index = resolver.build_index(files)

        assert index["cocosearch.exceptions"] == "src/cocosearch/exceptions.py"
        assert index["src.cocosearch.exceptions"] == "src/cocosearch/exceptions.py"

    def test_init_file_maps_to_package(self):
        resolver = PythonResolver()
        files = [("src/cocosearch/__init__.py", "py")]
        index = resolver.build_index(files)

        assert index["cocosearch"] == "src/cocosearch/__init__.py"
        assert index["src.cocosearch"] == "src/cocosearch/__init__.py"

    def test_top_level_file_without_src_prefix(self):
        resolver = PythonResolver()
        files = [("utils.py", "py")]
        index = resolver.build_index(files)

        assert index["utils"] == "utils.py"

    def test_skips_non_python_files(self):
        resolver = PythonResolver()
        files = [("src/main.go", "go"), ("README.md", "md")]
        index = resolver.build_index(files)

        assert index == {}

    def test_lib_prefix_stripped(self):
        resolver = PythonResolver()
        files = [("lib/mypackage/core.py", "py")]
        index = resolver.build_index(files)

        assert index["mypackage.core"] == "lib/mypackage/core.py"
        assert index["lib.mypackage.core"] == "lib/mypackage/core.py"

    def test_nested_init_file(self):
        resolver = PythonResolver()
        files = [("src/cocosearch/deps/__init__.py", "py")]
        index = resolver.build_index(files)

        assert index["cocosearch.deps"] == "src/cocosearch/deps/__init__.py"


# ============================================================================
# Tests: PythonResolver.resolve
# ============================================================================


class TestPythonResolverResolve:
    """Tests for PythonResolver.resolve()."""

    def test_resolves_absolute_import(self):
        resolver = PythonResolver()
        module_index = {
            "cocosearch.exceptions": "src/cocosearch/exceptions.py",
        }
        edge = _make_edge("src/app.py", "cocosearch.exceptions")
        assert resolver.resolve(edge, module_index) == "src/cocosearch/exceptions.py"

    def test_resolves_relative_import_single_dot(self):
        resolver = PythonResolver()
        module_index = {
            "cocosearch.deps.utils": "src/cocosearch/deps/utils.py",
        }
        edge = _make_edge("src/cocosearch/deps/extractor.py", ".utils")
        assert resolver.resolve(edge, module_index) == "src/cocosearch/deps/utils.py"

    def test_resolves_relative_import_double_dot(self):
        resolver = PythonResolver()
        module_index = {
            "cocosearch.deps.models": "src/cocosearch/deps/models.py",
        }
        edge = _make_edge("src/cocosearch/deps/extractors/python.py", "..models")
        assert resolver.resolve(edge, module_index) == "src/cocosearch/deps/models.py"

    def test_resolves_relative_import_dot_only(self):
        resolver = PythonResolver()
        module_index = {
            "cocosearch.deps": "src/cocosearch/deps/__init__.py",
        }
        edge = _make_edge("src/cocosearch/deps/extractor.py", ".")
        assert resolver.resolve(edge, module_index) == "src/cocosearch/deps/__init__.py"

    def test_unresolved_import_returns_none(self):
        resolver = PythonResolver()
        edge = _make_edge("src/app.py", "numpy")
        assert resolver.resolve(edge, {}) is None

    def test_no_module_in_metadata_returns_none(self):
        resolver = PythonResolver()
        edge = DependencyEdge(
            source_file="src/app.py",
            source_symbol=None,
            target_file=None,
            target_symbol=None,
            dep_type=DepType.IMPORT,
            metadata={"line": 1},
        )
        assert resolver.resolve(edge, {}) is None

    def test_resolves_submodule_to_parent(self):
        resolver = PythonResolver()
        module_index = {
            "cocosearch.deps.models": "src/cocosearch/deps/models.py",
        }
        edge = _make_edge("src/cli.py", "cocosearch.deps.models")
        assert resolver.resolve(edge, module_index) == "src/cocosearch/deps/models.py"


# ============================================================================
# Tests: JavaScriptResolver.build_index
# ============================================================================


class TestJavaScriptResolverBuildIndex:
    """Tests for JavaScriptResolver.build_index()."""

    def test_indexes_js_files(self):
        resolver = JavaScriptResolver()
        files = [("src/utils.js", "js"), ("src/app.tsx", "tsx")]
        index = resolver.build_index(files)

        assert "src/utils.js" in index
        assert "src/app.tsx" in index

    def test_skips_non_js_files(self):
        resolver = JavaScriptResolver()
        files = [("src/main.py", "py")]
        index = resolver.build_index(files)

        assert index == {}


# ============================================================================
# Tests: JavaScriptResolver.resolve
# ============================================================================


class TestJavaScriptResolverResolve:
    """Tests for JavaScriptResolver.resolve()."""

    def test_resolves_relative_import_with_extension(self):
        resolver = JavaScriptResolver()
        module_index = {"src/utils.js": "src/utils.js"}
        edge = _make_edge("src/app.js", "./utils.js")
        assert resolver.resolve(edge, module_index) == "src/utils.js"

    def test_resolves_relative_import_without_extension(self):
        resolver = JavaScriptResolver()
        module_index = {"src/utils.js": "src/utils.js"}
        edge = _make_edge("src/app.js", "./utils")
        assert resolver.resolve(edge, module_index) == "src/utils.js"

    def test_resolves_relative_import_ts_extension(self):
        resolver = JavaScriptResolver()
        module_index = {"src/utils.ts": "src/utils.ts"}
        edge = _make_edge("src/app.ts", "./utils")
        assert resolver.resolve(edge, module_index) == "src/utils.ts"

    def test_resolves_index_file(self):
        resolver = JavaScriptResolver()
        module_index = {"src/components/index.js": "src/components/index.js"}
        edge = _make_edge("src/app.js", "./components")
        assert resolver.resolve(edge, module_index) == "src/components/index.js"

    def test_resolves_index_ts_file(self):
        resolver = JavaScriptResolver()
        module_index = {"src/components/index.ts": "src/components/index.ts"}
        edge = _make_edge("src/app.ts", "./components")
        assert resolver.resolve(edge, module_index) == "src/components/index.ts"

    def test_resolves_parent_directory_import(self):
        resolver = JavaScriptResolver()
        module_index = {"src/helpers.js": "src/helpers.js"}
        edge = _make_edge("src/lib/app.js", "../helpers")
        assert resolver.resolve(edge, module_index) == "src/helpers.js"

    def test_bare_specifier_returns_none(self):
        resolver = JavaScriptResolver()
        module_index = {"src/utils.js": "src/utils.js"}
        edge = _make_edge("src/app.js", "react")
        assert resolver.resolve(edge, module_index) is None

    def test_scoped_package_returns_none(self):
        resolver = JavaScriptResolver()
        edge = _make_edge("src/app.js", "@mui/material")
        assert resolver.resolve(edge, {}) is None

    def test_unresolvable_relative_returns_none(self):
        resolver = JavaScriptResolver()
        edge = _make_edge("src/app.js", "./nonexistent")
        assert resolver.resolve(edge, {}) is None

    def test_no_module_in_metadata_returns_none(self):
        resolver = JavaScriptResolver()
        edge = DependencyEdge(
            source_file="src/app.js",
            source_symbol=None,
            target_file=None,
            target_symbol=None,
            dep_type=DepType.IMPORT,
            metadata={"line": 1},
        )
        assert resolver.resolve(edge, {}) is None


# ============================================================================
# Tests: GoResolver.build_index
# ============================================================================


class TestGoResolverBuildIndex:
    """Tests for GoResolver.build_index()."""

    def test_indexes_go_directories(self):
        resolver = GoResolver()
        files = [
            ("cmd/main.go", "go"),
            ("pkg/utils/helpers.go", "go"),
        ]
        index = resolver.build_index(files)

        assert "cmd" in index
        assert "pkg/utils" in index

    def test_skips_non_go_files(self):
        resolver = GoResolver()
        files = [("src/main.py", "py")]
        index = resolver.build_index(files)

        assert index == {}

    def test_first_file_wins_per_directory(self):
        resolver = GoResolver()
        files = [
            ("pkg/utils/a.go", "go"),
            ("pkg/utils/b.go", "go"),
        ]
        index = resolver.build_index(files)

        # First file in the directory should be stored
        assert index["pkg/utils"] == "pkg/utils/a.go"


# ============================================================================
# Tests: GoResolver.resolve
# ============================================================================


class TestGoResolverResolve:
    """Tests for GoResolver.resolve()."""

    def test_resolves_internal_package(self):
        resolver = GoResolver()
        module_index = {"pkg/utils": "pkg/utils/helpers.go"}
        edge = _make_edge("cmd/main.go", "github.com/user/repo/pkg/utils")
        assert resolver.resolve(edge, module_index) == "pkg/utils/helpers.go"

    def test_stdlib_import_returns_none(self):
        resolver = GoResolver()
        edge = _make_edge("cmd/main.go", "fmt")
        assert resolver.resolve(edge, {}) is None

    def test_external_package_returns_none(self):
        resolver = GoResolver()
        edge = _make_edge("cmd/main.go", "github.com/other/repo/pkg")
        assert resolver.resolve(edge, {}) is None

    def test_no_module_in_metadata_returns_none(self):
        resolver = GoResolver()
        edge = DependencyEdge(
            source_file="cmd/main.go",
            source_symbol=None,
            target_file=None,
            target_symbol=None,
            dep_type=DepType.IMPORT,
            metadata={"line": 1},
        )
        assert resolver.resolve(edge, {}) is None

    def test_resolves_short_internal_path(self):
        resolver = GoResolver()
        module_index = {"internal/auth": "internal/auth/auth.go"}
        edge = _make_edge("cmd/main.go", "myproject/internal/auth")
        assert resolver.resolve(edge, module_index) == "internal/auth/auth.go"


# ============================================================================
# Tests: Registry
# ============================================================================


class TestResolverRegistry:
    """Tests for the resolver registry."""

    def test_python_resolver_registered(self):
        assert isinstance(get_resolver("py"), PythonResolver)

    def test_js_resolver_registered(self):
        assert isinstance(get_resolver("js"), JavaScriptResolver)
        assert isinstance(get_resolver("ts"), JavaScriptResolver)
        assert isinstance(get_resolver("tsx"), JavaScriptResolver)
        assert isinstance(get_resolver("jsx"), JavaScriptResolver)

    def test_go_resolver_registered(self):
        assert isinstance(get_resolver("go"), GoResolver)

    def test_unknown_language_returns_none(self):
        assert get_resolver("rust") is None

    def test_get_resolvers_returns_all(self):
        resolvers = get_resolvers()
        assert "py" in resolvers
        assert "js" in resolvers
        assert "go" in resolvers

    def test_js_variants_share_instance(self):
        resolvers = get_resolvers()
        assert resolvers["js"] is resolvers["ts"]
        assert resolvers["js"] is resolvers["tsx"]
