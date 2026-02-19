# CocoSearch Skills

Reusable AI coding assistant skills that leverage CocoSearch's semantic and symbol-aware search for structured codebase workflows.

## Available Skills

| Skill | Description | Interactive? |
|-------|-------------|:---:|
| [cocosearch-quickstart](./cocosearch-quickstart/SKILL.md) | First-time setup: infrastructure check, indexing, and verification | Yes |
| [cocosearch-onboarding](./cocosearch-onboarding/SKILL.md) | Guided tour of a new codebase: architecture, layers, patterns | Yes |
| [cocosearch-explore](./cocosearch-explore/SKILL.md) | Codebase exploration with two modes: autonomous (subagent/plan mode) and interactive ("how does X work?") | Both |
| [cocosearch-debugging](./cocosearch-debugging/SKILL.md) | Root cause analysis: symptom parsing, call tracing, fix suggestions | Yes |
| [cocosearch-refactoring](./cocosearch-refactoring/SKILL.md) | Safe refactoring: full impact analysis, dependency mapping, step-by-step execution | Yes |
| [cocosearch-new-feature](./cocosearch-new-feature/SKILL.md) | Add new functionality: find patterns, match conventions, integrate | Yes |
| [cocosearch-subway](./cocosearch-subway/SKILL.md) | Visualize codebase as an interactive London Underground-style subway map | Yes |
| [cocosearch-add-language](./cocosearch-add-language/SKILL.md) | Add language support: handlers, symbol extraction, context expansion | Yes |
| [cocosearch-add-grammar](./cocosearch-add-grammar/SKILL.md) | Add grammar handler: domain-specific formats within a base language | Yes |

## Installation

### Claude Code Plugin (Recommended)

```bash
claude plugin marketplace add VioletCranberry/coco-s
claude plugin install cocosearch@cocosearch
```

This automatically configures the MCP server and all 9 skills. No symlinks or manual setup needed.

### Claude Code (project-local)

Symlink skills from a cloned CocoSearch repo into your project:

```bash
mkdir -p .claude/skills
for skill in cocosearch-onboarding cocosearch-refactoring cocosearch-debugging cocosearch-quickstart cocosearch-explore cocosearch-new-feature cocosearch-subway cocosearch-add-language cocosearch-add-grammar; do
    ln -sfn "../../skills/$skill" ".claude/skills/$skill"
done
```

### Claude Code (global)

Copy skills to your global Claude config:

```bash
for skill in cocosearch-onboarding cocosearch-refactoring cocosearch-debugging cocosearch-quickstart cocosearch-explore cocosearch-new-feature cocosearch-subway cocosearch-add-language cocosearch-add-grammar; do
    mkdir -p ~/.claude/skills/$skill
    cp skills/$skill/SKILL.md ~/.claude/skills/$skill/SKILL.md
done
```

### OpenCode

Copy skills to your OpenCode config:

```bash
for skill in cocosearch-onboarding cocosearch-refactoring cocosearch-debugging cocosearch-quickstart cocosearch-explore cocosearch-new-feature cocosearch-subway cocosearch-add-language cocosearch-add-grammar; do
    mkdir -p ~/.config/opencode/skills/$skill
    cp skills/$skill/SKILL.md ~/.config/opencode/skills/$skill/SKILL.md
done
```

After installation, restart your AI coding assistant or run the skill activation command for your platform.

## Common Search Tips

These tips apply across all CocoSearch skills:

- **Always use `use_hybrid_search=True`** -- combines semantic understanding with keyword precision via RRF fusion. Essential for both concept discovery and identifier lookup.
- **Always use `smart_context=True`** -- expands results to full function/class boundaries using Tree-sitter. Gives you complete code units, not truncated snippets.
- **Use `symbol_name` for precision** -- when you know the identifier, use `symbol_name="<name>*"` with glob patterns to catch variants (e.g., `User*` finds `User`, `UserService`, `UserProfile`).
- **Use `symbol_type` for structural searches** -- filter to `"function"`, `"class"`, `"method"`, or `"interface"` to reduce noise when looking for specific code structures.
- **Use `language` for polyglot codebases** -- add `language="python"` (or any supported language) to scope results when debugging language-specific issues.
- **Be specific in queries** -- `"search query embedding generation"` finds more relevant results than `"how search works"`.
- **Follow identifiers across hops** -- when a function body references another function, search for it by name using `symbol_name` for precision. Use semantic queries for intent-based discovery.
