# Phase 23: MCP Transport Integration - Research

**Researched:** 2026-02-01
**Domain:** MCP transport protocols (stdio, SSE, Streamable HTTP)
**Confidence:** HIGH

## Summary

This phase adds multi-transport support to the existing MCP server, enabling users to select between stdio, SSE, and Streamable HTTP transports at runtime via CLI flag (`--transport`) or environment variable (`MCP_TRANSPORT`). The existing codebase already uses `mcp[cli]>=1.26.0` with FastMCP, which natively supports all three transports via the `mcp.run(transport=...)` parameter.

The implementation is straightforward because FastMCP abstracts transport complexity. The main work is CLI integration (adding `--transport` and `--port` flags to the `mcp` subcommand), environment variable handling, and adding the `/health` endpoint for network transports. The existing stdio implementation in `server.py` remains the default, preserving backward compatibility.

The MCP specification deprecated SSE transport (as of 2025-03-26) in favor of Streamable HTTP, but SSE remains necessary for Claude Desktop compatibility. Streamable HTTP is the future standard and recommended for new integrations.

**Primary recommendation:** Extend `mcp_command()` in `cli.py` and `run_server()` in `server.py` to accept transport, host, and port parameters. Use FastMCP's native transport support rather than implementing transport layers manually.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| mcp[cli] | >=1.26.0 | MCP server with FastMCP | Already in project, provides native transport support |
| FastMCP | (bundled) | High-level MCP server framework | Decorator-based API, handles transport abstraction |
| Starlette | (transitive) | ASGI framework | Used internally by FastMCP for HTTP transports |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| argparse | (stdlib) | CLI argument parsing | Already used in cli.py |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| FastMCP transport | Manual ASGI implementation | Much more code, no benefit. FastMCP is the standard. |
| Starlette routes | FastAPI integration | Adds dependency, FastMCP custom_route is sufficient |

**Installation:**
```bash
# No new dependencies needed - mcp[cli]>=1.26.0 already includes everything
```

## Architecture Patterns

### Recommended Project Structure
```
src/cocosearch/mcp/
    __init__.py          # Exports run_server
    server.py            # FastMCP instance, tools, run_server() function
```

The existing structure is already correct. Changes are additive:
- Extend `run_server()` to accept transport, host, port parameters
- Add health endpoint to FastMCP instance
- Update CLI to pass transport options

### Pattern 1: Transport Selection via FastMCP.run()
**What:** FastMCP's `run()` method accepts transport type as a string parameter
**When to use:** All transport configurations
**Example:**
```python
# Source: https://gofastmcp.com/deployment/running-server
# Source: https://pypi.org/project/mcp/ (v1.26.0)

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("cocosearch")

# Tools defined with @mcp.tool() decorator
@mcp.tool()
def search_code(...):
    ...

def run_server(transport: str = "stdio", host: str = "127.0.0.1", port: int = 3000):
    """Run the MCP server with specified transport."""
    if transport == "stdio":
        mcp.run(transport="stdio")
    elif transport == "sse":
        mcp.run(transport="sse", host=host, port=port)
    elif transport == "http":
        mcp.run(transport="streamable-http", host=host, port=port)
```

### Pattern 2: Health Endpoint via FastMCP custom_route
**What:** Add HTTP health check endpoint for Docker/orchestration
**When to use:** Network transports (SSE, HTTP)
**Example:**
```python
# Source: https://deepwiki.com/modelcontextprotocol/python-sdk/9.1-running-servers

from starlette.responses import JSONResponse

@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    return JSONResponse({"status": "ok"})
```

### Pattern 3: CLI Flag with Environment Variable Fallback
**What:** CLI flag takes precedence over environment variable, with sensible default
**When to use:** Runtime configuration options
**Example:**
```python
# Pattern already used in cli.py for other options

import os

def mcp_command(args: argparse.Namespace) -> int:
    # Priority: CLI flag > env var > default
    transport = args.transport or os.getenv("MCP_TRANSPORT", "stdio")
    port = args.port or int(os.getenv("COCOSEARCH_MCP_PORT", "3000"))

    # Validate transport
    valid_transports = ("stdio", "sse", "http")
    if transport not in valid_transports:
        print(f"Error: Invalid transport '{transport}'. Valid options: {', '.join(valid_transports)}")
        return 1

    run_server(transport=transport, host="0.0.0.0", port=port)
    return 0
```

### Pattern 4: Startup Logging for All Transports
**What:** Log transport and connection details on startup
**When to use:** Always, for all transports
**Example:**
```python
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,  # CRITICAL: stderr to avoid corrupting stdio transport
)
logger = logging.getLogger(__name__)

def run_server(transport: str = "stdio", host: str = "127.0.0.1", port: int = 3000):
    logger.info(f"Starting MCP server with transport: {transport}")

    if transport == "stdio":
        logger.info("Using stdio transport")
    elif transport in ("sse", "http"):
        endpoint = "/sse" if transport == "sse" else "/mcp"
        logger.info(f"Connect at http://{host}:{port}{endpoint}")

    # ... run server
```

