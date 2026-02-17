# MCP Tools Reference

CocoSearch provides 6 Model Context Protocol (MCP) tools for semantic code search and index management. These tools enable AI agents and LLMs to search indexed codebases, manage indexes, analyze search pipelines, and retrieve statistics programmatically.

**Available transports:** stdio, SSE, streamable HTTP

---

## search_code

Search indexed code using natural language queries. Returns code chunks ranked by semantic similarity, with optional context expansion to enclosing function/class boundaries. Performs automatic project detection using MCP Roots when available, falling back to the `index_name` parameter or the working directory.

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| query | string | Yes | - | Natural language search query |
| index_name | string \| null | No | null | Name of the index to search. If not provided, auto-detects from current working directory. |
| limit | integer | No | 10 | Maximum results to return |
| language | string \| null | No | null | Filter by language (e.g., python, typescript, hcl, dockerfile, bash). Aliases: terraform=hcl, shell/sh=bash. Comma-separated for multiple. |
| use_hybrid_search | boolean \| null | No | null | Enable hybrid search (vector + keyword matching). None=auto (enabled for identifier patterns like camelCase/snake_case), True=always use hybrid, False=vector-only |
| symbol_type | string \| array\<string\> \| null | No | null | Filter by symbol type. Single: 'function', 'class', 'method', 'interface'. Array: ['function', 'method'] for OR filtering. |
| symbol_name | string \| null | No | null | Filter by symbol name pattern (glob). Examples: 'get*', 'User*Service', '*Handler'. Case-insensitive matching. |
| context_before | integer \| null | No | null | Number of lines to show before each match. Overrides smart context expansion when specified. |
| context_after | integer \| null | No | null | Number of lines to show after each match. Overrides smart context expansion when specified. |
| smart_context | boolean | No | true | Expand context to enclosing function/class boundaries. Enabled by default. Set to False for exact line counts only. |

### Natural Language Example

Search for authentication logic in a Python project:

"Find JWT token validation functions"

This will search the auto-detected index for code chunks related to JWT token validation, automatically using hybrid search since the query contains the identifier pattern "JWT".

### JSON Request

```json
{
  "query": "JWT token validation",
  "index_name": "my-api-server",
  "limit": 5,
  "language": "python",
  "use_hybrid_search": true,
  "symbol_type": "function",
  "context_before": 3,
  "context_after": 3,
  "smart_context": false
}
```

### JSON Response

```json
[
  {
    "file_path": "/Users/dev/my-api/auth/jwt.py",
    "start_line": 45,
    "end_line": 62,
    "score": 0.89,
    "content": "def validate_jwt_token(token: str) -> dict:\n    \"\"\"Validate JWT and return claims.\"\"\"\n    try:\n        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])\n        return payload\n    except jwt.ExpiredSignatureError:\n        raise AuthError('Token expired')\n    except jwt.InvalidTokenError:\n        raise AuthError('Invalid token')",
    "block_type": "function",
    "hierarchy": "validate_jwt_token",
    "language_id": "python",
    "symbol_type": "function",
    "symbol_name": "validate_jwt_token",
    "symbol_signature": "def validate_jwt_token(token: str) -> dict",
    "match_type": "both",
    "vector_score": 0.87,
    "keyword_score": 0.91,
    "context_before": "import jwt\nfrom .exceptions import AuthError\n\n",
    "context_after": "\n\ndef refresh_token(user_id: int) -> str:\n    return generate_jwt(user_id)"
  }
]
```

**Note:** Response may include a search_context header (when auto-detecting index) and a staleness_warning footer (when index is older than 7 days).

---

## analyze_query

Analyze the search pipeline for a query with stage-by-stage diagnostics. Runs the same pipeline as `search_code` but captures diagnostics at each stage: query analysis, mode selection, cache status, vector search, keyword search, RRF fusion, definition boost, filtering, and per-stage timing breakdown.

Use this to understand WHY a query returns specific results.

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| query | string | Yes | - | Search query to analyze |
| index_name | string \| null | No | null | Name of the index. Auto-detects if not provided. |
| limit | integer | No | 10 | Maximum results to return |
| language | string \| null | No | null | Filter by language. Comma-separated for multiple. |
| use_hybrid_search | boolean \| null | No | null | None=auto, True=always hybrid, False=vector-only |
| symbol_type | string \| array\<string\> \| null | No | null | Filter by symbol type |
| symbol_name | string \| null | No | null | Filter by symbol name pattern (glob) |

