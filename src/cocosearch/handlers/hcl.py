"""Handler for HCL (HashiCorp Configuration Language) files.

Provides language-aware chunking and metadata extraction for generic HCL files
used by HashiCorp tools (Packer, Vault, Nomad, etc.).

Handles .hcl file extension only. Terraform-specific files (.tf, .tfvars) are
handled by the Terraform grammar handler in handlers/grammars/terraform.py.
"""

import re

import cocoindex


class HclHandler:
    """Handler for generic HCL files."""

    EXTENSIONS = [".hcl"]

    SEPARATOR_SPEC = cocoindex.functions.CustomLanguageSpec(
        language_name="hcl",
        separators_regex=[
            # Level 1: Top-level block boundaries (any identifier at line start)
            r"\n[a-z_][a-z0-9_]* ",
            # Level 2: Blank lines between sections
            r"\n\n+",
            # Level 3: Single newlines
            r"\n",
            # Level 4: Whitespace (last resort)
            r" ",
        ],
        aliases=[],
    )

    # HCL line comment patterns (# or //)
    _COMMENT_LINE = re.compile(r"^\s*(?:#|//).*$", re.MULTILINE)

    # HCL block comment pattern (/* ... */)
    _DOC_COMMENT_LINE = re.compile(r"^\s*/?\*.*$", re.MULTILINE)

    # Match any HCL block: identifier [label1] [label2] {
    _BLOCK_RE = re.compile(
        r"^([a-z_][a-z0-9_]*)"
        r'(?:\s+"([^"]*)")?'  # optional first label
        r'(?:\s+"([^"]*)")?'  # optional second label
        r"\s*\{?",
    )

    # Match nested blocks (2+ space indented identifier + optional label + brace)
    _NESTED_BLOCK_RE = re.compile(
        r"^\s{2,}([a-z_][a-z0-9_]*)"
        r'(?:\s+"([^"]*)")?\s*\{',
    )

    # Match attribute assignments (identifier = value)
    _ATTRIBUTE_RE = re.compile(
        r"^\s*([a-z_][a-z0-9_]*)\s*=",
    )

    def extract_metadata(self, text: str) -> dict:
        """Extract metadata from HCL chunk.

        Matches any top-level HCL block keyword and extracts up to 2 quoted
        labels for building the dot-separated hierarchy. Also classifies
        nested blocks and attribute assignments.

        Args:
            text: The chunk text content.

        Returns:
            Dict with metadata fields:
            - block_type: HCL block type (e.g., "listener", "backend")
            - hierarchy: Dot-separated path (e.g., "listener.http")
            - language_id: "hcl"

        Example:
            Input: 'listener "http" {'
            Output: {
                "block_type": "listener",
                "hierarchy": "listener.http",
                "language_id": "hcl"
            }
        """
        stripped = self._strip_comments(text)

        # Check for top-level block (identifier at start of line + optional labels + brace)
        match = self._BLOCK_RE.match(stripped)
        if match and "{" in stripped.split("\n")[0]:
            block_type = match.group(1)
            label1 = match.group(2)
            label2 = match.group(3)

            parts = [block_type]
            if label1 is not None:
                parts.append(label1)
            if label2 is not None:
                parts.append(label2)
            hierarchy = ".".join(parts)

            return {
                "block_type": block_type,
                "hierarchy": hierarchy,
                "language_id": "hcl",
            }

        # Check for nested block (indented identifier + optional label + brace)
        nested_match = self._NESTED_BLOCK_RE.match(stripped)
        if nested_match:
            name = nested_match.group(1)
            label = nested_match.group(2)
            hierarchy = f"block.{name}.{label}" if label else f"block.{name}"
            return {
                "block_type": "block",
                "hierarchy": hierarchy,
                "language_id": "hcl",
            }

        # Check for attribute assignment (identifier = value)
        attr_match = self._ATTRIBUTE_RE.match(stripped)
        if attr_match:
            name = attr_match.group(1)
            return {
                "block_type": "attribute",
                "hierarchy": f"attribute.{name}",
                "language_id": "hcl",
            }

        return {"block_type": "", "hierarchy": "", "language_id": "hcl"}

    def _strip_comments(self, text: str) -> str:
        """Strip leading comments from chunk text, preserving indentation."""
        lines = text.lstrip("\n").split("\n")
        for i, line in enumerate(lines):
            if line.strip() and not self._COMMENT_LINE.match(line):
                if not self._DOC_COMMENT_LINE.match(line):
                    return "\n".join(lines[i:])
        return ""
