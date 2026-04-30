"""Handler for Groovy source files.

Provides language-aware chunking and metadata extraction for Groovy,
including classes, interfaces, traits, enums, and methods.

Handles .groovy and .gradle file extensions.
"""

import re

from cocoindex.ops.text import CustomLanguageConfig


class GroovyHandler:
    """Handler for Groovy source files."""

    EXTENSIONS = [".groovy", ".gradle"]

    SEPARATOR_SPEC = CustomLanguageConfig(
        language_name="groovy",
        separators_regex=[
            # Level 1: Top-level type boundaries (class, interface, trait, enum with optional modifiers)
            r"\n(?:abstract |final |public |private |protected |static )*(?:class |interface |trait |enum )",
            # Level 2: Method/field boundaries (def or typed method declarations)
            r"\n(?:public |private |protected |static |final |synchronized |abstract )*(?:def |void |int |long |double |float |boolean |String |Object |List |Map |Set )",
            # Level 3: Blank lines
            r"\n\n+",
            # Level 4: Single newlines
            r"\n",
            # Level 5: Whitespace (last resort)
            r" ",
        ],
        aliases=["gradle"],
    )

    # Comment patterns
    _COMMENT_LINE = re.compile(r"^\s*//.*$", re.MULTILINE)
    _DOC_COMMENT_LINE = re.compile(r"^\s*(?:/\*|\*).*$", re.MULTILINE)

    # Groovy definition patterns
    _DEF_RE = re.compile(
        r"^(?:"
        # class (with optional modifiers: abstract, final, public, private, protected, static)
        r"(?:abstract\s+|final\s+|public\s+|private\s+|protected\s+|static\s+)*class\s+([A-Za-z_][A-Za-z0-9_]*)"
        r"|"
        # interface (with optional modifiers: public, private, protected)
        r"(?:public\s+|private\s+|protected\s+)*interface\s+([A-Za-z_][A-Za-z0-9_]*)"
        r"|"
        # trait (with optional modifiers: public, private, protected, abstract)
        r"(?:public\s+|private\s+|protected\s+|abstract\s+)*trait\s+([A-Za-z_][A-Za-z0-9_]*)"
        r"|"
        # enum (with optional modifiers: public, private, protected)
        r"(?:public\s+|private\s+|protected\s+)*enum\s+([A-Za-z_][A-Za-z0-9_]*)"
        r"|"
        # def (with optional modifiers: public, private, protected, static, final, synchronized, abstract)
        r"(?:public\s+|private\s+|protected\s+|static\s+|final\s+|synchronized\s+|abstract\s+)*def\s+([A-Za-z_][A-Za-z0-9_]*)"
        r")"
    )

    def extract_metadata(self, text: str) -> dict:
        """Extract metadata from Groovy chunk.

        Args:
            text: The chunk text content.

        Returns:
            Dict with metadata fields:
            - block_type: "class", "interface", "trait", "enum", "function"
            - hierarchy: "type:name" (e.g. "class:MyService", "function:process")
            - language_id: "groovy"
        """
        stripped = self._strip_comments(text)
        match = self._DEF_RE.match(stripped)
        if not match:
            return {"block_type": "", "hierarchy": "", "language_id": "groovy"}

        # Groups: 1=class, 2=interface, 3=trait, 4=enum, 5=def
        if match.group(1):
            return {
                "block_type": "class",
                "hierarchy": f"class:{match.group(1)}",
                "language_id": "groovy",
            }
        elif match.group(2):
            return {
                "block_type": "interface",
                "hierarchy": f"interface:{match.group(2)}",
                "language_id": "groovy",
            }
        elif match.group(3):
            return {
                "block_type": "trait",
                "hierarchy": f"trait:{match.group(3)}",
                "language_id": "groovy",
            }
        elif match.group(4):
            return {
                "block_type": "enum",
                "hierarchy": f"enum:{match.group(4)}",
                "language_id": "groovy",
            }
        elif match.group(5):
            return {
                "block_type": "function",
                "hierarchy": f"function:{match.group(5)}",
                "language_id": "groovy",
            }

        return {"block_type": "", "hierarchy": "", "language_id": "groovy"}

    def _strip_comments(self, text: str) -> str:
        """Strip leading comments from chunk text.

        Handles // line comments and * lines from /** ... */ doc comments.

        Args:
            text: The chunk text content.

        Returns:
            Text from first non-comment, non-blank line onward
        """
        from cocosearch.handlers.utils import strip_leading_comments

        return strip_leading_comments(
            text, [self._COMMENT_LINE, self._DOC_COMMENT_LINE]
        )
