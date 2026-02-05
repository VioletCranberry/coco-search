# Phase 36: Developer Skills - Research

**Researched:** 2026-02-05
**Domain:** Agent skills documentation (SKILL.md format)
**Confidence:** HIGH

## Summary

Phase 36 creates compact skill documentation files for Claude Code and OpenCode that guide developers on installing CocoSearch and routing queries appropriately between CocoSearch and traditional tools like grep/ripgrep. The Agent Skills format is an open standard adopted by both Claude Code and OpenCode, making the same SKILL.md files work across both platforms.

Skills consist of YAML frontmatter (name + description for auto-triggering) and markdown content (instructions). The key insight is progressive disclosure: skill descriptions are always in context, but full content only loads when triggered. This means compact (~100 lines), focused documentation that helps AI assistants make routing decisions quickly.

For CocoSearch, routing guidance is critical because semantic search and grep/ripgrep serve different purposes. CocoSearch excels at intent-based discovery ("find authentication logic") while grep excels at exact matches ("find getUserById"). The skills need decision tree formats with inline examples showing when to use each tool.

**Primary recommendation:** Create two compact SKILL.md files (one for Claude Code, one for OpenCode) with identical structure but platform-specific MCP configuration. Focus on routing decision trees with concrete query examples, UV-based installation, and verification steps.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Agent Skills Spec | 2025-12 | SKILL.md format specification | Open standard adopted by Claude Code, OpenCode, Codex CLI, and other tools |
| UV | Latest | Python package installer | Replaces pip/pipx; 10-100x faster, single command for install |
| FastMCP | Latest (via CocoSearch) | MCP server protocol | Already in CocoSearch dependencies for stdio/HTTP transport |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Tree-sitter | Via CocoSearch | Language-aware parsing | Used internally by CocoSearch for symbol extraction |
| PostgreSQL+pgvector | 17+ | Vector storage | CocoSearch dependency, mentioned in setup |
| Ollama | Latest | Local embeddings | CocoSearch dependency for nomic-embed-text model |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Agent Skills (SKILL.md) | Custom markdown docs | Skills auto-trigger and integrate with /slash commands; custom docs require manual reference |
| UV | pip/pipx | UV is 10-100x faster, simpler syntax, but requires separate install step |
| Compact format (~100 lines) | Full documentation | Full docs exceed context budget; skills use progressive disclosure |

**Installation:**
```bash
# UV installation (one-time)
curl -LsSf https://astral.sh/uv/install.sh | sh  # macOS/Linux
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"  # Windows

# CocoSearch installation via skill
uv pip install cocosearch
```

## Architecture Patterns

### Recommended Skill Structure

```
skills/
├── claude-code-cocosearch/
│   └── SKILL.md          # Claude Code setup + routing
└── opencode-cocosearch/
    └── SKILL.md          # OpenCode setup + routing
```

### Pattern 1: Progressive Disclosure Format

**What:** Three-level loading: (1) description always in context, (2) SKILL.md body when triggered, (3) reference files as needed

**When to use:** All skills, especially when context budget is limited or multiple skills compete for attention

**Example:**
```markdown
---
name: cocosearch-setup
description: Install and configure CocoSearch for semantic code search via MCP. Use when setting up CocoSearch, configuring Claude Code integration, or troubleshooting MCP connection.
---

## Quick Setup (5 minutes)

1. Install UV: `curl -LsSf https://astral.sh/uv/install.sh | sh`
2. Install CocoSearch: `uv pip install cocosearch`
3. Verify: `cocosearch --version`
4. [MCP configuration steps...]

For troubleshooting, see project README.md
```

**Source:** [Claude Code Skills Documentation](https://code.claude.com/docs/en/skills)

### Pattern 2: Decision Tree Routing

**What:** Explicit "if X, use CocoSearch; if Y, use grep" branching with inline query examples

**When to use:** Routing guidance between overlapping tools (semantic search vs grep vs IDE tools)

**Example:**
```markdown
## When to Use CocoSearch