### Anti-Patterns to Avoid
- **Logging to stdout with stdio transport:** Corrupts JSON-RPC stream. Always use stderr.
- **Custom transport implementations:** FastMCP handles everything, don't rebuild.
- **Blocking startup checks in async context:** FastMCP's `run()` manages the event loop.
- **Hardcoding localhost in server:** Use `0.0.0.0` for container deployments.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SSE streaming | Custom HTTP SSE handler | `mcp.run(transport="sse")` | Protocol details, session management, reconnection |
| HTTP transport | Custom ASGI endpoint | `mcp.run(transport="streamable-http")` | Message routing, bidirectional streams |
| JSON-RPC handling | Manual message parsing | FastMCP | Error handling, batching, protocol compliance |
| Health endpoint | Separate Flask/Uvicorn server | `@mcp.custom_route()` | Single process, shared lifecycle |
| Port binding | Custom socket handling | FastMCP host/port params | Starlette handles it correctly |

**Key insight:** FastMCP is a complete solution. The MCP SDK team specifically designed it to abstract transport complexity. Adding custom transport code is technical debt.

## Common Pitfalls

### Pitfall 1: stdout Pollution with stdio Transport
**What goes wrong:** Any output to stdout corrupts the JSON-RPC message stream, causing protocol errors.
**Why it happens:** Python's `print()` defaults to stdout. Third-party libraries may log to stdout.
**How to avoid:**
- Configure logging to stderr explicitly (`stream=sys.stderr`)
- Use `logger.info()` not `print()`
- Audit dependencies for stdout usage
**Warning signs:** "Parse error" or "Invalid JSON" messages from MCP client

### Pitfall 2: --port Flag Ignored with stdio Transport
**What goes wrong:** User specifies `--port 8080 --transport stdio`, expects port to matter.
**Why it happens:** stdio doesn't use network ports.
**How to avoid:** Log a warning when `--port` is specified with stdio transport (per CONTEXT.md decision).
**Warning signs:** User confusion about why port setting doesn't work.

### Pitfall 3: Invalid Transport Value Not Caught Early
**What goes wrong:** Server crashes deep in FastMCP with unclear error.
**Why it happens:** Transport value passed through without validation.
**How to avoid:** Validate transport value immediately in CLI, exit with clear message listing valid options (per CONTEXT.md decision).
**Warning signs:** Stack traces mentioning transport/SSE/HTTP internals.

### Pitfall 4: Port Already in Use
**What goes wrong:** Server crashes on startup when another process uses the port.
**Why it happens:** No pre-check for port availability.
**How to avoid:** FastMCP will raise an exception. Catch it and provide clear error message (per CONTEXT.md decision).
**Warning signs:** "Address already in use" from Uvicorn/Starlette internals.

### Pitfall 5: Missing Health Endpoint
**What goes wrong:** Docker HEALTHCHECK fails, container marked unhealthy.
**Why it happens:** No `/health` route defined.
**How to avoid:** Add health endpoint via `@mcp.custom_route("/health")` for network transports.
**Warning signs:** Container restarts in Docker Compose/Kubernetes.

### Pitfall 6: Blocking Event Loop
**What goes wrong:** Server hangs or becomes unresponsive.
**Why it happens:** Synchronous I/O (like `cocoindex.init()`) called in async context.
**How to avoid:** Initialize CocoIndex in tool functions, not at server startup. Current code already does this correctly.
**Warning signs:** Server becomes unresponsive during operations.

## Code Examples

Verified patterns from official sources:

### Complete run_server() Implementation
```python
# Source: Synthesized from official MCP Python SDK docs and CONTEXT.md decisions

import logging
import sys
import os

from starlette.responses import JSONResponse
from mcp.server.fastmcp import FastMCP

# CRITICAL: Configure logging to stderr BEFORE other imports
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

mcp = FastMCP("cocosearch")

# Health endpoint for Docker/orchestration
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    return JSONResponse({"status": "ok"})

# ... existing @mcp.tool() definitions ...

def run_server(
    transport: str = "stdio",
    host: str = "0.0.0.0",
    port: int = 3000,
):
    """Run the MCP server with specified transport.

    Args:
        transport: Transport protocol - "stdio", "sse", or "http"
        host: Host to bind to (ignored for stdio)
        port: Port to bind to (ignored for stdio)
    """
    # Log startup info (always to stderr)
    logger.info(f"Starting MCP server with transport: {transport}")

    if transport == "stdio":
        if port != 3000:  # Non-default port specified
            logger.warning("--port is ignored with stdio transport")
        mcp.run(transport="stdio")
    elif transport == "sse":
        logger.info(f"Connect at http://{host}:{port}/sse")
        logger.info(f"Health check at http://{host}:{port}/health")
        mcp.run(transport="sse", host=host, port=port)
    elif transport == "http":
        logger.info(f"Connect at http://{host}:{port}/mcp")
        logger.info(f"Health check at http://{host}:{port}/health")
        mcp.run(transport="streamable-http", host=host, port=port)
    else:
        # Should not reach here if CLI validates
        raise ValueError(f"Invalid transport: {transport}")
```

