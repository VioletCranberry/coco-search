"""Tests for the Python import dependency extractor."""

import pytest

from cocosearch.deps.extractors.python import PythonImportExtractor
from cocosearch.deps.models import DepType


@pytest.fixture
def extractor():
    """Create a PythonImportExtractor instance."""
    return PythonImportExtractor()


# ============================================================================
# Tests: LANGUAGES attribute
# ============================================================================


class TestLanguages:
    """Tests for PythonImportExtractor.LANGUAGES."""

    def test_languages_contains_python(self, extractor):
        """LANGUAGES should include 'python'."""
        assert "py" in extractor.LANGUAGES


# ============================================================================
# Tests: import statement (no from)
# ============================================================================


class TestImportStatement:
    """Tests for plain 'import X' statements."""

    def test_import_simple_module(self, extractor):
        """import os -> edge with module='os', no target_symbol."""
        edges = extractor.extract("app.py", "import os\n")
        assert len(edges) == 1
        edge = edges[0]
        assert edge.dep_type == DepType.IMPORT
        assert edge.source_file == ""
        assert edge.source_symbol is None
        assert edge.target_symbol is None
        assert edge.metadata["module"] == "os"
        assert edge.metadata["line"] == 1

    def test_import_with_alias(self, extractor):
        """import numpy as np -> edge with alias='np'."""
        edges = extractor.extract("app.py", "import numpy as np\n")
        assert len(edges) == 1
        edge = edges[0]
        assert edge.metadata["module"] == "numpy"
        assert edge.metadata["alias"] == "np"
        assert edge.metadata["line"] == 1

    def test_import_dotted_module(self, extractor):
        """import os.path -> edge with module='os.path'."""
        edges = extractor.extract("app.py", "import os.path\n")
        assert len(edges) == 1
        assert edges[0].metadata["module"] == "os.path"


# ============================================================================
# Tests: from ... import statement
# ============================================================================


class TestFromImportStatement:
    """Tests for 'from X import Y' statements."""

    def test_from_import_single_name(self, extractor):
        """from os.path import join -> target_symbol='join'."""
        edges = extractor.extract("app.py", "from os.path import join\n")
        assert len(edges) == 1
        edge = edges[0]
        assert edge.dep_type == DepType.IMPORT
        assert edge.source_file == ""
        assert edge.source_symbol is None
        assert edge.target_symbol == "join"
        assert edge.metadata["module"] == "os.path"
        assert edge.metadata["line"] == 1

    def test_from_import_multiple_names(self, extractor):
        """from os.path import join, exists, dirname -> 3 edges."""
        code = "from os.path import join, exists, dirname\n"
        edges = extractor.extract("app.py", code)
        assert len(edges) == 3
        symbols = {e.target_symbol for e in edges}
        assert symbols == {"join", "exists", "dirname"}
        for edge in edges:
            assert edge.metadata["module"] == "os.path"
            assert edge.metadata["line"] == 1

    def test_from_import_with_alias(self, extractor):
        """from collections import OrderedDict as OD -> alias in metadata."""
        code = "from collections import OrderedDict as OD\n"
        edges = extractor.extract("app.py", code)
        assert len(edges) == 1
        edge = edges[0]
        assert edge.target_symbol == "OrderedDict"
        assert edge.metadata["module"] == "collections"
        assert edge.metadata["alias"] == "OD"

    def test_from_import_wildcard(self, extractor):
        """from os.path import * -> target_symbol='*'."""
        edges = extractor.extract("app.py", "from os.path import *\n")
        assert len(edges) == 1
        assert edges[0].target_symbol == "*"
        assert edges[0].metadata["module"] == "os.path"

    def test_from_relative_import(self, extractor):
        """from . import utils -> module starts with dot."""
        edges = extractor.extract("app.py", "from . import utils\n")
        assert len(edges) == 1
        assert edges[0].target_symbol == "utils"
        assert edges[0].metadata["module"] == "."

    def test_from_relative_dotted_import(self, extractor):
        """from ..models import User -> module is '..models'."""
        edges = extractor.extract("app.py", "from ..models import User\n")
        assert len(edges) == 1
        assert edges[0].target_symbol == "User"
        assert edges[0].metadata["module"] == "..models"


# ============================================================================
# Tests: line numbers
# ============================================================================


