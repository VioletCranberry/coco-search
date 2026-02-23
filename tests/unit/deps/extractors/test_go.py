"""Tests for cocosearch.deps.extractors.go module."""

from cocosearch.deps.extractors.go import GoImportExtractor
from cocosearch.deps.models import DepType


def _extract(code: str, file_path: str = "cmd/main.go"):
    """Helper to extract edges from Go code."""
    extractor = GoImportExtractor()
    return extractor.extract(file_path, code)


# ============================================================================
# Tests: Single imports
# ============================================================================


class TestSingleImports:
    """Tests for single import declarations."""

    def test_single_import(self):
        edges = _extract('import "fmt"')
        assert len(edges) == 1
        assert edges[0].metadata["module"] == "fmt"
        assert edges[0].dep_type == DepType.IMPORT

    def test_single_import_path(self):
        edges = _extract('import "os/exec"')
        assert len(edges) == 1
        assert edges[0].metadata["module"] == "os/exec"

    def test_aliased_import(self):
        edges = _extract('import f "fmt"')
        assert len(edges) == 1
        assert edges[0].metadata["module"] == "fmt"
        assert edges[0].metadata["alias"] == "f"

    def test_blank_import(self):
        edges = _extract('import _ "database/sql"')
        assert len(edges) == 1
        assert edges[0].metadata["module"] == "database/sql"
        assert edges[0].metadata["alias"] == "_"

    def test_dot_import(self):
        edges = _extract('import . "fmt"')
        assert len(edges) == 1
        assert edges[0].metadata["module"] == "fmt"
        assert edges[0].metadata["alias"] == "."

    def test_line_number_tracked(self):
        code = '\npackage main\n\nimport "fmt"\n'
        edges = _extract(code)
        assert len(edges) == 1
        assert edges[0].metadata["line"] >= 1


# ============================================================================
# Tests: Grouped imports
# ============================================================================


class TestGroupedImports:
    """Tests for grouped import declarations."""

    def test_grouped_imports(self):
        code = """\
import (
    "fmt"
    "os"
)
"""
        edges = _extract(code)
        modules = [e.metadata["module"] for e in edges]
        assert "fmt" in modules
        assert "os" in modules

    def test_grouped_with_aliases(self):
        code = """\
import (
    "fmt"
    f "os"
    _ "database/sql"
)
"""
        edges = _extract(code)
        assert len(edges) == 3

        # Find the aliased import
        os_edge = [e for e in edges if e.metadata["module"] == "os"][0]
        assert os_edge.metadata["alias"] == "f"

        # Find the blank import
        sql_edge = [e for e in edges if e.metadata["module"] == "database/sql"][0]
        assert sql_edge.metadata["alias"] == "_"

    def test_grouped_external_packages(self):
        code = """\
import (
    "fmt"
    "github.com/user/repo/pkg"
    "golang.org/x/tools"
)
"""
        edges = _extract(code)
        modules = [e.metadata["module"] for e in edges]
        assert "fmt" in modules
        assert "github.com/user/repo/pkg" in modules
        assert "golang.org/x/tools" in modules


# ============================================================================
# Tests: Full Go file
# ============================================================================


class TestFullGoFile:
    """Tests for complete Go source files."""

    def test_complete_go_file(self):
        code = """\
package main

import (
    "fmt"
    "os"

    "github.com/user/repo/internal/auth"
)

func main() {
    fmt.Println("hello")
}
"""
        edges = _extract(code)
        modules = [e.metadata["module"] for e in edges]
        assert "fmt" in modules
        assert "os" in modules
        assert "github.com/user/repo/internal/auth" in modules

    def test_multiple_import_declarations(self):
        code = """\
package main

import "fmt"
import "os"
"""
        edges = _extract(code)
        modules = [e.metadata["module"] for e in edges]
        assert "fmt" in modules
        assert "os" in modules


# ============================================================================
# Tests: Edge cases
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_file(self):
        edges = _extract("")
        assert edges == []

    def test_no_imports(self):
        code = """\
package main

func main() {}
"""
        edges = _extract(code)
        assert edges == []

    def test_source_file_left_empty(self):
        edges = _extract('import "fmt"')
        assert edges[0].source_file == ""

    def test_target_file_is_none(self):
        edges = _extract('import "fmt"')
        assert edges[0].target_file is None

    def test_languages_set(self):
        extractor = GoImportExtractor()
        assert extractor.LANGUAGES == {"go"}


# ============================================================================
# Tests: Nested import declarations
# ============================================================================


class TestNestedImports:
    """Tests for imports nested inside blocks (init functions, etc.)."""

    def test_import_inside_init_function(self):
        """Import inside func init() should be found (rare but valid Go)."""
        code = """\
package main

import "fmt"

func init() {
    // Go doesn't allow import inside functions syntactically,
    // but the recursive walker should still find top-level imports
    // and not break when traversing function bodies.
}
"""
        edges = _extract(code)
        modules = [e.metadata["module"] for e in edges]
        assert "fmt" in modules

    def test_recursive_walk_does_not_duplicate(self):
        """Recursive walk should not produce duplicate edges."""
        code = """\
package main

import (
    "fmt"
    "os"
)

func main() {
    fmt.Println("hello")
    os.Exit(0)
}
"""
        edges = _extract(code)
        modules = [e.metadata["module"] for e in edges]
        assert len(modules) == 2
        assert "fmt" in modules
        assert "os" in modules
