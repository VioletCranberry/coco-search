# Phase 17: Developer Setup Script - Context

**Gathered:** 2026-01-31
**Status:** Ready for planning

<domain>
## Phase Boundary

One-command setup script (`./dev-setup.sh`) that gets new developers from zero to a working CocoSearch environment. Handles dependency checking, container startup, Python environment setup, and codebase indexing. Script completes with indexed codebase ready for search.

</domain>

<decisions>
## Implementation Decisions

### Dependency detection
- Docker: Check if installed and running; fail with clear message if not running (don't auto-start)
- Ollama: Always use Docker container (not native) for consistency across developers
- Python: Skip Python version check — assume dev environment responsibility
- Package manager: Use UV for dependency installation (consistency with project)

### Progress & output style
- Plain text output — no colors, no emojis (CI-friendly, minimal)
- Stream all output from underlying tools (docker pull, uv install, etc.)
- Single output mode — no verbosity flags
- Inline prefix format: `postgres: Starting container...` — minimal, grep-friendly

### Failure handling
- On failure: prompt user "Keep containers for debugging? [y/N]"
- No resume support — always restart fresh on each run
- Exit code + stderr message for errors (standard Unix)
- Port conflicts: fail with clear message showing which port is in use

### Post-setup experience
- Auto-index CocoSearch codebase at the end
- Run a demo search query to show it's working
- Show quick reference commands (search, index, repl) — copy-paste ready
- Include teardown instructions (how to stop services)

### Claude's Discretion
- Exact container names and network configuration
- Which demo search query to run
- Specific error message wording
- Order of setup steps

</decisions>

<specifics>
## Specific Ideas

- User wants UV for package management (consistency)
- Output should be grep-friendly with inline prefixes
- Demo query proves the setup actually works end-to-end

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 17-developer-setup-script*
*Context gathered: 2026-01-31*
