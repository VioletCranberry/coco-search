"""Terraform dependency extractor.

Extracts references from Terraform/HCL files:
- ``module`` block ``source`` attributes (local or registry modules,
  with optional ``version``)
- ``required_providers`` entries (provider source and version constraints)
- ``data "terraform_remote_state"`` blocks (cross-stack dependencies)
- ``.tfvars`` file associations (variable files linked to module directories)

Regex-based since HCL is not YAML.  Local sources (starting with
``./`` or ``../``) are resolvable; registry sources are external.
All edges use ``dep_type = DepType.REFERENCE``.
"""

import re
from pathlib import PurePosixPath

from cocosearch.deps.models import DependencyEdge, DepType

# Match the start of a module block: module "name" {
_MODULE_START_RE = re.compile(r'module\s+"([^"]+)"\s*\{')

# Match source = "value" inside a block
_SOURCE_RE = re.compile(r'source\s*=\s*"([^"]+)"')

# Match version = "value" inside a block
_VERSION_RE = re.compile(r'version\s*=\s*"([^"]+)"')

# Match terraform { block start
_TERRAFORM_BLOCK_START_RE = re.compile(r"terraform\s*\{")

# Match required_providers { block start
_REQ_PROVIDERS_START_RE = re.compile(r"required_providers\s*\{")

# Match provider object entry: aws = {
_PROVIDER_ENTRY_RE = re.compile(r"([a-z_][a-z0-9_]*)\s*=\s*\{")

# Match provider shorthand: random = "hashicorp/random"
_PROVIDER_SHORTHAND_RE = re.compile(r'([a-z_][a-z0-9_]*)\s*=\s*"([^"]+)"')

# Match data "terraform_remote_state" "name" {
_REMOTE_STATE_START_RE = re.compile(r'data\s+"terraform_remote_state"\s+"([^"]+)"\s*\{')

# Match backend = "value" inside a block
_BACKEND_RE = re.compile(r'backend\s*=\s*"([^"]+)"')

# Match key = "value" inside a block
_KEY_RE = re.compile(r'key\s*=\s*"([^"]+)"')


def _extract_block_body(content: str, start_pos: int) -> str:
    """Extract the body of a brace-delimited block starting after the opening ``{``.

    Args:
        content: Full file content.
        start_pos: Position immediately after the opening ``{``.

    Returns:
        The text between the opening and matching closing brace.
    """
    depth = 1
    i = start_pos
    while i < len(content) and depth > 0:
        if content[i] == "{":
            depth += 1
        elif content[i] == "}":
            depth -= 1
        i += 1
    return content[start_pos : i - 1] if depth == 0 else content[start_pos:]


def _extract_module_blocks(content: str) -> list[tuple[str, str]]:
    """Extract (module_name, block_body) pairs from module blocks."""
    results = []
    for match in _MODULE_START_RE.finditer(content):
        module_name = match.group(1)
        block_body = _extract_block_body(content, match.end())
        results.append((module_name, block_body))
    return results


class TerraformExtractor:
    """Extractor for Terraform reference edges."""

    LANGUAGES: set[str] = {"terraform"}

    def extract(self, file_path: str, content: str) -> list[DependencyEdge]:
        if not content:
            return []

        edges: list[DependencyEdge] = []

        # .tfvars file association
        if file_path.endswith(".tfvars"):
            dir_path = str(PurePosixPath(file_path).parent)
            edges.append(
                DependencyEdge(
                    source_file="",
                    source_symbol=None,
                    target_file=dir_path,
                    target_symbol=None,
                    dep_type=DepType.REFERENCE,
                    metadata={
                        "kind": "variable_file",
                        "filename": PurePosixPath(file_path).name,
                    },
                )
            )

        # Module sources
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

            metadata: dict[str, str] = {
                "kind": "module_source",
                "value": source,
            }
            version_match = _VERSION_RE.search(block_body)
            if version_match:
                metadata["version"] = version_match.group(1)

            edges.append(
                DependencyEdge(
                    source_file="",
                    source_symbol=module_name,
                    target_file=target_file,
                    target_symbol=None,
                    dep_type=DepType.REFERENCE,
                    metadata=metadata,
                )
            )

        # Required providers
        edges.extend(self._extract_required_providers(content))

        # Remote state
        edges.extend(self._extract_remote_state(content))

        return edges

    @staticmethod
    def _extract_required_providers(content: str) -> list[DependencyEdge]:
        """Extract provider edges from ``terraform { required_providers { } }``."""
        edges: list[DependencyEdge] = []

        for tf_match in _TERRAFORM_BLOCK_START_RE.finditer(content):
            tf_body = _extract_block_body(content, tf_match.end())

            rp_match = _REQ_PROVIDERS_START_RE.search(tf_body)
            if not rp_match:
                continue

            rp_body = _extract_block_body(tf_body, rp_match.end())

            # Parse object-form providers: aws = { source = "...", version = "..." }
            for entry_match in _PROVIDER_ENTRY_RE.finditer(rp_body):
                provider_name = entry_match.group(1)
                entry_body = _extract_block_body(rp_body, entry_match.end())

                source_match = _SOURCE_RE.search(entry_body)
                if not source_match:
                    continue

                metadata: dict[str, str] = {
                    "kind": "provider",
                    "source": source_match.group(1),
                }
                version_match = _VERSION_RE.search(entry_body)
                if version_match:
                    metadata["version"] = version_match.group(1)

                edges.append(
                    DependencyEdge(
                        source_file="",
                        source_symbol=provider_name,
                        target_file=None,
                        target_symbol=None,
                        dep_type=DepType.REFERENCE,
                        metadata=metadata,
                    )
                )

            # Parse shorthand providers: random = "hashicorp/random"
            # Only match lines that aren't already inside an object entry
            for sh_match in _PROVIDER_SHORTHAND_RE.finditer(rp_body):
                provider_name = sh_match.group(1)
                # Skip if this name was already handled as an object entry
                if any(
                    e.source_symbol == provider_name
                    and e.metadata.get("kind") == "provider"
                    for e in edges
                ):
                    continue
                # Verify this isn't a nested attribute (source = "..." or version = "...")
                if provider_name in ("source", "version"):
                    continue

                edges.append(
                    DependencyEdge(
                        source_file="",
                        source_symbol=provider_name,
                        target_file=None,
                        target_symbol=None,
                        dep_type=DepType.REFERENCE,
                        metadata={
                            "kind": "provider",
                            "source": sh_match.group(2),
                        },
                    )
                )

        return edges

    @staticmethod
    def _extract_remote_state(content: str) -> list[DependencyEdge]:
        """Extract edges from ``data "terraform_remote_state"`` blocks."""
        edges: list[DependencyEdge] = []

        for rs_match in _REMOTE_STATE_START_RE.finditer(content):
            state_name = rs_match.group(1)
            block_body = _extract_block_body(content, rs_match.end())

            metadata: dict[str, str] = {
                "kind": "remote_state",
                "name": state_name,
            }
            backend_match = _BACKEND_RE.search(block_body)
            if backend_match:
                metadata["backend"] = backend_match.group(1)

            key_match = _KEY_RE.search(block_body)
            if key_match:
                metadata["key"] = key_match.group(1)

            edges.append(
                DependencyEdge(
                    source_file="",
                    source_symbol=state_name,
                    target_file=None,
                    target_symbol=None,
                    dep_type=DepType.REFERENCE,
                    metadata=metadata,
                )
            )

        return edges