### Natural Language Example

"Why does searching for getUserById not return the right function?"

### JSON Request

```json
{
  "query": "getUserById",
  "index_name": "my-api-server"
}
```

### JSON Response

```json
{
  "query_analysis": {
    "original_query": "getUserById",
    "has_identifier": true,
    "normalized_keyword_query": "getUserById get User By Id"
  },
  "search_mode": {
    "mode": "hybrid",
    "reason": "Auto-detected identifier pattern in query",
    "use_hybrid_flag": null,
    "has_content_text_column": true,
    "has_identifier_pattern": true
  },
  "cache": {
    "checked": false,
    "hit": false,
    "hit_type": "miss",
    "cache_key_prefix": "a1b2c3d4e5f67890"
  },
  "vector_search": {
    "result_count": 12,
    "top_score": 0.872,
    "bottom_score": 0.534
  },
  "keyword_search": {
    "executed": true,
    "normalized_query": "getUserById get User By Id",
    "result_count": 8,
    "top_ts_rank": 0.098
  },
  "fusion": {
    "executed": true,
    "k_constant": 60,
    "vector_only_count": 8,
    "keyword_only_count": 4,
    "both_count": 4,
    "total_fused": 16
  },
  "definition_boost": {
    "executed": true,
    "boost_multiplier": 2.0,
    "boosted_count": 3,
    "rank_changes": 1
  },
  "filtering": {
    "language_filter": null,
    "symbol_type_filter": null,
    "symbol_name_filter": null,
    "min_score": 0.0,
    "pre_filter_count": 10,
    "post_filter_count": 10
  },
  "timings": {
    "query_analysis_ms": 0.1,
    "cache_check_ms": 0.0,
    "embedding_ms": 0.0,
    "vector_search_ms": 12.3,
    "keyword_search_ms": 2.1,
    "rrf_fusion_ms": 0.3,
    "definition_boost_ms": 0.1,
    "total_ms": 15.2
  },
  "results": []
}
```

**Note:** The `results` array contains full `SearchResult` objects (same format as `search_code`). Cache is always bypassed for analysis.

---

## list_indexes

List all available code indexes. Returns index names and their corresponding table names.

### Parameters

None

### Natural Language Example

Get all indexed codebases to see what's available for searching.

### JSON Request

```json
{}
```

### JSON Response

```json
[
  {
    "name": "my-api-server",
    "table_name": "cocosearch_my_api_server"
  },
  {
    "name": "frontend-app",
    "table_name": "cocosearch_frontend_app"
  },
  {
    "name": "shared-utils",
    "table_name": "cocosearch_shared_utils"
  }
]
```

---

## index_stats

Get statistics for code indexes. Returns file count, chunk count, storage size, language distribution, symbol counts, parse health, and staleness information.

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| index_name | string \| null | No | null | Name of the index (omit for all indexes) |
| include_failures | boolean | No | false | Include per-language parse failure details in response |

### Natural Language Example

Check how many files and chunks are indexed in "my-api-server" and when it was last updated.

### JSON Request (Single Index)

```json
{
  "index_name": "my-api-server"
}
```

### JSON Response (Single Index)

```json
{
  "name": "my-api-server",
  "file_count": 342,
  "chunk_count": 1523,
  "storage_size": 8421376,
  "storage_size_pretty": "8.0 MB",
  "created_at": "2026-01-15T10:30:00Z",
  "updated_at": "2026-02-05T14:22:00Z",
  "is_stale": false,
  "staleness_days": 1,
  "languages": [
    {
      "language": "python",
      "file_count": 180,
      "chunk_count": 890,
      "line_count": 12500
    },
    {
      "language": "typescript",
      "file_count": 120,
      "chunk_count": 520,
      "line_count": 8200
    },
    {
      "language": "hcl",
      "file_count": 42,
      "chunk_count": 113,
      "line_count": 1800
    }
  ],
  "symbols": {
    "function": 450,
    "class": 85,
    "method": 320,
    "interface": 25
  },
  "parse_stats": {
    "parse_health_pct": 95.2,
    "total_files": 342,
    "total_ok": 325,
    "by_language": {
      "python": {
        "files": 180,
        "ok": 175,
        "partial": 3,
        "error": 2,
        "no_grammar": 0
      },
      "typescript": {
        "files": 120,
        "ok": 115,
        "partial": 3,
        "error": 2,
        "no_grammar": 0
      }
    }
  },
  "warnings": []
}
```

