"""Markdown documentation dependency extractor.

Extracts references from Markdown/MDX files to source code files,
creating ``reference`` edges that connect documentation to the code it describes.

Detection sources (in priority order):
1. YAML frontmatter ``depends:`` field (authoritative)
2. Inline links to local files (``[text](path/to/file.py)``)
3. Inline code spans that look like paths (````src/cli.py````)
4. Paths in fenced code block comments
"""

import re

import yaml
from tree_sitter import Parser
from tree_sitter_language_pack import get_parser

from cocosearch.deps.models import DependencyEdge, DepType

# Module-level parser caches (lazy, one-time setup)
_md_parser: Parser | None = None
_inline_parser: Parser | None = None

# Pattern for path-like strings in code blocks (comment lines)
_CODE_BLOCK_PATH_RE = re.compile(
    r"""(?:^|\s)                   # start of line or whitespace
    (?:[#/]+\s*)?                  # optional comment prefix (# or //)
    (                              # capture the path
        (?:[\w.~-]+/)+             # one or more directory segments with /
        [\w.-]+                    # filename
        (?:\.\w+)?                 # optional extension
    )""",
    re.VERBOSE,
)

# Extensions that indicate a file path (not exhaustive, but covers common cases)
_PATH_EXTENSIONS = frozenset(
    {
        "py",
        "js",
        "jsx",
        "ts",
        "tsx",
        "go",
        "rs",
        "java",
        "rb",
        "scala",
        "sh",
        "bash",
        "zsh",
        "yaml",
        "yml",
        "json",
        "toml",
        "cfg",
        "ini",
        "md",
        "mdx",
        "txt",
        "html",
        "css",
        "scss",
        "sql",
        "graphql",
        "tf",
        "hcl",
        "dockerfile",
        "makefile",
        "c",
        "cpp",
        "h",
        "hpp",
        "swift",
        "kt",
        "lua",
        "r",
        "pl",
        "ex",
        "exs",
        "erl",
        "hs",
        "vue",
        "svelte",
        "astro",
        "prisma",
        "proto",
    }
)


def _get_md_parser() -> Parser:
    """Get or create the cached Markdown tree-sitter parser."""
    global _md_parser
    if _md_parser is None:
        _md_parser = get_parser("markdown")
    return _md_parser


def _get_inline_parser() -> Parser:
    """Get or create the cached Markdown inline tree-sitter parser."""
    global _inline_parser
    if _inline_parser is None:
        _inline_parser = get_parser("markdown_inline")
    return _inline_parser


def _node_text(source: bytes, node) -> str:
    """Extract text content from a tree-sitter node."""
    return source[node.start_byte : node.end_byte].decode("utf8")


def _looks_like_path(text: str) -> bool:
    """Heuristic: does this inline code span look like a file/directory path?

    Must contain ``/`` or a dot with a known extension. Rejects strings
    that look like code expressions, CLI commands, or are too long.
    """
    if len(text) > 200:
        return False

    # Reject things that are clearly not paths
    if any(
        ch in text
        for ch in ("(", ")", "=", "+", "{", "}", "[", "]", ";", "|", ">", "<")
    ):
        return False

    # Reject if it starts with a dash (CLI flag)
    if text.startswith("-"):
        return False

    # Reject if it contains spaces (likely a command or sentence)
    if " " in text:
        return False

    # Must contain / (directory separator) or have a known file extension
    if "/" in text:
        return True

    # Check for known file extension
    if "." in text:
        ext = text.rsplit(".", 1)[-1].lower()
        return ext in _PATH_EXTENSIONS

    return False


