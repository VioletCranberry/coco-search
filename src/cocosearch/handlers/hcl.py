"""Handler for HCL/Terraform files.

Provides language-aware chunking and metadata extraction for HashiCorp
Configuration Language (HCL) files used by Terraform and other HashiCorp tools.

Handles .tf, .hcl, and .tfvars file extensions.
"""

import re

import cocoindex


class HclHandler:
    """Handler for HCL/Terraform files."""

    EXTENSIONS = [".tf", ".hcl", ".tfvars"]

    SEPARATOR_SPEC = cocoindex.functions.CustomLanguageSpec(
        language_name="hcl",
        separators_regex=[
            # Level 1: Top-level HCL block boundaries (12 keywords)
            r"\n(?:resource|data|variable|output|locals|module|provider|terraform|import|moved|removed|check) ",
            # Level 2: Blank lines between sections
            r"\n\n+",
            # Level 3: Single newlines
            r"\n",
            # Level 4: Whitespace (last resort)
            r" ",
        ],
        aliases=["tf", "tfvars"],
    )

    # HCL comment patterns (line comments: # or //, block comments: /* */)
    _COMMENT_LINE = re.compile(r"^\s*(?:#|//|/\*).*$", re.MULTILINE)

    # Match 12 top-level HCL block keywords with 0-2 quoted labels
    _BLOCK_RE = re.compile(
        r"^(resource|data|variable|output|locals|module|provider|terraform|import|moved|removed|check)"
        r'(?:\s+"([^"]*)")?'  # optional first label
        r'(?:\s+"([^"]*)")?'  # optional second label
        r"\s*\{?",
    )

    def extract_metadata(self, text: str) -> dict:
        """Extract metadata from HCL chunk.

        Matches the 12 top-level HCL block keywords and extracts up to 2 quoted
        labels for building the dot-separated hierarchy.

        Args:
            text: The chunk text content.

        Returns:
            Dict with metadata fields:
            - block_type: HCL block type (e.g., "resource", "variable")
            - hierarchy: Dot-separated path (e.g., "resource.aws_s3_bucket.data")
            - language_id: "hcl"

        Example:
            Input: 'resource "aws_s3_bucket" "data" {'
            Output: {
                "block_type": "resource",
                "hierarchy": "resource.aws_s3_bucket.data",
                "language_id": "hcl"
            }
        """
        stripped = self._strip_comments(text)
        match = self._BLOCK_RE.match(stripped)
        if not match:
            return {"block_type": "", "hierarchy": "", "language_id": "hcl"}

        block_type = match.group(1)
        label1 = match.group(2)
        label2 = match.group(3)

        # Build hierarchy from block_type + available labels
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

    def _strip_comments(self, text: str) -> str:
        """Strip leading comments from chunk text.

        Args:
            text: The chunk text content.

        Returns:
            Text from first non-comment, non-blank line onward
        """
        from cocosearch.handlers.utils import strip_leading_comments

        return strip_leading_comments(text, [self._COMMENT_LINE])
