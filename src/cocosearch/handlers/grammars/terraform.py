"""Grammar handler for Terraform HCL files.

Provides domain-specific chunking and metadata extraction for Terraform
configuration files (.tf, .tfvars) with keyword-aware block boundaries.

Matches: *.tf, *.tfvars (path-based — these extensions are always Terraform)
"""

import fnmatch
import re

import cocoindex


class TerraformHandler:
    """Grammar handler for Terraform configuration files."""

    GRAMMAR_NAME = "terraform"
    BASE_LANGUAGE = "hcl"
    PATH_PATTERNS = ["**/*.tf", "**/*.tfvars"]

    SEPARATOR_SPEC = cocoindex.functions.CustomLanguageSpec(
        language_name="terraform",
        separators_regex=[
            # Level 1: Top-level Terraform block boundaries (12 keywords)
            r"\n(?:resource|data|variable|output|locals|module|provider|terraform|import|moved|removed|check) ",
            # Level 2: Nested block openings (2-space indent + identifier + optional label + brace)
            r'\n  [a-z_][a-z0-9_]*(?:\s+"[^"]*")?\s*\{',
            # Level 3: Blank lines
            r"\n\n+",
            # Level 4: Attribute assignments
            r"\n\s+[a-z_][a-z0-9_]*\s*=",
            # Level 5: Single newlines
            r"\n",
            # Level 6: Whitespace (last resort)
            r" ",
        ],
        aliases=["tf", "tfvars"],
    )

    # Line comment patterns (# or //)
    _COMMENT_LINE = re.compile(r"^\s*(?:#|//).*$", re.MULTILINE)

    # Block comment pattern (/* ... */ and continuation lines)
    _DOC_COMMENT_LINE = re.compile(r"^\s*/?\*.*$", re.MULTILINE)

    # 12 top-level Terraform block keywords
    _TERRAFORM_KEYWORDS = frozenset(
        {
            "resource",
            "data",
            "variable",
            "output",
            "locals",
            "module",
            "provider",
            "terraform",
            "import",
            "moved",
            "removed",
            "check",
        }
    )

    # Match top-level Terraform block with 0-2 quoted labels
    _BLOCK_RE = re.compile(
        r"^(resource|data|variable|output|locals|module|provider|terraform|import|moved|removed|check)"
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

    # Extension-based patterns for basename matching
    _BASENAME_PATTERNS = ["*.tf", "*.tfvars"]

    def matches(self, filepath: str, content: str | None = None) -> bool:
        """Check if file is a Terraform configuration file.

        Uses path-based matching only — .tf and .tfvars files are always
        Terraform. Content validation is not needed.

        Args:
            filepath: Relative file path within the project.
            content: Optional file content (not used for Terraform matching).

        Returns:
            True if this is a Terraform configuration file.
        """
        basename = filepath.rsplit("/", 1)[-1] if "/" in filepath else filepath
        for pattern in self._BASENAME_PATTERNS:
            if fnmatch.fnmatch(basename, pattern):
                return True
        return False

    def extract_metadata(self, text: str) -> dict:
        """Extract metadata from Terraform chunk.

        4-tier classification:
        1. Top-level blocks (12 Terraform keywords) with 0-2 labels
        2. Nested blocks (indented identifier + optional label + brace)
        3. Attributes (identifier = value)
        4. Unrecognized content (empty strings)

        Args:
            text: The chunk text content.

        Returns:
            Dict with metadata fields:
            - block_type: Terraform block keyword or "block"/"attribute"
            - hierarchy: Dot-separated path (e.g., "resource.aws_s3_bucket.data")
            - language_id: "terraform"

        Examples:
            Input: 'resource "aws_s3_bucket" "data" {'
            Output: {
                "block_type": "resource",
                "hierarchy": "resource.aws_s3_bucket.data",
                "language_id": "terraform"
            }
        """
        stripped = self._strip_comments(text)

        # Tier 1: Top-level Terraform block keywords
        match = self._BLOCK_RE.match(stripped)
        if match:
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
                "language_id": self.GRAMMAR_NAME,
            }

        # Tier 2: Nested blocks (lifecycle, provisioner, etc.)
        nested_match = self._NESTED_BLOCK_RE.match(stripped)
        if nested_match:
            name = nested_match.group(1)
            label = nested_match.group(2)
            hierarchy = f"block.{name}.{label}" if label else f"block.{name}"
            return {
                "block_type": "block",
                "hierarchy": hierarchy,
                "language_id": self.GRAMMAR_NAME,
            }

        # Tier 3: Attribute assignments
        attr_match = self._ATTRIBUTE_RE.match(stripped)
        if attr_match:
            name = attr_match.group(1)
            return {
                "block_type": "attribute",
                "hierarchy": f"attribute.{name}",
                "language_id": self.GRAMMAR_NAME,
            }

        # Tier 4: Unrecognized content
        return {
            "block_type": "",
            "hierarchy": "",
            "language_id": self.GRAMMAR_NAME,
        }

    def _strip_comments(self, text: str) -> str:
        """Strip leading comments from chunk text, preserving indentation."""
        lines = text.lstrip("\n").split("\n")
        for i, line in enumerate(lines):
            if line.strip() and not self._COMMENT_LINE.match(line):
                if not self._DOC_COMMENT_LINE.match(line):
                    return "\n".join(lines[i:])
        return ""
