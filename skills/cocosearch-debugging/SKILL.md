---
name: cocosearch-debugging
description: Use when debugging an error, unexpected behavior, or tracing how code flows through a system. Guides root cause analysis using CocoSearch semantic and symbol search.
---

# Debugging with CocoSearch

## Pre-flight Check

1. Read `cocosearch.yaml` for `indexName` (critical -- use this for all operations)
2. `list_indexes()` to confirm project is indexed
3. `index_stats(index_name="<configured-name>")` to check freshness
- No index → offer to index before debugging
- Stale (>7 days) → warn: "Index is X days old -- results may not reflect recent changes. Want me to reindex first?"

## Step 1: Understand the Symptom

Parse what the user is reporting. Different inputs require different extraction:

**If error message or exception:**

- Extract error type: `ValueError`, `TypeError`, `NullPointerException`, etc.
- Extract key identifiers: function names, class names, variable names from stack trace
- Extract semantic context: what operation was being performed?

**If unexpected behavior:**

- Extract what's happening vs. what should happen
- Extract any mentioned functions, files, or data flows
- Identify the symptom's observable effects

**If user provides stack trace:**

- Parse the call stack: which functions are involved?
- Identify entry point (top of stack) and failure point (bottom of stack)
- Extract file paths and line numbers if present

**Store extracted information:**

- **Identifiers:** List of function names, class names, variables mentioned
- **Semantic query:** Natural language description of the problem
- **Suspected area:** File paths or module names mentioned

Present back to user: "I see the error is `<error-type>` in `<function-name>` when `<operation>`. Let me search for where this originates."

## Step 2: Cast Wide Net

**This is the critical discovery phase.** Run both semantic and symbol searches simultaneously to find the strongest leads.

**Semantic search for symptom:**

```
search_code(
    query="<user's symptom description>",
    use_hybrid_search=True,
    smart_context=True,
    limit=10
)
```

**Symbol search for each identifier:**
For each identifier extracted from the symptom (function names, class names, error types):

```
search_code(
    query="<identifier>",
    symbol_name="<identifier>*",
    use_hybrid_search=True,
    smart_context=True,
    limit=5
)
```

**Synthesize results:**

- Which files appear in BOTH semantic and symbol searches? These are the strongest candidates.
- Which functions have high scores in both searches? Likely the root cause.
- Any files that appear in symbol search but NOT semantic? Might be related but not the origin.

**Present findings:**
"Based on the symptom, I found these strong leads:

- `<file-path>` contains `<function-name>` (appears in both semantic and symbol searches)
- `<other-file>` has related code but lower confidence
- Total of X files mention this identifier

The issue likely originates in `<strongest-candidate>`. Want me to trace how code flows through this area?"

**Branch based on findings:**

- **Clear origin found:** Proceed to Step 3 (trace the call chain)
- **Multiple candidates (3+):** Ask user which area to focus on first
- **Nothing relevant found:** Try broader search terms:
  - Remove specifics, search for general operation: "database connection" instead of "connect_to_postgres"
  - Search for error handling patterns: "error handling", "exception catch"
  - Search by file type: add `language="python"` if language known

## Step 3: Trace the Call Chain (Adaptive Depth)

**Start shallow, go deeper on request.** Default to ONE HOP first.

**One-hop trace:**

1. **Find the suspected origin function:**

```
search_code(
    query="<function-name>",
    symbol_name="<function-name>",
    symbol_type="function",
    smart_context=True
)
```

2. **Find immediate callers:**

```
search_code(
    query="calls <function-name>",
    use_hybrid_search=True,
    limit=10
)
```

3. **Find immediate callees (what it calls):**
   Look at the function body from step 1, extract called functions, then search for each:

```
search_code(
    query="<called-function-name>",
    symbol_name="<called-function-name>",
    smart_context=True
)
```

**Present one-hop view:**
"Function `<function-name>` at `<file>:<line>`:

- Called by: `<caller-A>`, `<caller-B>`, `<caller-C>`
- Calls: `<callee-D>`, `<callee-E>`

Here's the function body:

```
[full function code from smart_context]
```

**Checkpoint with user:**
"This is one level deep. Want me to trace deeper into any of these callers or callees?"

**If user wants deeper trace:**

