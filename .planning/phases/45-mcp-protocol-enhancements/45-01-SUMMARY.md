---
phase: 45-mcp-protocol-enhancements
plan: 01
subsystem: mcp
tags: [mcp, roots, fastmcp, file-uri, project-detection, async]

# Dependency graph
requires:
  - phase: 44-docker-image-simplification
    provides: "Stable infrastructure baseline for MCP server"
provides:
  - "file_uri_to_path() utility for file:// URI to Path conversion"
  - "_detect_project() async helper with roots > query_param > env > cwd priority chain"
  - "register_roots_notification() for roots/list_changed handler"
affects: [45-02, 45-03, 45-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Priority-chain detection: roots > query_param > env > cwd"
    - "file:// URI parsing via urlparse + unquote (NOT FileUrl.path)"
    - "Low-level server notification_handlers dict for roots change"

key-files:
  created:
    - src/cocosearch/mcp/project_detection.py
  modified:
    - src/cocosearch/mcp/__init__.py

key-decisions:
  - "Return type is tuple[Path, str] -- never None; cwd is unconditional fallback"
  - "Use urlparse + unquote for URI decoding (FileUrl.path does not percent-decode)"
  - "No caching in _detect_project -- re-detect fresh each tool call; notification handler logs only"
  - "Access _mcp_server.notification_handlers directly (FastMCP has no public notification API)"

patterns-established:
  - "Priority-chain detection: roots > query_param > env > cwd"
  - "Async tool pattern: ctx: Context parameter for session/request access"
  - "Guard ctx.request_context.request is not None for stdio safety"

# Metrics
duration: 2min
completed: 2026-02-08
---

# Phase 45 Plan 01: Project Detection Module Summary

**Async project detection helper with file URI parsing, 4-step priority chain (roots > query_param > env > cwd), and roots change notification handler**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-08T15:34:40Z
- **Completed:** 2026-02-08T15:36:24Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Created `project_detection.py` with `file_uri_to_path()`, `_detect_project()`, and `register_roots_notification()`
- `file_uri_to_path` correctly handles file:// URIs with percent-decoding using `urlparse` + `unquote`
- `_detect_project` is async, follows roots > query_param > env > cwd priority, always returns a valid Path (never None)
- `register_roots_notification` hooks into the low-level server notification_handlers dict for roots/list_changed
- Package-level exports updated in `__init__.py` for all three functions

## Task Commits

Each task was committed atomically:

1. **Task 1: Create project_detection.py module** - `05e475c` (feat)
2. **Task 2: Update mcp/__init__.py exports** - `ae2f7c2` (feat)

## Files Created/Modified
- `src/cocosearch/mcp/project_detection.py` - New module: file_uri_to_path(), _detect_project(), register_roots_notification()
- `src/cocosearch/mcp/__init__.py` - Updated exports to include new project detection functions

## Decisions Made
- Return type is `tuple[Path, str]` (never None) -- cwd is an unconditional fallback, so None is impossible
- Used `urlparse` + `unquote` from stdlib for file:// URI parsing (Pydantic's FileUrl.path does NOT decode percent-encoding)
- No caching in `_detect_project` -- re-detect fresh on each tool call; roots notification handler is logging-only
- Accessed `_mcp_server.notification_handlers` directly since FastMCP has no public API for notification registration

## Deviations from Plan

None -- plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `_detect_project()` is ready for integration into server.py tools (Plan 02)
- All MCP tools can be converted to async and accept `ctx: Context` to use the new detection
- `register_roots_notification()` is ready to be called during server initialization

---
*Phase: 45-mcp-protocol-enhancements*
*Completed: 2026-02-08*
