"""Project detection module for MCP server.

Provides file URI parsing, the priority-chain detection helper, and roots
notification registration. All MCP tools call ``_detect_project()`` to
determine which project the user is working with.

Detection priority chain: roots > query_param > env > cwd
"""

import logging
import os
from pathlib import Path
from urllib.parse import unquote, urlparse

from mcp.server.fastmcp import Context, FastMCP
from mcp.shared.exceptions import McpError
from mcp.types import ClientCapabilities, RootsCapability, RootsListChangedNotification

logger = logging.getLogger(__name__)


def file_uri_to_path(uri: str) -> Path | None:
    """Convert a file:// URI to a filesystem Path (Unix only).

    Uses ``urlparse`` + ``unquote`` for correct percent-decoding.
    Do NOT use ``FileUrl.path`` from Pydantic -- it does NOT decode
    percent-encoding (e.g. ``%20`` stays as ``%20``).

    Args:
        uri: A URI string, expected to start with ``file://``.

    Returns:
        A :class:`Path` if the URI is valid, or ``None`` if the URI does
        not start with ``file://`` or has an empty path component.

    Examples:
        >>> file_uri_to_path("file:///tmp/test")
        PosixPath('/tmp/test')
        >>> file_uri_to_path("file:///my%20project")
        PosixPath('/my project')
        >>> file_uri_to_path("https://example.com")  # not file://
        >>> file_uri_to_path("")
    """
    if not uri or not uri.startswith("file://"):
        return None
    parsed = urlparse(uri)
    decoded_path = unquote(parsed.path)
    if not decoded_path:
        return None
    return Path(decoded_path)


async def _detect_project(ctx: Context) -> tuple[Path, str]:
    """Detect the active project using the priority chain.

    Priority: roots > query_param > env > cwd

    This function **always** returns a valid ``Path`` because step 4 (cwd)
    is an unconditional fallback. It never returns ``None``.

    Args:
        ctx: FastMCP Context, auto-injected by the framework.

    Returns:
        ``(path, source)`` where *source* is one of ``"roots"``,
        ``"query_param"``, ``"env"``, or ``"cwd"``.
    """
    # Step 1 -- Try MCP Roots capability
    try:
        session = ctx.session
        if session.check_client_capability(ClientCapabilities(roots=RootsCapability())):
            logger.debug("Client supports Roots capability, listing roots...")
            result = await session.list_roots()
            logger.debug("Roots returned: %d root(s)", len(result.roots))
            for root in result.roots:
                path = file_uri_to_path(str(root.uri))
                if path and path.exists():
                    logger.info(
                        "Project detected via roots: %s (root name: %s)",
                        path,
                        root.name,
                    )
                    return path, "roots"
                elif path:
                    logger.debug("Root path does not exist on disk, skipping: %s", path)
        else:
            logger.debug("Client does not support Roots capability")
    except McpError as exc:
        logger.debug("McpError while listing roots: %s", exc)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Unexpected error while listing roots: %s", exc)

    # Step 2 -- Try HTTP query parameter
    try:
        request = ctx.request_context.request
        if request is not None:
            project_path = request.query_params.get("project_path")
            if project_path:
                path = Path(project_path)
                if not path.is_absolute():
                    logger.debug(
                        "Rejecting relative project_path query param: %s",
                        project_path,
                    )
                elif path.exists():
                    logger.info("Project detected via query_param: %s", path)
                    return path, "query_param"
                else:
                    logger.debug(
                        "project_path query param does not exist on disk: %s",
                        project_path,
                    )
        else:
            logger.debug("No HTTP request available (stdio transport)")
    except AttributeError:
        logger.debug("Could not access request context (likely stdio transport)")
    except Exception as exc:  # noqa: BLE001
        logger.debug("Unexpected error reading query param: %s", exc)

    # Step 3 -- Try environment variable
    env_path = os.environ.get("COCOSEARCH_PROJECT_PATH") or os.environ.get(
        "COCOSEARCH_PROJECT"
    )
    if env_path:
        path = Path(env_path)
        if path.exists():
            logger.info("Project detected via env: %s", path)
            return path, "env"
        else:
            logger.debug("Env var project path does not exist on disk: %s", env_path)

    # Step 4 -- Fall back to cwd (unconditional)
    cwd = Path.cwd()
    logger.info("Project detected via cwd: %s", cwd)
    return cwd, "cwd"


def register_roots_notification(mcp_server: FastMCP) -> None:
    """Register a handler for ``notifications/roots/list_changed``.

    The handler logs the notification. No caching is needed because
    ``_detect_project()`` is called fresh on each tool invocation.

    Args:
        mcp_server: The :class:`FastMCP` instance (e.g. the module-level
            ``mcp`` object from ``server.py``).
    """

    async def _handle_roots_changed(
        notification: RootsListChangedNotification,
    ) -> None:
        logger.info("Roots list changed, will re-detect on next tool call")

    # FastMCP does not expose a decorator for notification handlers.
    # Register directly on the underlying low-level server.
    mcp_server._mcp_server.notification_handlers[  # noqa: SLF001
        RootsListChangedNotification
    ] = _handle_roots_changed
    logger.debug("Registered roots list changed notification handler")