- Ask which direction: "Trace upward (who calls the callers) or downward (what the callees call)?"
- Repeat the one-hop search for the selected function
- Present the expanded view
- Repeat until root cause is identified or user says stop

**Trace strategies:**

- **For errors in leaf functions:** Trace UPWARD to find where bad data originates
- **For errors in entry points:** Trace DOWNWARD to find where the error is thrown
- **For flow understanding:** Trace both directions, building a call graph

**Stop conditions:**

- User says "that's enough"
- Found the root cause (code that's clearly wrong)
- Hit architectural boundaries (external API calls, database, file system)

## Step 4: Root Cause Analysis

**Present the root cause clearly:**

1. **What's wrong:**
   - Show the problematic code with full context (`smart_context=True`)
   - Explain why this code causes the symptom
   - Highlight the specific line or logic error

2. **Where it is:**
   - File path and line number
   - Function/class containing the issue
   - Context of surrounding code (what this function's purpose is)

3. **Why it causes the symptom:**
   - Trace the logic: "When X happens, this code does Y, but should do Z"
   - Connect back to user's original symptom
   - Explain the propagation path if error bubbles up

**Example root cause presentation:**
"Root cause found in `src/auth/validator.py:45` in function `validate_token`:

```python
def validate_token(token: str) -> User:
    decoded = jwt.decode(token, verify=False)  # <-- Problem here
    return User.from_dict(decoded)
```

The issue: `verify=False` disables signature verification, allowing any malformed JWT to pass. This causes the `KeyError` you saw because the fake token doesn't have required fields.

This explains your symptom: when an attacker sends a crafted JWT, it's accepted without validation, then fails when trying to extract user data."

**Ask about fix suggestions (do NOT auto-suggest):**
"Want me to suggest a fix based on how this is handled elsewhere in the codebase?"

**If user wants fix suggestions:**

1. **Search for correct patterns:**

```
search_code(
    query="JWT token validation with signature verification",
    use_hybrid_search=True,
    language="python"
)
```

2. **Find similar fixed code:**

```
search_code(
    query="jwt.decode verify signature",
    use_hybrid_search=True
)
```

3. **Present fix based on established patterns:**
   "Here's how it's done correctly in `src/api/auth.py:23`:

```python
def validate_api_token(token: str) -> User:
    try:
        decoded = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return User.from_dict(decoded)
    except jwt.InvalidTokenError as e:
        raise AuthenticationError(f"Invalid token: {e}")
```

Suggested fix for `validator.py:45`:

1. Add signature verification with `SECRET_KEY`
2. Specify allowed algorithms
3. Add exception handling for invalid tokens

Want me to show the exact code change?"

**If user doesn't want fixes:**
"Root cause identified. Let me know if you need anything else!"

## Advanced Debugging Patterns

**Pattern 1: Symbol type filtering for specific searches**

When debugging object-oriented code:

```
# Find all classes related to authentication
search_code(query="authentication", symbol_type="class")

# Find all methods that handle errors
search_code(query="error handler", symbol_type=["method", "function"])
```

**Pattern 2: Language filtering for polyglot codebases**

When error is language-specific:

```
# Python-specific async issue
search_code(query="async await deadlock", language="python")

# TypeScript type error
search_code(query="type mismatch interface", language="typescript")
```

**Pattern 3: Symbol name wildcards for related functions**

When tracing naming conventions:

```
# Find all handler functions
search_code(query="request processing", symbol_name="*Handler")

# Find all validator methods
search_code(query="validation", symbol_name="validate*")
```

**Pattern 4: Context expansion for full understanding**

When you need complete function bodies:

```
# Get full function context (default with smart_context=True)
search_code(query="database transaction", smart_context=True)

# Get fixed context lines
search_code(query="error handling", context_before=10, context_after=10)
```

**Pattern 5: Pipeline analysis for search debugging**

When search results are unexpected, use `analyze_query` to see the full pipeline breakdown:

```
# See why a query returns specific results
analyze_query(query="getUserById")
```

Returns stage-by-stage diagnostics: identifier detection, hybrid mode decision, vector/keyword search results, RRF fusion breakdown (both/semantic-only/keyword-only counts), definition boost effects, and per-stage timings.

For installation instructions, see `skills/README.md`.
