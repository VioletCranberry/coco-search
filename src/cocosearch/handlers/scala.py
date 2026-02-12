"""Handler for Scala source files.

Provides language-aware chunking and metadata extraction for Scala,
including classes, case classes, traits, objects, methods, vals, vars,
and type aliases.

Handles .scala file extensions.
"""

import re

import cocoindex


class ScalaHandler:
    """Handler for Scala source files."""

    EXTENSIONS = [".scala"]

    SEPARATOR_SPEC = cocoindex.functions.CustomLanguageSpec(
        language_name="scala",
        separators_regex=[
            # Level 1: Top-level type boundaries (class, trait, object with optional modifiers)
            r"\n(?:abstract |sealed |case |final |private |protected |implicit )*(?:class |trait |object )",
            # Level 2: Method/def boundaries (with optional modifiers)
            r"\n(?:override |private |protected |final |implicit |lazy )*(?:def |val |var )",
            # Level 3: Blank lines
            r"\n\n+",
            # Level 4: Single newlines
            r"\n",
            # Level 5: Whitespace (last resort)
            r" ",
        ],
        aliases=["sc"],
    )

    # Comment patterns
    _COMMENT_LINE = re.compile(r"^\s*//.*$", re.MULTILINE)
    _DOC_COMMENT_LINE = re.compile(r"^\s*(?:/\*|\*).*$", re.MULTILINE)

    # Scala definition patterns
    _DEF_RE = re.compile(
        r"^(?:"
        # class (with optional modifiers: abstract, case, sealed, final, private, protected, implicit)
        r"(?:abstract\s+|sealed\s+|case\s+|final\s+|private\s+|protected\s+|implicit\s+)*class\s+([A-Za-z_][A-Za-z0-9_]*)"
        r"|"
        # trait (with optional modifiers: sealed, private, protected)
        r"(?:sealed\s+|private\s+|protected\s+)*trait\s+([A-Za-z_][A-Za-z0-9_]*)"
        r"|"
        # object (with optional modifiers: case, private, protected, implicit)
        r"(?:case\s+|private\s+|protected\s+|implicit\s+)*object\s+([A-Za-z_][A-Za-z0-9_]*)"
        r"|"
        # def (with optional modifiers: override, private, protected, final, implicit, lazy)
        r"(?:override\s+|private\s+|protected\s+|final\s+|implicit\s+|lazy\s+)*def\s+([A-Za-z_][A-Za-z0-9_]*)"
        r"|"
        # val
        r"(?:override\s+|private\s+|protected\s+|final\s+|implicit\s+|lazy\s+)*val\s+([A-Za-z_][A-Za-z0-9_]*)"
        r"|"
        # var
        r"(?:override\s+|private\s+|protected\s+)*var\s+([A-Za-z_][A-Za-z0-9_]*)"
        r"|"
        # type alias
        r"(?:override\s+|private\s+|protected\s+)*type\s+([A-Za-z_][A-Za-z0-9_]*)"
        r")"
    )

    def extract_metadata(self, text: str) -> dict:
        """Extract metadata from Scala chunk.

        Args:
            text: The chunk text content.

        Returns:
            Dict with metadata fields:
            - block_type: "class", "trait", "object", "function", "val", "var", "type"
            - hierarchy: "type:name" (e.g. "class:MyClass", "function:process")
            - language_id: "scala"
        """
        stripped = self._strip_comments(text)
        match = self._DEF_RE.match(stripped)
        if not match:
            return {"block_type": "", "hierarchy": "", "language_id": "scala"}

        # Groups: 1=class, 2=trait, 3=object, 4=def, 5=val, 6=var, 7=type
        if match.group(1):
            return {
                "block_type": "class",
                "hierarchy": f"class:{match.group(1)}",
                "language_id": "scala",
            }
        elif match.group(2):
            return {
                "block_type": "trait",
                "hierarchy": f"trait:{match.group(2)}",
                "language_id": "scala",
            }
        elif match.group(3):
            return {
                "block_type": "object",
                "hierarchy": f"object:{match.group(3)}",
                "language_id": "scala",
            }
        elif match.group(4):
            return {
                "block_type": "function",
                "hierarchy": f"function:{match.group(4)}",
                "language_id": "scala",
            }
        elif match.group(5):
            return {
                "block_type": "val",
                "hierarchy": f"val:{match.group(5)}",
                "language_id": "scala",
            }
        elif match.group(6):
            return {
                "block_type": "var",
                "hierarchy": f"var:{match.group(6)}",
                "language_id": "scala",
            }
        elif match.group(7):
            return {
                "block_type": "type",
                "hierarchy": f"type:{match.group(7)}",
                "language_id": "scala",
            }

        return {"block_type": "", "hierarchy": "", "language_id": "scala"}

    def _strip_comments(self, text: str) -> str:
        """Strip leading comments from chunk text.

        Handles // line comments and * lines from /** ... */ doc comments.

        Args:
            text: The chunk text content.

        Returns:
            Text from first non-comment, non-blank line onward
        """
        lines = text.lstrip().split("\n")
        for i, line in enumerate(lines):
            stripped = line.strip()
            if (
                stripped
                and not self._COMMENT_LINE.match(line)
                and not self._DOC_COMMENT_LINE.match(line)
            ):
                return "\n".join(lines[i:])
        return ""
