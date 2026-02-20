"""Template for creating new language handlers.

Copy this file to <language>.py and implement the TODOs.

Example: To add support for YAML files, copy this to yaml.py and:
1. Replace <LANGUAGE> with "YAML"
2. Set EXTENSIONS to ['.yaml', '.yml']
3. Define SEPARATOR_SPEC with appropriate regex separators
4. Implement _extract_metadata() with YAML-specific logic

For domain-specific schemas within a language (e.g., GitHub Actions is
a grammar of YAML), see grammars/_template.py instead.

For full documentation, see handlers/README.md
"""

import re

import cocoindex


class TemplateHandler:
    """Handler for <LANGUAGE> files.

    TODO: Replace <LANGUAGE> with language name (e.g., "YAML", "JSON", "Makefile").
    """

    # TODO: List file extensions this handler manages (with leading dot)
    EXTENSIONS = [".example"]

    # TODO: Define CustomLanguageSpec with hierarchical separators
    # Separators are tried in order - earlier separators have higher priority
    # Use standard Rust regex syntax (no lookaheads, lookbehinds, backreferences)
    # See: https://docs.rs/regex/latest/regex/#syntax
    SEPARATOR_SPEC = cocoindex.functions.CustomLanguageSpec(
        language_name="example",
        separators_regex=[
            # Level 1: Top-level structural boundaries (functions, classes, blocks)
            r"\nfunction ",
            # Level 2: Blank lines (logical section separators)
            r"\n\n+",
            # Level 3: Single newlines
            r"\n",
            # Level 4: Whitespace (last resort)
            r" ",
        ],
        # Aliases: alternative names that map to this language
        # Example: ["yml"] for YAML, ["tf", "tfvars"] for HCL
        aliases=[],
    )

    # TODO: Define regex patterns for metadata extraction
    # Example: Match block types, function names, section headers
    _BLOCK_RE = re.compile(r"^some_pattern")
    _COMMENT_LINE = re.compile(r"^\s*#.*$", re.MULTILINE)

    def extract_metadata(self, text: str) -> dict:
        """Extract metadata from <LANGUAGE> chunk.

        TODO: Implement metadata extraction logic:
        1. Strip leading comments (optional)
        2. Match patterns to identify block type
        3. Extract hierarchy information (e.g., "function:deploy", "class.method")
        4. Return dict with block_type, hierarchy, language_id

        Args:
            text: The chunk text content.

        Returns:
            Dict with metadata fields:
            - block_type: Type of block (e.g., "function", "class", "resource")
            - hierarchy: Dot or colon-separated hierarchy (e.g., "function:deploy")
            - language_id: Language identifier (e.g., "yaml", "json")

        Example for HCL:
            block_type="resource"
            hierarchy="resource.aws_s3_bucket.data"
            language_id="hcl"

        Example for Dockerfile:
            block_type="FROM"
            hierarchy="stage:builder"
            language_id="dockerfile"

        Example for Bash:
            block_type="function"
            hierarchy="function:deploy"
            language_id="bash"
        """
        # Strip leading comments (optional but recommended)
        stripped = self._strip_comments(text)

        # Match patterns
        match = self._BLOCK_RE.match(stripped)
        if not match:
            # Return empty metadata if no match
            return {"block_type": "", "hierarchy": "", "language_id": "example"}

        # Extract fields from regex groups
        block_type = match.group(1)
        # Build hierarchy from matched groups
        hierarchy = block_type  # TODO: Construct hierarchy

        return {
            "block_type": block_type,
            "hierarchy": hierarchy,
            "language_id": "example",  # TODO: Replace with actual language
        }

    def _strip_comments(self, text: str) -> str:
        """Strip leading comments from chunk text."""
        from cocosearch.handlers.utils import strip_leading_comments

        return strip_leading_comments(text, [self._COMMENT_LINE])


# ---------------------------------------------------------------------------
# Helper patterns from RESEARCH.md
# ---------------------------------------------------------------------------
#
# HCL example:
#   _BLOCK_RE = re.compile(
#       r"^(resource|data|variable|output|locals|module|provider|terraform)"
#       r'(?:\s+"([^"]*)")?'  # optional first label
#       r'(?:\s+"([^"]*)")?'  # optional second label
#       r"\s*\{?",
#   )
#
# Dockerfile example:
#   _INSTRUCTION_RE = re.compile(
#       r"^(FROM|RUN|CMD|LABEL|EXPOSE|ENV|ADD|COPY|ENTRYPOINT|VOLUME|USER|WORKDIR|ARG)\b"
#   )
#   _FROM_RE = re.compile(
#       r"^FROM\s+(?:--platform=\S+\s+)?(\S+)(?:\s+[Aa][Ss]\s+(\S+))?"
#   )
#
# Bash example:
#   _FUNCTION_RE = re.compile(
#       r"^(?:function\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:\(\s*\))?\s*\{?"
#       r"|([a-zA-Z_][a-zA-Z0-9_]*)\s*\(\s*\)\s*\{?)"
#   )
#
# ---------------------------------------------------------------------------
