"""Metadata extraction for DevOps file chunks.

Extracts structured metadata from DevOps file chunks (HCL, Dockerfile, Bash)
using regex pattern matching. Each chunk produces a DevOpsMetadata dataclass
with block_type, hierarchy, and language_id fields.

All regex patterns are compiled at module level to avoid recompilation overhead
on every chunk.
"""

import dataclasses
import re

import cocoindex


@dataclasses.dataclass
class DevOpsMetadata:
    """Structured metadata for a DevOps file chunk.

    Fields:
        block_type: The type of block (e.g., "resource", "FROM", "function").
                    Empty string for non-DevOps or unrecognized chunks.
        hierarchy: Dot-separated hierarchy for HCL (e.g., "resource.aws_s3_bucket.data"),
                   colon-prefixed for Dockerfile/Bash (e.g., "stage:builder", "function:deploy").
                   Empty string for non-DevOps or unrecognized chunks.
        language_id: Language identifier ("hcl", "dockerfile", "bash").
                     Empty string for non-DevOps files.
    """

    block_type: str
    hierarchy: str
    language_id: str


# ---------------------------------------------------------------------------
# Module-level compiled regex patterns
# ---------------------------------------------------------------------------

# Comment patterns (per-language)
_HCL_COMMENT_LINE = re.compile(r"^\s*(?:#|//|/\*).*$", re.MULTILINE)
_DOCKERFILE_COMMENT_LINE = re.compile(r"^\s*#.*$", re.MULTILINE)
_BASH_COMMENT_LINE = re.compile(r"^\s*#.*$", re.MULTILINE)

# HCL: Match 12 top-level block keywords with 0-2 quoted labels
_HCL_BLOCK_RE = re.compile(
    r"^(resource|data|variable|output|locals|module|provider|terraform|import|moved|removed|check)"
    r'(?:\s+"([^"]*)")?'  # optional first label
    r'(?:\s+"([^"]*)")?'  # optional second label
    r"\s*\{?",
)

# Dockerfile: Match any of the 18 instructions at line start
_DOCKERFILE_INSTRUCTION_RE = re.compile(
    r"^(FROM|RUN|CMD|LABEL|MAINTAINER|EXPOSE|ENV|ADD|COPY|ENTRYPOINT|"
    r"VOLUME|USER|WORKDIR|ARG|ONBUILD|STOPSIGNAL|HEALTHCHECK|SHELL)\b"
)

# Dockerfile: FROM with optional --platform and optional AS clause
_DOCKERFILE_FROM_RE = re.compile(
    r"^FROM\s+"
    r"(?:--platform=\S+\s+)?"
    r"(\S+)"  # image reference
    r"(?:\s+[Aa][Ss]\s+(\S+))?",  # optional AS stage_name (case-insensitive AS)
)

# Bash: Three function definition syntaxes (POSIX, ksh, hybrid)
_BASH_FUNCTION_RE = re.compile(
    r"^(?:"
    r"function\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:\(\s*\))?\s*\{?"
    r"|"
    r"([a-zA-Z_][a-zA-Z0-9_]*)\s*\(\s*\)\s*\{?"
    r")"
)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _strip_leading_comments(text: str, comment_pattern: re.Pattern) -> str:
    """Strip leading comment and blank lines from chunk text.

    Args:
        text: The chunk text content.
        comment_pattern: A compiled regex matching comment lines for the language.

    Returns:
        The text from the first non-comment, non-blank line onward.
        Empty string if all lines are comments or blank.
    """
    lines = text.lstrip().split("\n")
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped and not comment_pattern.match(line):
            return "\n".join(lines[i:])
    return ""


# ---------------------------------------------------------------------------
# Per-language extraction functions (plain Python, not decorated)
# ---------------------------------------------------------------------------


def extract_hcl_metadata(text: str) -> DevOpsMetadata:
    """Extract metadata from an HCL chunk.

    Matches the 12 top-level HCL block keywords and extracts up to 2 quoted
    labels for building the dot-separated hierarchy.

    Args:
        text: The chunk text content.

    Returns:
        DevOpsMetadata with extracted block_type and hierarchy, language_id="hcl".
    """
    stripped = _strip_leading_comments(text, _HCL_COMMENT_LINE)
    match = _HCL_BLOCK_RE.match(stripped)
    if not match:
        return DevOpsMetadata(block_type="", hierarchy="", language_id="hcl")

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

    return DevOpsMetadata(block_type=block_type, hierarchy=hierarchy, language_id="hcl")