When `include_failures` is true, the response includes a `parse_failures` array with file paths and error details for each failed parse:

```json
{
  "parse_failures": [
    {
      "file_path": "src/legacy/parser.py",
      "language": "python",
      "parse_status": "error",
      "error_message": "tree-sitter parse failed"
    }
  ]
}
```

### JSON Request (All Indexes)

```json
{}
```

### JSON Response (All Indexes)

```json
[
  {
    "name": "my-api-server",
    "file_count": 342,
    "chunk_count": 1523,
    "storage_size": 8421376,
    "storage_size_pretty": "8.0 MB",
    "created_at": "2026-01-15T10:30:00Z",
    "updated_at": "2026-02-05T14:22:00Z",
    "is_stale": false,
    "staleness_days": 1,
    "languages": [
      {
        "language": "python",
        "file_count": 180,
        "chunk_count": 890,
        "line_count": 12500
      }
    ],
    "symbols": {
      "function": 450,
      "class": 85
    },
    "parse_stats": {
      "parse_health_pct": 97.8,
      "total_files": 180,
      "total_ok": 176,
      "by_language": {}
    },
    "warnings": []
  },
  {
    "name": "frontend-app",
    "file_count": 215,
    "chunk_count": 980,
    "storage_size": 5242880,
    "storage_size_pretty": "5.0 MB",
    "created_at": "2026-01-20T08:15:00Z",
    "updated_at": "2026-01-28T16:45:00Z",
    "is_stale": true,
    "staleness_days": 9,
    "languages": [
      {
        "language": "typescript",
        "file_count": 200,
        "chunk_count": 920,
        "line_count": 15200
      }
    ],
    "symbols": {
      "function": 320,
      "interface": 45
    },
    "parse_stats": {
      "parse_health_pct": 99.0,
      "total_files": 200,
      "total_ok": 198,
      "by_language": {}
    },
    "warnings": [
      "Index is stale (9 days since last update)"
    ]
  }
]
```

**Note:** The `line_count` field is `null` for indexes created before v1.7 (lacking the `content_text` column). The `symbols` field is an empty object `{}` for pre-v1.7 indexes.

---

## clear_index

Clear (delete) a code index. Permanently deletes all indexed data for a codebase, including the associated parse results tracking table. This operation cannot be undone.

**WARNING:** This is a destructive operation.

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| index_name | string | Yes | - | Name of the index to delete |

### Natural Language Example

Delete the "old-prototype" index that's no longer needed.

### JSON Request

```json
{
  "index_name": "old-prototype"
}
```

### JSON Response (Success)

```json
{
  "success": true,
  "message": "Index 'old-prototype' cleared successfully"
}
```

### JSON Response (Error)

```json
{
  "success": false,
  "error": "Index 'nonexistent' not found"
}
```

---

## index_codebase

Index a codebase directory for semantic search. Creates embeddings for all code files and stores them in the database. If the index already exists, it will be updated with any changes.

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| path | string | Yes | - | Path to the codebase directory to index |
| index_name | string \| null | No | null | Name for the index (auto-derived from path if not provided) |

### Natural Language Example

Index the codebase at "/Users/dev/my-new-project" so it can be searched.

### JSON Request

```json
{
  "path": "/Users/dev/my-new-project",
  "index_name": "my-new-project"
}
```

### JSON Response (Success)

```json
{
  "success": true,
  "index_name": "my-new-project",
  "path": "/Users/dev/my-new-project",
  "stats": {
    "files_added": 150,
    "files_removed": 0,
    "files_updated": 0
  }
}
```

### JSON Response (Error)

```json
{
  "success": false,
  "error": "Failed to index codebase: Path does not exist: /invalid/path"
}
```

**Note:** If `index_name` is not provided, it will be auto-derived from the path (e.g., "/Users/dev/my-api" becomes "my-api").

---

## Implementation

All tools are implemented in `src/cocosearch/mcp/server.py` using the FastMCP framework.

**Core search engine:** `src/cocosearch/search/query.py`
**Index management:** `src/cocosearch/management/__init__.py`
**Statistics:** `src/cocosearch/management/stats.py`
**Parse tracking:** `src/cocosearch/indexer/parse_tracking.py`