**Use CocoSearch for:**
- Intent-based discovery: "find authentication logic"
  → Returns functions like validateUser, checkCredentials even without keyword match
- Symbol exploration: "database connection handlers" --symbol-type function
  → Filters to function-level results with semantic understanding
- Cross-file patterns: "error handling patterns"
  → Finds conceptually similar code across multiple files

**Use grep/ripgrep for:**
- Exact identifier matches: `rg "getUserById"`
  → Faster for literal string lookup
- Regex patterns: `rg "TODO:.*urgent"`
  → Pattern matching CocoSearch doesn't support
- Single-file edits: `rg "import React" src/components/`
  → When you know the location and exact text

**Use IDE tools for:**
- Go-to-definition: Navigate to where a symbol is defined
- Find-references: All usages of a specific identifier
- Rename refactoring: Change identifier everywhere safely
```

**Source:** Research on [semantic search vs grep decision frameworks](https://www.aifreeapi.com/en/posts/claude-code-tool-search)

### Pattern 3: Hybrid Search + Symbol Filter Examples

**What:** Prioritize examples showing CocoSearch's power combo: hybrid search for identifiers + symbol filters for type narrowing

**When to use:** Demonstrating unique CocoSearch capabilities that grep and semantic-only search cannot replicate

**Example:**
```markdown
## Power Combo: Hybrid + Symbol Filters

```bash
# Find all authentication-related functions (identifier + semantic + type)
cocosearch search "authenticate" --hybrid --symbol-type function

# Expected output:
# [1] src/auth/validate.py:45-67 (score: 0.91)
#     def authenticate_user(username: str, password: str) -> User:
#         """Validate credentials and return user."""
```