def extract_dockerfile_metadata(text: str) -> DevOpsMetadata:
    """Extract metadata from a Dockerfile chunk.

    Matches Dockerfile instructions. For FROM instructions, extracts stage name
    (AS clause) or image reference for the hierarchy.

    Args:
        text: The chunk text content.

    Returns:
        DevOpsMetadata with extracted block_type and hierarchy, language_id="dockerfile".
    """
    stripped = _strip_leading_comments(text, _DOCKERFILE_COMMENT_LINE)
    match = _DOCKERFILE_INSTRUCTION_RE.match(stripped)
    if not match:
        return DevOpsMetadata(block_type="", hierarchy="", language_id="dockerfile")

    instruction = match.group(1)

    if instruction == "FROM":
        from_match = _DOCKERFILE_FROM_RE.match(stripped)
        if from_match:
            stage_name = from_match.group(2)
            if stage_name:
                hierarchy = f"stage:{stage_name}"
            else:
                image_ref = from_match.group(1)
                hierarchy = f"image:{image_ref}"
        else:
            hierarchy = ""
    else:
        # Non-FROM instructions get empty hierarchy in v1.2
        hierarchy = ""

    return DevOpsMetadata(
        block_type=instruction, hierarchy=hierarchy, language_id="dockerfile"
    )


def extract_bash_metadata(text: str) -> DevOpsMetadata:
    """Extract metadata from a Bash chunk.

    Matches all 3 Bash function definition syntaxes (POSIX, ksh, hybrid).

    Args:
        text: The chunk text content.

    Returns:
        DevOpsMetadata with extracted block_type and hierarchy, language_id="bash".
    """
    stripped = _strip_leading_comments(text, _BASH_COMMENT_LINE)
    match = _BASH_FUNCTION_RE.match(stripped)
    if not match:
        return DevOpsMetadata(block_type="", hierarchy="", language_id="bash")

    # group(1) is the ksh/hybrid form, group(2) is the POSIX form
    func_name = match.group(1) or match.group(2)
    return DevOpsMetadata(
        block_type="function",
        hierarchy=f"function:{func_name}",
        language_id="bash",
    )


# ---------------------------------------------------------------------------
# Dispatch maps and main function
# ---------------------------------------------------------------------------

_LANGUAGE_DISPATCH = {
    "hcl": extract_hcl_metadata,
    "tf": extract_hcl_metadata,
    "tfvars": extract_hcl_metadata,
    "dockerfile": extract_dockerfile_metadata,
    "sh": extract_bash_metadata,
    "bash": extract_bash_metadata,
    "zsh": extract_bash_metadata,
    "shell": extract_bash_metadata,
}

_LANGUAGE_ID_MAP = {
    "hcl": "hcl",
    "tf": "hcl",
    "tfvars": "hcl",
    "dockerfile": "dockerfile",
    "sh": "bash",
    "bash": "bash",
    "zsh": "bash",
    "shell": "bash",
}

_EMPTY_METADATA = DevOpsMetadata(block_type="", hierarchy="", language_id="")


@cocoindex.op.function()
def extract_devops_metadata(text: str, language: str) -> DevOpsMetadata:
    """Extract structured metadata from a DevOps file chunk.

    Args:
        text: The chunk text content.
        language: Language identifier from extract_language() (e.g., "tf", "dockerfile", "sh").

    Returns:
        DevOpsMetadata with extracted fields, or empty strings for non-DevOps files.
    """
    extractor = _LANGUAGE_DISPATCH.get(language)
    if extractor is None:
        return _EMPTY_METADATA

    metadata = extractor(text)
    # Override language_id with canonical ID (e.g., "tf" -> "hcl")
    return DevOpsMetadata(
        block_type=metadata.block_type,
        hierarchy=metadata.hierarchy,
        language_id=_LANGUAGE_ID_MAP[language],
    )
