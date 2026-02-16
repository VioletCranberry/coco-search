# How CocoSearch Works (Under the Hood)

This is the "explain it simply" version of the [Architecture Overview](architecture.md) and [Retrieval Logic](retrieval.md) docs. Same system, fewer formulas, more analogies.

## The Big Picture

CocoSearch does two things: **indexing** (reading your code and preparing it for search) and **searching** (finding the right code when you ask a question). Everything runs on your machine — no cloud, no external APIs, no data leaving your laptop.

Think of it like building a personal library catalog. First you organize all the books (indexing), then you use the catalog to find what you need (searching).

## Indexing: Building the Catalog

When you run `cocosearch index .`, here's what happens step by step:

### 1. Find the files

CocoSearch walks your project directory and picks up source files. It respects `.gitignore` (so `node_modules/` and build artifacts stay out) and your configured include/exclude patterns. Nothing clever here — just a filtered file listing.

### 2. Chop code into chunks

A 500-line file is too big to be a useful search result. So CocoSearch splits files into smaller pieces — roughly 1000 bytes each, with a 300-byte overlap between neighbors.

The splitting is not random. For languages like Python, Go, or Rust, it uses [Tree-sitter](https://tree-sitter.github.io/tree-sitter/) — a real parser that understands syntax. This means chunks break at function or class boundaries, not in the middle of an `if` statement. For languages without a Tree-sitter grammar (like HCL or Dockerfile), CocoSearch has custom regex-based splitters that know where the natural seams are.

The overlap exists so that context isn't lost at boundaries. If a function straddles two chunks, the overlap ensures both chunks have enough surrounding code to make sense.

### 3. Turn chunks into numbers

This is where the magic happens. Each chunk gets fed to an embedding model ([nomic-embed-text](https://ollama.com/library/nomic-embed-text), running locally via Ollama) that converts the text into a list of 768 numbers — a **vector**.

Before embedding, CocoSearch prepends the file path to the chunk text (e.g., `"File: .github/workflows/release.yaml\n<chunk text>"`). This gives the model context about *where* the code lives, so searching "release flow" can surface `release.yaml` even if the chunk text itself doesn't say "release". The filename prefix is only used for generating the embedding — the stored text stays clean.

What do these numbers mean? They're a compressed representation of the chunk's *meaning*. Two chunks that do similar things will produce similar vectors, even if the code looks completely different. A Python function that validates emails and a Go function that validates emails will end up with vectors that are close together in this 768-dimensional space.

You don't need to understand the math. The key insight is: **similar code = similar numbers**.

### 4. Prepare for keyword search

Vectors are great for "find code that *means* something like this," but sometimes you know the exact function name — `getUserById` — and you just want a direct match.

For this, CocoSearch also prepares each chunk for PostgreSQL's full-text search. It splits camelCase and snake_case identifiers into individual words (`getUserById` becomes `get`, `user`, `by`, `id` — plus the original `getuserbyid`), then appends tokens extracted from the file path (`.github/workflows/release.yaml` → `github`, `workflows`, `release`, `yaml`). All of this is stored as a tsvector. Think of it as building a keyword index alongside the semantic one — one that knows about both code content and file names.

### 5. Extract metadata

While processing chunks, CocoSearch also extracts structured information:

- **Language** — what programming language this file is written in
- **Symbol info** — for 13 supported languages, it runs Tree-sitter queries to figure out if a chunk contains a function definition, a class, a method, etc., and what it's called. This powers filters like `--symbol-type function` or `--symbol-name "User*"`
- **Block type** — for DevOps files (Terraform, Docker Compose, CI configs), what kind of block this is (a resource, a service, a job)

### 6. Store everything

All of this — the chunk's location (file path + byte offsets), its vector embedding, keyword index, and metadata — goes into PostgreSQL. The actual chunk text is *not* stored in the database. CocoSearch only stores where the chunk lives in the file and reads the real content at search time. This keeps the database lean and means results always reflect the current state of your code.

Two database indexes make search fast:
- A **vector index** (via pgvector) for finding similar embeddings
- A **GIN index** on the tsvector column for fast keyword lookups

That's it for indexing. Your code is now a searchable catalog of semantically meaningful, keyword-indexed chunks.

## Searching: Using the Catalog

When you search for `"authentication flow"` or `getUserById`, here's what happens:

### 1. Check the cache

Before doing any real work, CocoSearch checks if you've asked this (or something very similar) before. The cache has two levels:

- **Exact match** — same query, same filters, same everything? Return the cached results instantly.
- **Semantic match** — different wording but same meaning? If a previous query's vector is >= 95% similar to yours, the cached results are close enough. `"auth logic"` and `"authentication handler"` will often hit this.

Cache hits skip the entire search pipeline, including the embedding step.

### 2. Analyze the query

CocoSearch looks at your query to decide *how* to search. If it spots identifier patterns (camelCase, snake_case, PascalCase), it automatically enables **hybrid mode** — using both vector search and keyword search. Plain English queries like `"how does caching work"` use vector search alone, since keyword matching won't add much.

You can override this with `--hybrid` or `--no-hybrid`, but the auto-detection is right most of the time.

### 3. Vector search (the semantic part)

Your query gets embedded into a 768-number vector using the same model that embedded the chunks. Then PostgreSQL finds the chunks whose vectors are most similar (by cosine similarity — essentially measuring the angle between two vectors in 768-dimensional space).

This is what makes CocoSearch understand *meaning*. Searching for `"validate user input"` will find a function called `sanitize_form_data` even though they share zero keywords, because their vectors point in roughly the same direction.

### 4. Keyword search (the precision part)

If hybrid mode is on, CocoSearch also runs a PostgreSQL full-text search. Your query gets the same identifier-splitting treatment as during indexing (`getUserById` → `get user by id getuserbyid`), then matched against the tsvector column.

This catches things that semantic search can miss — especially exact identifier names. If you're looking for `HttpClient`, keyword search will find it even if the embedding model doesn't consider it semantically distinctive.

### 5. Merge the two result lists (RRF)

Now there are two ranked lists of results: one from vector search, one from keyword search. How do you combine them?

CocoSearch uses **Reciprocal Rank Fusion (RRF)**. The idea is simple: a result's score depends on where it appears in each list, not the raw similarity number. Being ranked #1 in a list is worth more than being ranked #50. If a result appears in *both* lists, it gets credit from both, which naturally pushes it to the top.

Why not just average the scores? Because cosine similarity scores and keyword relevance scores live on completely different scales. Rank position is the one thing they have in common, so that's what RRF uses.

A result that's #3 in vector search and #1 in keyword search will almost always outrank a result that's #1 in vector search but absent from keyword results. Being found by both strategies is a strong signal.

### 6. Boost definitions

After merging, CocoSearch gives a 2x score bump to chunks that are *definitions* (function declarations, class definitions) rather than usage sites. When you search for `UserService`, you probably want to see where it's defined, not every file that imports it.

### 7. Expand context

A raw chunk might be 15 lines from the middle of a function — not very useful on its own. CocoSearch expands each result to include the full enclosing function or class (up to 50 lines), again using Tree-sitter to find the boundaries. This way, results are immediately readable without needing a separate "open file" step.

### 8. Return and cache

The final ranked results are returned and stored in the cache for next time.

## Why Two Search Strategies?

Each strategy has a blind spot the other one covers:

| Scenario | Vector search | Keyword search |
|----------|:---:|:---:|
| `"how does authentication work"` | Finds it | Struggles (no keyword match) |
| `getUserById` | Might miss it (model doesn't "know" this identifier) | Finds it exactly |
| `"find the caching logic"` | Finds it | Partial (matches "caching" but misses synonyms) |
| `validate_email_address` | Finds similar validation code | Finds this exact function |

Hybrid search with RRF fusion gives you the best of both worlds. Semantic understanding for intent-based queries, keyword precision for identifier lookups.

## The Local-First Part

Everything described above runs on your machine:

- **Ollama** runs the embedding model locally — no API keys, no network calls
- **PostgreSQL + pgvector** stores and searches vectors locally — your code never touches a remote database
- **CocoSearch** orchestrates it all as a Python CLI — no daemon, no cloud service

The only external dependencies are Docker (to run Postgres and Ollama) and the embedding model weights (downloaded once by Ollama). After that, you could run CocoSearch on an airplane.

## Where to Go from Here

- [Architecture Overview](architecture.md) — component diagram, design decisions, module structure
- [Retrieval Logic](retrieval.md) — exact formulas, SQL queries, parameter values
- [Search Features](search-features.md) — all the search flags and filters you can use
- [Adding Languages](adding-languages.md) — how to add support for a new language