Combines:
- Hybrid search → boosts exact "authenticate" matches
- Semantic → catches related terms (validate, verify, check)
- Symbol filter → functions only, excludes classes/comments
```

**Source:** CocoSearch v1.7 features (hybrid search, symbol filtering documented in README.md lines 750-850)

### Anti-Patterns to Avoid

- **Troubleshooting sections in skills**: Skills should reference README.md for troubleshooting; keep skills focused on "happy path" setup and usage
- **Duplicate content across skill and references**: If content exists in README.md, reference it rather than copying
- **Vague routing guidance**: Avoid "consider using CocoSearch when..." → Use explicit decision trees with concrete queries
- **Generic examples**: Avoid "search for code" → Show actual queries with expected output snippets

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Skill auto-triggering | Custom command parsing logic | Agent Skills frontmatter `description` field | Claude/OpenCode use description to decide when to load skills automatically |
| MCP server stdio/HTTP | Custom JSON-RPC implementation | FastMCP with --transport flag | Already in CocoSearch; handles protocol negotiation, transport switching |
| Routing decision logic | LLM prompting to choose tools | Decision tree in skill markdown | Explicit rules faster and more reliable than LLM reasoning over tool descriptions |
| Installation verification | Manual testing instructions | `cocosearch stats` command | Returns error if database/Ollama not connected; one command validates full stack |
| Query caching | Custom cache implementation | CocoSearch built-in cache (v1.8+) | Hash-based exact match cache, embedding similarity cache coming in REQ-003/004 |

**Key insight:** Skills are guidance documents, not code. Don't build new functionality; document existing functionality clearly so AI assistants route correctly.

## Common Pitfalls

### Pitfall 1: Exceeding Context Budget

**What goes wrong:** Skill descriptions total >15,000 characters, Claude excludes some skills from context

**Why it happens:** Each skill's description is always in context (for auto-triggering). Too many verbose descriptions exceed budget.

**How to avoid:**
- Keep descriptions under 100 characters when possible
- Use the SKILL.md body for details, not the description
- Check context usage with `/context` command in Claude Code

**Warning signs:** Claude doesn't suggest a skill you know exists; `/context` shows excluded skills warning

**Source:** [Claude Code skills troubleshooting](https://code.claude.com/docs/en/skills#skill-not-triggering)

### Pitfall 2: Config Path Assumptions

**What goes wrong:** Skill shows `~/.claude/skills/` path but user installs to `.claude/skills/` (project-local)

**Why it happens:** Skills can live in multiple locations (enterprise, personal, project); documentation often assumes one

**How to avoid:**
- Show both project-level (`.claude/skills/`) and global (`~/.claude/skills/`) options
- Explain tradeoffs: project = team sharing via git, global = personal across projects
- For CocoSearch: recommend project-level since setup is per-codebase

**Warning signs:** User reports "skill not found" despite following instructions

**Source:** [Claude Code skill discovery](https://code.claude.com/docs/en/skills#where-skills-live)

### Pitfall 3: UV vs pip Confusion

**What goes wrong:** Instructions say "uv pip install" but user tries "pip install" and gets version conflicts or slow install

**Why it happens:** UV syntax mimics pip but isn't identical; users default to familiar pip commands

**How to avoid:**
- State explicitly "Use UV, not pip" in bold
- Show UV installation as first step before any package installs
- Include verification: `uv --version` → should show UV version, not error

**Warning signs:** User reports "pip install took 5 minutes" (should be <10 seconds with UV)

**Source:** [UV documentation](https://docs.astral.sh/uv/getting-started/installation/)

### Pitfall 4: MCP Transport Mismatch

**What goes wrong:** Skill configures stdio transport but user's client expects HTTP, or vice versa

**Why it happens:** Claude Code uses stdio, Claude Desktop uses HTTP, OpenCode supports both

**How to avoid:**
- Platform-specific skills (separate for Claude Code vs OpenCode)
- Explicit transport specification in config examples
- Note: Claude Desktop requires mcp-remote bridge for HTTP

**Warning signs:** "Server disconnected" or "Connection refused" errors despite correct installation

**Source:** CocoSearch README.md Docker setup sections (lines 195-295), MCP transport differences

### Pitfall 5: Symbol Filter + Pre-v1.7 Index

**What goes wrong:** User tries `--symbol-type function` but gets "Index does not support symbol filtering" error

**Why it happens:** Symbol extraction added in v1.7; older indexes lack symbol metadata

**How to avoid:**
- Skills should note symbol features require v1.7+ and reindexing
- Include fix: "Reindex with: `cocosearch index . --name <index>`"
- Check index version: `cocosearch stats <index>` shows if symbols available

**Warning signs:** Symbol filters work on some indexes but not others in same installation

**Source:** CocoSearch v1.7 release (Phase 29-30), symbol-aware indexing requirements

## Code Examples

Verified patterns from official sources:

### Claude Code MCP Configuration (stdio)

```bash
# Via Claude CLI (recommended)
claude mcp add --transport stdio --scope user \
  --env COCOSEARCH_DATABASE_URL=postgresql://cocoindex:cocoindex@localhost:5432/cocoindex \
  cocosearch -- uv run --directory /absolute/path/to/cocosearch cocosearch mcp

# Via ~/.claude.json
{
  "mcpServers": {
    "cocosearch": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/cocosearch", "cocosearch", "mcp"],
      "env": {
        "COCOSEARCH_DATABASE_URL": "postgresql://cocoindex:cocoindex@localhost:5432/cocoindex"
      }
    }
  }
}
```

**Source:** CocoSearch README.md lines 458-497

### OpenCode MCP Configuration

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "cocosearch": {
      "type": "local",
      "command": ["uv", "run", "--directory", "/absolute/path/to/cocosearch", "cocosearch", "mcp"],
      "enabled": true,
      "environment": {
        "COCOSEARCH_DATABASE_URL": "postgresql://cocoindex:cocoindex@localhost:5432/cocoindex"
      }
    }
  }
}
```

**Key differences from Claude Code:**
- `"type": "local"` explicit (not implicit)
- `command` is array (not separate command/args)
- `"environment"` (not `"env"`)
- `"enabled": true` required

