"""Tests for cocosearch.deps.extractors.javascript module."""

from cocosearch.deps.extractors.javascript import JavaScriptImportExtractor
from cocosearch.deps.models import DepType


def _extract(code: str, file_path: str = "src/app.js"):
    """Helper to extract edges from JS/TS code."""
    extractor = JavaScriptImportExtractor()
    return extractor.extract(file_path, code)


# ============================================================================
# Tests: ES6 imports
# ============================================================================


class TestES6Imports:
    """Tests for ES6 import statement extraction."""

    def test_default_import(self):
        edges = _extract("import React from 'react';")
        assert len(edges) == 1
        assert edges[0].metadata["module"] == "react"
        assert edges[0].dep_type == DepType.IMPORT

    def test_named_import(self):
        edges = _extract("import { useState, useEffect } from 'react';")
        assert len(edges) == 1
        assert edges[0].metadata["module"] == "react"

    def test_namespace_import(self):
        edges = _extract("import * as utils from './utils';")
        assert len(edges) == 1
        assert edges[0].metadata["module"] == "./utils"

    def test_side_effect_import(self):
        edges = _extract("import './styles.css';")
        assert len(edges) == 1
        assert edges[0].metadata["module"] == "./styles.css"

    def test_relative_import(self):
        edges = _extract("import { helper } from './helpers';")
        assert len(edges) == 1
        assert edges[0].metadata["module"] == "./helpers"

    def test_parent_relative_import(self):
        edges = _extract("import { config } from '../config';")
        assert len(edges) == 1
        assert edges[0].metadata["module"] == "../config"

    def test_scoped_package(self):
        edges = _extract("import Button from '@mui/material/Button';")
        assert len(edges) == 1
        assert edges[0].metadata["module"] == "@mui/material/Button"

    def test_line_number_tracked(self):
        code = "\n\nimport os from 'os';\n"
        edges = _extract(code)
        assert len(edges) == 1
        assert edges[0].metadata["line"] == 3


# ============================================================================
# Tests: CommonJS require
# ============================================================================


class TestCommonJSRequire:
    """Tests for CommonJS require() extraction."""

    def test_require_string(self):
        edges = _extract("const fs = require('fs');")
        assert len(edges) == 1
        assert edges[0].metadata["module"] == "fs"
        assert edges[0].dep_type == DepType.IMPORT

    def test_require_relative(self):
        edges = _extract("const utils = require('./utils');")
        assert len(edges) == 1
        assert edges[0].metadata["module"] == "./utils"

    def test_require_destructured(self):
        edges = _extract("const { join } = require('path');")
        assert len(edges) == 1
        assert edges[0].metadata["module"] == "path"

    def test_require_inline(self):
        edges = _extract("const data = require('./data.json');")
        assert len(edges) == 1
        assert edges[0].metadata["module"] == "./data.json"


# ============================================================================
# Tests: Re-exports
# ============================================================================


class TestReExports:
    """Tests for re-export statement extraction."""

    def test_named_reexport(self):
        edges = _extract("export { foo } from './foo';")
        assert len(edges) == 1
        assert edges[0].metadata["module"] == "./foo"
        assert edges[0].dep_type == DepType.IMPORT

    def test_wildcard_reexport(self):
        edges = _extract("export * from './utils';")
        assert len(edges) == 1
        assert edges[0].metadata["module"] == "./utils"


# ============================================================================
# Tests: TypeScript specifics
# ============================================================================


class TestTypeScriptSpecifics:
    """Tests for TypeScript-specific import handling."""

    def test_import_type(self):
        edges = _extract(
            "import type { User } from './models';",
            file_path="src/app.ts",
        )
        assert len(edges) == 1
        assert edges[0].metadata["module"] == "./models"
        assert edges[0].metadata.get("import_kind") == "type"

    def test_regular_import_has_value_kind(self):
        edges = _extract(
            "import { helper } from './helpers';",
            file_path="src/app.ts",
        )
        assert len(edges) == 1
        assert edges[0].metadata.get("import_kind") == "value"

    def test_tsx_file_detection(self):
        edges = _extract(
            "import React from 'react';",
            file_path="src/App.tsx",
        )
        assert len(edges) == 1
        assert edges[0].metadata.get("import_kind") == "value"


# ============================================================================
# Tests: Multiple imports
# ============================================================================


class TestMultipleImports:
    """Tests for files with multiple import statements."""

    def test_multiple_es6_imports(self):
        code = """\
import React from 'react';
import { useState } from 'react';
import './styles.css';
"""
        edges = _extract(code)
        modules = [e.metadata["module"] for e in edges]
        assert "react" in modules
        assert "./styles.css" in modules

    def test_mixed_import_styles(self):
        code = """\
import { helper } from './helpers';
const fs = require('fs');
export { utils } from './utils';
"""
        edges = _extract(code)
        modules = [e.metadata["module"] for e in edges]
        assert "./helpers" in modules
        assert "fs" in modules
        assert "./utils" in modules


# ============================================================================
# Tests: Edge cases
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_file(self):
        edges = _extract("")
        assert edges == []

    def test_no_imports(self):
        edges = _extract("const x = 42;\nconsole.log(x);\n")
        assert edges == []

    def test_source_file_left_empty(self):
        edges = _extract("import React from 'react';")
        assert edges[0].source_file == ""

    def test_target_file_is_none(self):
        edges = _extract("import React from 'react';")
        assert edges[0].target_file is None

    def test_languages_set(self):
        extractor = JavaScriptImportExtractor()
        expected = {"js", "jsx", "mjs", "cjs", "ts", "tsx", "mts", "cts"}
        assert extractor.LANGUAGES == expected
