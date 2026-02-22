"""Terraform dependency extractor.

Extracts references from Terraform/HCL files:
- ``module`` block ``source`` attributes (local or registry modules)

Regex-based since HCL is not YAML.  Local sources (starting with
``./`` or ``../``) are resolvable; registry sources are external.
All edges use ``dep_type = DepType.REFERENCE``.
"""

import re

from cocosearch.deps.models import DependencyEdge, DepType

# Match the start of a module block: module "name" {
_MODULE_START_RE = re.compile(r'module\s+"([^"]+)"\s*\{')

# Match source = "value" inside a block
_SOURCE_RE = re.compile(r'source\s*=\s*"([^"]+)"')


def _extract_module_blocks(content: str) -> list[tuple[str, str]]:
    """Extract (module_name, block_body) pairs using brace-depth tracking.

    Handles nested braces correctly (e.g., tags = { ... } inside module blocks).
    """
    results = []
    for match in _MODULE_START_RE.finditer(content):
        module_name = match.group(1)
        # Start after the opening brace
        start = match.end()
        depth = 1
        i = start
        while i < len(content) and depth > 0:
            if content[i] == "{":
                depth += 1
            elif content[i] == "}":
                depth -= 1
            i += 1
        # Block body is between opening { and matching }
        block_body = content[start : i - 1] if depth == 0 else content[start:]
        results.append((module_name, block_body))
    return results


class TerraformExtractor:
    """Extractor for Terraform reference edges."""

    LANGUAGES: set[str] = {"terraform"}

    def extract(self, file_path: str, content: str) -> list[DependencyEdge]:
        if not content:
            return []

        edges: list[DependencyEdge] = []

        for module_name, block_body in _extract_module_blocks(content):
            source_match = _SOURCE_RE.search(block_body)
            if not source_match:
                continue

            source = source_match.group(1)
            is_local = source.startswith("./") or source.startswith("../")
            target_file = source if is_local else None
            # Strip leading ./ for local paths
            if target_file and target_file.startswith("./"):
                target_file = target_file[2:]

            edges.append(
                DependencyEdge(
                    source_file="",
                    source_symbol=module_name,
                    target_file=target_file,
                    target_symbol=None,
                    dep_type=DepType.REFERENCE,
                    metadata={
                        "kind": "module_source",
                        "value": source,
                    },
                )
            )

        return edges
