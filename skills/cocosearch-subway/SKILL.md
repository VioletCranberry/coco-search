---
name: cocosearch-subway
description: Use when the user wants to visualize codebase structure as an interactive London Underground-style subway map. AI-generated visualization using CocoSearch tools for exploration.
---

# Code Underground Map

Generate an interactive London Underground-style subway map of a codebase. Lines represent modules/directories, stations are key symbols (functions, classes), and transfers show cross-module connections.

## Pre-flight Check

Before generating the map, verify we have a usable index.

**I'll run:**

1. **Check for project config first:** Look for `cocosearch.yaml` in the project root. If it exists and has an `indexName` field, use that as the index name. **This is critical** -- the MCP `index_codebase` tool auto-derives names from the directory path if `index_name` is not specified, which may not match the configured name.
2. `list_indexes()` -- Check what indexes exist
3. `index_stats(index_name="<configured-name>")` -- Check index health, especially that it has symbols (requires v1.7+ index)

**What to look for:**

- **No index found:** Offer to run `index_codebase(path, index_name="<configured-name>")` first
- **Index exists but no symbols:** The subway map needs symbol data. Suggest re-indexing.
- **Index fresh with symbols:** Ready to explore and generate

## Step 1 -- Explore the Codebase

Use CocoSearch tools to understand the codebase structure before generating the map.

**I'll run multiple searches to discover:**

1. **Module structure:** Use `search_code("module entry point main init", index_name="<name>", symbol_type=["function", "class"])` to find key entry points
2. **Top-level directories:** Use `index_stats(index_name="<name>")` to see language distribution and file counts -- this reveals the major code areas
3. **Key symbols per area:** For each major module/directory, run `search_code("<module-name> core functionality", index_name="<name>", symbol_type=["function", "class", "method"], limit=15)` to discover the important symbols
4. **Cross-module connections:** Search for imports/references between modules: `search_code("import from <module>", index_name="<name>")` to find where modules connect

**Goal:** Build a mental model of:
- 4-8 "lines" (major modules/directories)
- 5-12 "stations" per line (key symbols)
- Transfer stations where modules connect (shared dependencies, cross-module calls)

## Step 2 -- Generate the Map HTML

Write a self-contained HTML file with an interactive London Underground-style subway map.

**Output file:** Write to a temp file (e.g., `/tmp/cocosearch-subway-<index-name>.html`) or to the project directory if the user prefers.

**Design requirements:**

### Visual Style -- London Underground Aesthetic
- **Dark background** (`#1a1a2e` or similar dark navy) with light-colored lines
- **Lines:** Smooth, rounded paths with distinct colors per module. Use the classic Underground color palette:
  - Central (red `#DC241F`), Victoria (light blue `#0098D4`), Jubilee (silver `#A0A5A9`), Northern (black/dark `#000000` on dark bg use `#CCCCCC`), Piccadilly (dark blue `#003688`), District (green `#007D32`), Circle (yellow `#FFD300`), Metropolitan (magenta `#9B0056`)
- **Stations:** Small circles (8px) on the line. Filled white for regular stations, larger (12px) with a ring for interchange/transfer stations
- **Station labels:** Small, clean sans-serif text. Rotate labels to avoid overlap
- **Line names:** Displayed in a legend matching Underground signage style (colored roundel + line name)

### Layout
- Lines run primarily horizontally or at 45-degree angles (like real Underground maps)
- Avoid crossing lines where possible
- Transfer stations should be clearly marked where lines intersect
- Use a grid-like layout -- the map should feel spatial and navigable, not like a random graph

### Interactivity (D3.js via CDN)
- **Pan and zoom** (d3-zoom)
- **Hover on station:** Show tooltip with symbol type, file path, and a brief description
- **Click on station:** Highlight the line(s) it belongs to
- **Legend:** Clickable -- toggle line visibility

### Technical
- Self-contained HTML with inline CSS and JS
- Load D3.js v7 from CDN (`https://d3js.org/d3.v7.min.js`)
- All data embedded as inline JSON (no API calls needed)
- Should work by opening the file directly in a browser (file:// protocol)

**I'll share with the user:**

- The file path to the generated HTML
- How to open it: "Open `/tmp/cocosearch-subway-<name>.html` in your browser"
- Summary: number of lines, stations, and transfers
- Brief interpretation of the map structure

## Step 3 -- Deep Dive (Optional)

If the user asks about any station or line, provide full context.

**I'll run:**

- `search_code("<station-name>", index_name="<configured-name>", symbol_name="<station-name>", smart_context=True)`

**I'll share:**

- The full function/class implementation
- What it does and how it fits into the codebase architecture
- Why it connects to other modules (if it's a transfer station)
