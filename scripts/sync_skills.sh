#!/usr/bin/env bash
# Sync skills from skills/ (source of truth) to src/cocosearch/skills/ (bundled package).
# Copies cocosearch-*/SKILL.md files, preserving __init__.py and ignoring README.md.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC_DIR="$REPO_ROOT/skills"
DST_DIR="$REPO_ROOT/src/cocosearch/skills"

errors=0
synced=0

for skill_dir in "$SRC_DIR"/cocosearch-*/; do
    skill_name="$(basename "$skill_dir")"
    skill_file="$skill_dir/SKILL.md"

    if [ ! -f "$skill_file" ]; then
        echo "ERROR: $skill_dir is missing SKILL.md" >&2
        errors=$((errors + 1))
        continue
    fi

    target_dir="$DST_DIR/$skill_name"
    mkdir -p "$target_dir"
    cp "$skill_file" "$target_dir/SKILL.md"
    synced=$((synced + 1))
    echo "  synced $skill_name/SKILL.md"
done

echo ""
echo "Synced $synced skill(s) from skills/ -> src/cocosearch/skills/"

if [ "$errors" -gt 0 ]; then
    echo "ERROR: $errors skill directory(ies) missing SKILL.md" >&2
    exit 1
fi