### CLI Integration for mcp Subcommand
```python
# Source: Pattern from existing cli.py, adapted for transport options

def mcp_command(args: argparse.Namespace) -> int:
    """Start the MCP server.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    from cocosearch.mcp import run_server

    # Resolve transport: CLI > env > default
    transport = args.transport or os.getenv("MCP_TRANSPORT", "stdio")

    # Validate transport
    valid_transports = ("stdio", "sse", "http")
    if transport not in valid_transports:
        print(f"Error: Invalid transport '{transport}'. Valid options: {', '.join(valid_transports)}", file=sys.stderr)
        return 1

    # Resolve port: CLI > env > default
    if args.port is not None:
        port = args.port
    else:
        port_env = os.getenv("COCOSEARCH_MCP_PORT", "3000")
        try:
            port = int(port_env)
        except ValueError:
            print(f"Error: Invalid port value in COCOSEARCH_MCP_PORT: '{port_env}'", file=sys.stderr)
            return 1

    try:
        run_server(transport=transport, port=port)
        return 0
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"Error: Port {port} is already in use", file=sys.stderr)
            return 1
        raise

# In main(), update mcp subparser:
mcp_parser = subparsers.add_parser(
    "mcp",
    help="Start MCP server for LLM integration",
    description="Start the Model Context Protocol server for use with Claude and other LLM clients.",
)
mcp_parser.add_argument(
    "--transport", "-t",
    choices=["stdio", "sse", "http"],
    default=None,
    help="Transport protocol (default: stdio). [env: MCP_TRANSPORT]",
)
mcp_parser.add_argument(
    "--port", "-p",
    type=int,
    default=None,
    help="Port for SSE/HTTP transports (default: 3000). [env: COCOSEARCH_MCP_PORT]",
)
```

### Transport Endpoint Conventions
```python
# Source: MCP specification, FastMCP defaults

# SSE transport endpoints:
# - GET /sse - establishes SSE stream
# - POST /messages - receives client messages
# - GET /health - health check (custom)

# Streamable HTTP transport endpoints:
# - POST /mcp - all MCP interactions
# - GET /mcp - optional server-initiated streaming
# - GET /health - health check (custom)

# FastMCP defaults:
# - SSE: /sse (matches spec convention)
# - HTTP: /mcp (matches spec example)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| SSE transport (HTTP+SSE) | Streamable HTTP | March 2025 (spec 2025-03-26) | SSE deprecated, use HTTP for new integrations |
| Dual endpoint SSE | Single endpoint HTTP | March 2025 | Simpler client implementation |
| Session cookies | Mcp-Session-Id header | March 2025 | Stateless HTTP possible |

**Deprecated/outdated:**
- **SSE transport:** Officially deprecated in MCP spec. Still needed for Claude Desktop compatibility. The MCP SDK still supports it, but new clients should use Streamable HTTP.
- **HTTP+SSE dual endpoints:** Old pattern with separate GET /events and POST /messages. Replaced by single-endpoint Streamable HTTP.

## Open Questions

Things that couldn't be fully resolved:

1. **Claude Desktop HTTP support timeline**
   - What we know: SSE is deprecated, Streamable HTTP is the standard
   - What's unclear: When Claude Desktop will natively support Streamable HTTP
   - Recommendation: Support both SSE and HTTP transports for now. Users can use `mcp-remote` npm package as bridge if needed.

2. **FastMCP host option in streamable-http**
   - What we know: SSE supports host parameter, there was a reported bug in FastMCP 2.8.1 where host was ignored for streamable-http
   - What's unclear: Whether this is fixed in current mcp[cli]>=1.26.0
   - Recommendation: Test during implementation. Fall back to 0.0.0.0 if host binding doesn't work.

## Sources

### Primary (HIGH confidence)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) - FastMCP API, transport options
- [PyPI mcp v1.26.0](https://pypi.org/project/mcp/) - Current package version, transport documentation
- [MCP Specification 2025-03-26](https://modelcontextprotocol.io/specification/2025-03-26/basic/transports) - Official transport specification
- [FastMCP Running Server](https://gofastmcp.com/deployment/running-server) - Transport options, host/port parameters
- [DeepWiki MCP SDK Running Servers](https://deepwiki.com/modelcontextprotocol/python-sdk/9.1-running-servers) - Configuration options, custom routes

### Secondary (MEDIUM confidence)
- [Cloudflare Streamable HTTP Blog](https://blog.cloudflare.com/streamable-http-mcp-servers-python/) - Implementation patterns
- [Nearform MCP Tips](https://nearform.com/digital-community/implementing-model-context-protocol-mcp-tips-tricks-and-pitfalls/) - Common pitfalls

### Tertiary (LOW confidence)
- [FastMCP GitHub Issue #873](https://github.com/jlowin/fastmcp/issues/873) - Host option not supported in streamable-http (may be fixed)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - FastMCP is the official recommendation, already in project dependencies
- Architecture: HIGH - Patterns verified in official MCP SDK documentation
- Pitfalls: HIGH - stdout pollution documented extensively, other pitfalls from spec and project research

**Research date:** 2026-02-01
**Valid until:** 2026-03-01 (30 days - MCP SDK is stable)