class MarkdownDocExtractor:
    """Extractor for documentation reference edges from Markdown/MDX files.

    Parses Markdown files using tree-sitter and extracts references to
    source code files. Creates ``reference`` edges with metadata indicating
    the source context (frontmatter, link, inline code, code block).
    """

    LANGUAGES: set[str] = {"md", "mdx"}

    def extract(self, file_path: str, content: str) -> list[DependencyEdge]:
        """Extract documentation reference edges from a Markdown file.

        Args:
            file_path: Relative path to the markdown file (unused here;
                source_file is set by the orchestrator).
            content: Full text content of the Markdown file.

        Returns:
            List of DependencyEdge instances, one per referenced file/directory.
        """
        if not content:
            return []

        parser = _get_md_parser()
        source = content.encode("utf8")
        tree = parser.parse(source)

        edges: list[DependencyEdge] = []
        self._walk_blocks(source, tree.root_node, edges)
        return edges

    def _walk_blocks(self, source: bytes, node, edges: list[DependencyEdge]) -> None:
        """Recursively walk block-level nodes to find extractable content."""
        for child in node.children:
            if child.type == "minus_metadata":
                edges.extend(self._extract_frontmatter(source, child))
            elif child.type == "fenced_code_block":
                edges.extend(self._extract_from_code_block(source, child))
            elif child.type in ("paragraph", "atx_heading", "list", "list_item"):
                edges.extend(self._extract_from_inline_content(source, child))
            elif child.type in ("section", "document"):
                self._walk_blocks(source, child, edges)

    # ------------------------------------------------------------------
    # Frontmatter: depends: field
    # ------------------------------------------------------------------

    def _extract_frontmatter(self, source: bytes, node) -> list[DependencyEdge]:
        """Extract references from YAML frontmatter ``depends:`` field."""
        text = _node_text(source, node)
        # Strip --- delimiters
        lines = text.strip().split("\n")
        if len(lines) < 2:
            return []
        yaml_text = (
            "\n".join(lines[1:-1])
            if lines[-1].strip() == "---"
            else "\n".join(lines[1:])
        )

        try:
            data = yaml.safe_load(yaml_text)
        except yaml.YAMLError:
            return []

        if not isinstance(data, dict):
            return []

        depends = data.get("depends")
        if not isinstance(depends, list):
            return []

        line = node.start_point.row + 1
        edges: list[DependencyEdge] = []
        for path in depends:
            if not isinstance(path, str) or not path.strip():
                continue
            path = path.strip()
            edges.append(
                DependencyEdge(
                    source_file="",
                    source_symbol=None,
                    target_file=None,
                    target_symbol=None,
                    dep_type=DepType.REFERENCE,
                    metadata={
                        "kind": "doc_frontmatter",
                        "module": path,
                        "line": line,
                        "is_directory": path.endswith("/"),
                    },
                )
            )

        return edges

    # ------------------------------------------------------------------
    # Inline content: links and code spans
    # ------------------------------------------------------------------

    def _extract_from_inline_content(self, source: bytes, node) -> list[DependencyEdge]:
        """Extract references from inline content (links and code spans).

        Walks descendant nodes to find inline content, then parses with
        the markdown_inline parser.
        """
        edges: list[DependencyEdge] = []
        self._walk_for_inline(source, node, edges)
        return edges

    def _walk_for_inline(
        self, source: bytes, node, edges: list[DependencyEdge]
    ) -> None:
        """Recursively walk nodes to find inline content."""
        if node.type == "inline":
            inline_bytes = source[node.start_byte : node.end_byte]
            line_offset = node.start_point.row
            inline_parser = _get_inline_parser()
            inline_tree = inline_parser.parse(inline_bytes)
            edges.extend(self._extract_links(inline_tree, inline_bytes, line_offset))
            edges.extend(
                self._extract_code_spans(inline_tree, inline_bytes, line_offset)
            )
        else:
            for child in node.children:
                self._walk_for_inline(source, child, edges)

    def _extract_links(
        self, inline_tree, inline_bytes: bytes, line_offset: int
    ) -> list[DependencyEdge]:
        """Extract local file references from inline links."""
        edges: list[DependencyEdge] = []
        stack = [inline_tree.root_node]

        while stack:
            n = stack.pop()
            if n.type == "inline_link":
                dest = self._find_link_destination(n, inline_bytes)
                if dest is not None:
                    line = line_offset + n.start_point.row + 1
                    edges.append(
                        DependencyEdge(
                            source_file="",
                            source_symbol=None,
                            target_file=None,
                            target_symbol=None,
                            dep_type=DepType.REFERENCE,
                            metadata={
                                "kind": "doc_link",
                                "module": dest,
                                "line": line,
                            },
                        )
                    )
            else:
                stack.extend(n.children)

        return edges

    def _find_link_destination(self, link_node, inline_bytes: bytes) -> str | None:
        """Extract and validate a link destination from an inline_link node."""
        for child in link_node.children:
            if child.type == "link_destination":
                dest = _node_text(inline_bytes, child)
                return self._validate_link_path(dest)
        return None

    @staticmethod
    def _validate_link_path(dest: str) -> str | None:
        """Validate and clean a link destination, returning None for non-local paths."""
        # Skip URLs
        if "://" in dest:
            return None
        # Skip mailto
        if dest.startswith("mailto:"):
            return None
        # Skip pure anchors
        if dest.startswith("#"):
            return None
        # Strip fragment
        if "#" in dest:
            dest = dest.split("#", 1)[0]
        # After stripping fragment, skip if empty
        if not dest:
            return None
        return dest

    def _extract_code_spans(
        self, inline_tree, inline_bytes: bytes, line_offset: int
    ) -> list[DependencyEdge]:
        """Extract path-like references from inline code spans."""
        edges: list[DependencyEdge] = []
        stack = [inline_tree.root_node]

        while stack:
            n = stack.pop()
            if n.type == "code_span":
                text = _node_text(inline_bytes, n)
                # Strip backticks
                if text.startswith("`") and text.endswith("`"):
                    text = text[1:-1]
                if _looks_like_path(text):
                    line = line_offset + n.start_point.row + 1
                    edges.append(
                        DependencyEdge(
                            source_file="",
                            source_symbol=None,
                            target_file=None,
                            target_symbol=None,
                            dep_type=DepType.REFERENCE,
                            metadata={
                                "kind": "doc_inline_code",
                                "module": text,
                                "line": line,
                            },
                        )
                    )
            else:
                stack.extend(n.children)

        return edges

    # ------------------------------------------------------------------
    # Code blocks: paths in comments
    # ------------------------------------------------------------------

    def _extract_from_code_block(self, source: bytes, node) -> list[DependencyEdge]:
        """Extract path references from fenced code block content."""
        edges: list[DependencyEdge] = []

        for child in node.children:
            if child.type == "code_fence_content":
                text = _node_text(source, child)
                line_start = child.start_point.row + 1

                for i, line in enumerate(text.split("\n")):
                    stripped = line.strip()
                    # Focus on comment lines to reduce noise
                    if not stripped or not (
                        stripped.startswith("#")
                        or stripped.startswith("//")
                        or stripped.startswith("--")
                    ):
                        continue

                    for match in _CODE_BLOCK_PATH_RE.finditer(line):
                        path = match.group(1)
                        # Verify it has a known extension or looks like a directory path
                        if "." in path.rsplit("/", 1)[-1]:
                            ext = path.rsplit(".", 1)[-1].lower()
                            if ext not in _PATH_EXTENSIONS:
                                continue
                        edges.append(
                            DependencyEdge(
                                source_file="",
                                source_symbol=None,
                                target_file=None,
                                target_symbol=None,
                                dep_type=DepType.REFERENCE,
                                metadata={
                                    "kind": "doc_code_block",
                                    "module": path,
                                    "line": line_start + i,
                                    "confidence": "low",
                                },
                            )
                        )

        return edges