**Source:** CocoSearch README.md lines 544-589

### Installation Verification

```bash
# 1. Install UV (macOS/Linux)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Install CocoSearch
uv pip install cocosearch

# 3. Verify installation
cocosearch --version  # Should show version number

# 4. Verify MCP connection (after config)
cocosearch stats  # Should connect to database, show indexes or "No indexes found"
```

**Source:** [UV installation docs](https://docs.astral.sh/uv/getting-started/installation/), CocoSearch README.md

### Routing Decision Examples

```markdown
## Decision Tree

**Query: "find user authentication"**
→ Use CocoSearch: Intent-based, needs semantic understanding
→ Command: `cocosearch search "user authentication" --symbol-type function`

**Query: "find getUserById"**
→ Use grep first: Exact identifier, faster with literal match
→ Command: `rg "getUserById"`
→ If nothing found or need context: Try CocoSearch with hybrid
→ Command: `cocosearch search "getUserById" --hybrid`

**Query: "where is User class defined?"**
→ Use IDE: Go-to-definition (Cmd+Click / F12)
→ Fallback CocoSearch: `cocosearch search "User" --symbol-type class`

**Query: "all files importing React"**
→ Use grep: Exact text pattern across files
→ Command: `rg "import.*React"`

**Query: "error handling patterns in API code"**
→ Use CocoSearch: Semantic + location-aware
→ Command: `cocosearch search "error handling" --lang typescript`
```

**Source:** Research on [grep vs semantic search patterns](https://medium.com/@vanshkharidia7/rag-retrieval-beyond-semantic-search-day-1-grep-599cec898a68), [routing best practices](https://www.aifreeapi.com/en/posts/claude-code-tool-search)

### Context Expansion Example

```bash
# Smart context (default) - expands to function boundary
cocosearch search "database connection" --pretty

# Output shows entire function containing match (up to 50 lines)
# [1] src/db/connect.py:45-78 (score: 0.89)
#     def establish_connection(config: dict) -> Connection:
#         """Create database connection with retry logic."""
#         # [full function body shown]

# Fixed context - exact line counts
cocosearch search "database connection" -C 5 --no-smart --pretty

# Output shows match + exactly 5 lines before/after
# [1] src/db/connect.py:50-60 (score: 0.89)
#     # [5 lines before]
#         conn = psycopg2.connect(**config)
#     # [5 lines after]
```

**Source:** CocoSearch README.md lines 822-863, context expansion feature (v1.7)

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| pip for package install | UV for Python tooling | 2024-2025 | 10-100x faster installs; single tool replaces pip, pipx, venv |
| Custom .md files in .claude/commands/ | Agent Skills (.claude/skills/SKILL.md) | Dec 2025 | Open standard, auto-triggering, cross-platform (Claude Code, OpenCode, Codex CLI) |
| Vector-only semantic search | Hybrid search (vector + keyword) | CocoSearch v1.7 (Feb 2026) | Better identifier matching while preserving semantic understanding |
| Symbol-agnostic indexing | Symbol-aware with filtering | CocoSearch v1.7 (Feb 2026) | Can filter to functions/classes, disambiguate with qualified names |
| Fixed context windows | Smart context expansion | CocoSearch v1.7 (Feb 2026) | Shows enclosing function/class automatically, up to 50 lines |

**Deprecated/outdated:**
- **pip/pipx for CocoSearch install**: UV is now standard, faster, simpler
- **.claude/commands/ for skills**: Still works but skills/ preferred for auto-triggering and bundled resources
- **Pure semantic search queries**: Hybrid search auto-enables for identifiers, better results

**Source:** [UV launch 2024](https://astral.sh/blog/uv), [Agent Skills announcement Dec 2025](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview), CocoSearch v1.7 features

## Open Questions

1. **Skill testing in ambiguous scenarios**
   - What we know: Phase 36 CONTEXT.md mentions "Test skill routing with ambiguous queries" as research flag
   - What's unclear: Specific test queries for validation (e.g., "find config" could mean grep config files OR CocoSearch semantic search)
   - Recommendation: Include 5+ ambiguous query examples in PLAN.md verification tasks (e.g., "find API endpoints" → both grep "GET|POST" and CocoSearch "API route handlers" are valid, skill should guide choice)

2. **Docker setup mention in skills**
   - What we know: CONTEXT.md says "UV only — no Docker mention in skills (advanced setup)"
   - What's unclear: Should skills mention Docker exists at all, or completely omit?
   - Recommendation: Omit Docker entirely from skills; README.md covers Docker setup comprehensively. Skills focus on UV-based local install as primary path.

3. **Skill directory location preference**
   - What we know: Skills can be global (~/.claude/skills/) or project-local (.claude/skills/)
   - What's unclear: Which should be recommended default for CocoSearch skills?
   - Recommendation: Recommend project-local (.claude/skills/) since CocoSearch setup is per-codebase and skills commit to version control for team sharing. Mention global option as alternative.

4. **Output truncation style for examples**
   - What we know: CONTEXT.md says show "expected output format (query + truncated output)" for 5+ examples
   - What's unclear: Truncate after N lines? Show "..." for omission? Include score thresholds?
   - Recommendation: Show first result fully (10-15 lines), second result truncated with "[...]", include score (0.89) and file path. Mirrors actual CLI output format.

## Sources

### Primary (HIGH confidence)

- [Claude Code Skills Documentation](https://code.claude.com/docs/en/skills) - Official spec, skill structure, frontmatter, progressive disclosure
- [Agent Skills Specification](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview) - Open standard, cross-platform compatibility
- [CocoSearch README.md](file:///Users/fedorzhdanov/GIT/personal/coco-s/README.md) - MCP configuration (Claude Code lines 458-497, OpenCode lines 544-589), features documentation
- [UV Documentation](https://docs.astral.sh/uv/getting-started/installation/) - Installation commands, uv pip vs pip differences
- CocoSearch CLI help output - Verified command flags, options, defaults

### Secondary (MEDIUM confidence)

- [Agent Skills Deep Dive](https://leehanchung.github.io/blogs/2025/10/26/claude-skills-deep-dive/) - SKILL.md patterns, progressive disclosure examples
- [OpenCode Skills Guide](https://blog.devgenius.io/writing-opencode-agent-skills-a-practical-guide-with-examples-870ff24eec66) - OpenCode-specific config format differences
- [Claude Code Tool Search Guide](https://www.aifreeapi.com/en/posts/claude-code-tool-search) - Grep vs semantic search routing patterns
- [Switching to UV Guide](https://blog.appsignal.com/2025/09/24/switching-from-pip-to-uv-in-python-a-comprehensive-guide.html) - UV benefits, migration from pip

### Tertiary (LOW confidence)

- [Semantic Search vs Grep](https://medium.com/@vanshkharidia7/rag-retrieval-beyond-semantic-search-day-1-grep-599cec898a68) - General patterns, not CocoSearch-specific
- [ripgrep vs grep comparison](https://www.codeant.ai/blogs/ripgrep-vs-grep) - Performance benchmarks, use case differences

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Agent Skills spec is official, UV widely adopted
- Architecture: HIGH - Claude Code docs authoritative, verified with CocoSearch README
- Pitfalls: HIGH - Drawn from official troubleshooting docs and observed issues (symbol filter errors, transport mismatches)
- Routing guidance: MEDIUM - Synthesized from multiple sources, not single authoritative decision tree

**Research date:** 2026-02-05
**Valid until:** 2026-03-05 (30 days - stable domain, Agent Skills spec frozen, UV stable)

---

**Ready for planning:** Yes. Planner can create tasks for two SKILL.md files (Claude Code, OpenCode) with clear structure template, routing examples, and verification steps.