class TestLineNumbers:
    """Tests for correct line number tracking."""

    def test_line_numbers_multiple_imports(self, extractor):
        """Line numbers should match the actual source lines."""
        code = "import os\nimport sys\nfrom pathlib import Path\n"
        edges = extractor.extract("app.py", code)
        assert len(edges) == 3
        lines = sorted(e.metadata["line"] for e in edges)
        assert lines == [1, 2, 3]


# ============================================================================
# Tests: empty / no-import cases
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_file(self, extractor):
        """Empty file returns empty list."""
        assert extractor.extract("app.py", "") == []

    def test_no_imports(self, extractor):
        """File with no imports returns empty list."""
        code = "x = 1\nprint(x)\n"
        assert extractor.extract("app.py", code) == []


# ============================================================================
# Tests: multiple imports in one file
# ============================================================================


class TestMultipleImports:
    """Tests for files with multiple import statements."""

    def test_mixed_import_forms(self, extractor):
        """Mix of import and from-import in one file."""
        code = (
            "import os\n"
            "import json\n"
            "from pathlib import Path\n"
            "from collections import OrderedDict as OD\n"
        )
        edges = extractor.extract("app.py", code)
        assert len(edges) == 4

        # Check all dep_type and source_file
        for edge in edges:
            assert edge.dep_type == DepType.IMPORT
            assert edge.source_file == ""
            assert edge.source_symbol is None

    def test_from_import_expands_names(self, extractor):
        """from os.path import join, exists produces 2 edges + import os = 3."""
        code = "import os\nfrom os.path import join, exists\n"
        edges = extractor.extract("app.py", code)
        assert len(edges) == 3


# ============================================================================
# Tests: common edge fields
# ============================================================================


class TestEdgeFields:
    """Tests for DependencyEdge field values."""

    def test_source_file_is_empty(self, extractor):
        """source_file should be empty string (filled by orchestrator)."""
        edges = extractor.extract("app.py", "import os\n")
        assert edges[0].source_file == ""

    def test_target_file_is_none(self, extractor):
        """target_file should be None (resolved later)."""
        edges = extractor.extract("app.py", "import os\n")
        assert edges[0].target_file is None


# ============================================================================
# Tests: nested imports (try/except, TYPE_CHECKING, functions, if blocks)
# ============================================================================


class TestNestedImports:
    """Tests for imports nested inside blocks (not at module top level)."""

    def test_import_inside_try_except(self, extractor):
        """Imports inside try/except should be found."""
        code = (
            "try:\n"
            "    from fast import X\n"
            "except ImportError:\n"
            "    from slow import X\n"
        )
        edges = extractor.extract("app.py", code)
        assert len(edges) == 2
        modules = {e.metadata["module"] for e in edges}
        assert modules == {"fast", "slow"}

    def test_import_inside_if_type_checking(self, extractor):
        """Imports inside if TYPE_CHECKING: should be found."""
        code = (
            "from typing import TYPE_CHECKING\n"
            "\n"
            "if TYPE_CHECKING:\n"
            "    from rich import Table\n"
            "    from pathlib import Path\n"
        )
        edges = extractor.extract("app.py", code)
        # 3 edges: TYPE_CHECKING + Table + Path
        assert len(edges) == 3
        symbols = {e.target_symbol for e in edges if e.target_symbol}
        assert "Table" in symbols
        assert "Path" in symbols

    def test_import_inside_function(self, extractor):
        """Lazy imports inside function bodies should be found."""
        code = (
            "def load_heavy():\n"
            "    import numpy as np\n"
            "    from pandas import DataFrame\n"
            "    return np, DataFrame\n"
        )
        edges = extractor.extract("app.py", code)
        assert len(edges) == 2
        modules = {e.metadata["module"] for e in edges}
        assert "numpy" in modules
        assert "pandas" in modules

    def test_import_inside_if_block(self, extractor):
        """Conditional imports inside if blocks should be found."""
        code = (
            "import sys\n"
            "if sys.version_info >= (3, 11):\n"
            "    from tomllib import loads\n"
            "else:\n"
            "    from tomli import loads\n"
        )
        edges = extractor.extract("app.py", code)
        assert len(edges) == 3  # sys + tomllib.loads + tomli.loads
        modules = {e.metadata["module"] for e in edges}
        assert "sys" in modules
        assert "tomllib" in modules
        assert "tomli" in modules
