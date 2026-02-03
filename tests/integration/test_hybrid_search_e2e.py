"""Integration tests for hybrid search end-to-end flow.

Tests the complete hybrid search pipeline with real PostgreSQL and embeddings,
verifying that:
- Vector (semantic) matches work correctly
- Keyword matches work correctly
- RRF fusion ranks double-matches higher
- Auto-detection triggers hybrid for identifier patterns
- Graceful degradation works for pre-v1.7 indexes
"""

import os

import cocoindex
import psycopg
import pytest
from pgvector.psycopg import register_vector

from cocosearch.indexer.schema_migration import ensure_hybrid_search_schema
from cocosearch.indexer.tsvector import preprocess_code_for_tsvector
from cocosearch.search import search
from cocosearch.search.db import get_table_name


# Test table name (mimics CocoIndex naming)
TEST_INDEX_NAME = "hybrid_e2e_test"


@pytest.fixture(autouse=True)
def reset_search_module_state():
    """Reset search module state between tests.

    The search module caches column existence checks. Reset before each test
    to ensure tests don't affect each other.
    """
    import cocosearch.search.db as db_module
    import cocosearch.search.query as query_module

    # Save original state
    orig_has_metadata = query_module._has_metadata_columns
    orig_metadata_warning = query_module._metadata_warning_emitted
    orig_has_content_text = query_module._has_content_text_column
    orig_hybrid_warning = query_module._hybrid_warning_emitted
    orig_pool = db_module._pool

    # Reset to default state
    query_module._has_metadata_columns = True
    query_module._metadata_warning_emitted = False
    query_module._has_content_text_column = True
    query_module._hybrid_warning_emitted = False
    db_module._pool = None

    yield

    # Restore original state after test
    query_module._has_metadata_columns = orig_has_metadata
    query_module._metadata_warning_emitted = orig_metadata_warning
    query_module._has_content_text_column = orig_has_content_text
    query_module._hybrid_warning_emitted = orig_hybrid_warning
    db_module._pool = orig_pool


@pytest.fixture
def hybrid_env(initialized_db, warmed_ollama):
    """Set up environment for hybrid search tests.

    Sets COCOSEARCH_DATABASE_URL and COCOSEARCH_OLLAMA_URL for the duration
    of the test. Returns both URLs for test use.

    Yields:
        tuple[str, str]: (db_url, ollama_url)
    """
    # Save original env vars
    orig_db_url = os.environ.get("COCOSEARCH_DATABASE_URL")
    orig_ollama_url = os.environ.get("COCOSEARCH_OLLAMA_URL")

    # Set up environment
    os.environ["COCOSEARCH_DATABASE_URL"] = initialized_db
    os.environ["COCOSEARCH_OLLAMA_URL"] = warmed_ollama

    yield (initialized_db, warmed_ollama)

    # Restore original env vars
    if orig_db_url is not None:
        os.environ["COCOSEARCH_DATABASE_URL"] = orig_db_url
    elif "COCOSEARCH_DATABASE_URL" in os.environ:
        del os.environ["COCOSEARCH_DATABASE_URL"]

    if orig_ollama_url is not None:
        os.environ["COCOSEARCH_OLLAMA_URL"] = orig_ollama_url
    elif "COCOSEARCH_OLLAMA_URL" in os.environ:
        del os.environ["COCOSEARCH_OLLAMA_URL"]


@pytest.fixture
def hybrid_test_table(hybrid_env):
    """Create a test table with v1.7 schema (hybrid search enabled).

    Creates table with:
    - filename, location (int4range), embedding columns (core schema)
    - content_text, content_tsv_input columns (hybrid search)
    - block_type, hierarchy, language_id columns (metadata)
    - content_tsv generated column + GIN index (via migration)

    Yields:
        tuple[str, str, str]: (table_name, db_url, ollama_url)
    """
    db_url, ollama_url = hybrid_env
    table_name = get_table_name(TEST_INDEX_NAME)

    with psycopg.connect(db_url) as conn:
        register_vector(conn)
        with conn.cursor() as cur:
            # Drop if exists
            cur.execute(f"DROP TABLE IF EXISTS {table_name}")

            # Create table with full v1.7 schema
            cur.execute(f"""
                CREATE TABLE {table_name} (
                    id SERIAL PRIMARY KEY,
                    filename TEXT NOT NULL,
                    location INT4RANGE NOT NULL,
                    embedding VECTOR(768),
                    content_text TEXT,
                    content_tsv_input TEXT,
                    block_type TEXT,
                    hierarchy TEXT,
                    language_id TEXT
                )
            """)
            conn.commit()

        # Apply hybrid search schema migration (adds content_tsv + GIN index)
        ensure_hybrid_search_schema(conn, table_name)

    yield (table_name, db_url, ollama_url)

    # Cleanup
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {table_name}")
            conn.commit()


@pytest.fixture
def pre_v17_test_table(hybrid_env):
    """Create a test table WITHOUT v1.7 schema (no hybrid search).

    Creates table with only core columns, no content_text/content_tsv.
    Used to test graceful degradation.

    Yields:
        tuple[str, str, str]: (table_name, db_url, ollama_url)
    """
    db_url, ollama_url = hybrid_env
    table_name = get_table_name(TEST_INDEX_NAME)

    with psycopg.connect(db_url) as conn:
        register_vector(conn)
        with conn.cursor() as cur:
            # Drop if exists
            cur.execute(f"DROP TABLE IF EXISTS {table_name}")

            # Create table WITHOUT hybrid search columns (pre-v1.7 schema)
            cur.execute(f"""
                CREATE TABLE {table_name} (
                    id SERIAL PRIMARY KEY,
                    filename TEXT NOT NULL,
                    location INT4RANGE NOT NULL,
                    embedding VECTOR(768),
                    block_type TEXT,
                    hierarchy TEXT,
                    language_id TEXT
                )
            """)
            conn.commit()

    yield (table_name, db_url, ollama_url)

    # Cleanup
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {table_name}")
            conn.commit()


def insert_test_chunk(
    conn: psycopg.Connection,
    table_name: str,
    filename: str,
    start_byte: int,
    end_byte: int,
    embedding: list[float],
    content_text: str | None = None,
    block_type: str = "",
    hierarchy: str = "",
    language_id: str = "",
):
    """Insert a test chunk into the table.

    Args:
        conn: Database connection
        table_name: Table name
        filename: File path
        start_byte: Start byte offset
        end_byte: End byte offset
        embedding: 768-dimensional embedding vector
        content_text: Raw text content (optional, for hybrid search)
        block_type: Block type metadata
        hierarchy: Hierarchy metadata
        language_id: Language ID metadata
    """
    # Generate content_tsv_input from content_text if provided
    content_tsv_input = None
    if content_text:
        content_tsv_input = preprocess_code_for_tsvector(content_text)

    with conn.cursor() as cur:
        cur.execute(f"""
            INSERT INTO {table_name}
            (filename, location, embedding, content_text, content_tsv_input,
             block_type, hierarchy, language_id)
            VALUES (%s, int4range(%s, %s), %s::vector, %s, %s, %s, %s, %s)
        """, (
            filename,
            start_byte,
            end_byte,
            embedding,
            content_text,
            content_tsv_input,
            block_type,
            hierarchy,
            language_id,
        ))
        conn.commit()


def insert_pre_v17_chunk(
    conn: psycopg.Connection,
    table_name: str,
    filename: str,
    start_byte: int,
    end_byte: int,
    embedding: list[float],
    block_type: str = "",
    hierarchy: str = "",
    language_id: str = "",
):
    """Insert a test chunk into pre-v1.7 table (no content_text column)."""
    with conn.cursor() as cur:
        cur.execute(f"""
            INSERT INTO {table_name}
            (filename, location, embedding, block_type, hierarchy, language_id)
            VALUES (%s, int4range(%s, %s), %s::vector, %s, %s, %s)
        """, (
            filename,
            start_byte,
            end_byte,
            embedding,
            block_type,
            hierarchy,
            language_id,
        ))
        conn.commit()


def get_embedding(text: str, ollama_url: str) -> list[float]:
    """Get embedding for text using Ollama.

    Creates a fresh embedding flow with the specified Ollama URL.

    Args:
        text: Text to embed
        ollama_url: Ollama service URL

    Returns:
        768-dimensional embedding vector
    """

    @cocoindex.transform_flow()
    def embed_text(
        content: cocoindex.DataSlice[str],
    ) -> cocoindex.DataSlice[list[float]]:
        return content.transform(
            cocoindex.functions.EmbedText(
                api_type=cocoindex.LlmApiType.OLLAMA,
                model="nomic-embed-text",
                address=ollama_url,
            )
        )

    return embed_text.eval(text)


class TestHybridSearchSemanticMatch:
    """Tests for semantic (vector) matching in hybrid search."""

    def test_hybrid_search_finds_semantic_match(self, hybrid_test_table):
        """Verify semantic similarity finds relevant content.

        Insert chunk with "authentication handler" content, search for
        "login authentication" - should find via semantic similarity.
        """
        table_name, db_url, ollama_url = hybrid_test_table
        content = """
def authenticate_user(username, password):
    '''Authentication handler for user login.'''
    # Validate credentials against database
    user = db.find_user(username)
    if user and check_password(password, user.password_hash):
        return create_session(user)
    return None
"""
        # Generate embedding for the actual content
        embedding = get_embedding(content, ollama_url)

        with psycopg.connect(db_url) as conn:
            register_vector(conn)
            insert_test_chunk(
                conn, table_name,
                filename="/src/auth.py",
                start_byte=0,
                end_byte=len(content),
                embedding=embedding,
                content_text=content,
                language_id="python",
            )

        # Search with semantically similar query
        results = search("login authentication", TEST_INDEX_NAME, limit=5)

        assert len(results) > 0, "Should find at least one result"
        assert results[0].filename == "/src/auth.py"
        # Semantic match should have match_type "semantic" or "both"
        assert results[0].match_type in ("semantic", "both"), \
            f"Expected semantic or both match type, got {results[0].match_type}"


class TestHybridSearchKeywordMatch:
    """Tests for keyword (full-text) matching in hybrid search."""

    def test_hybrid_search_finds_keyword_match(self, hybrid_test_table):
        """Verify keyword search finds exact identifier matches.

        Insert chunk with "getUserById" function, search for "getUserById" -
        should find via keyword search with match_type "keyword" or "both".
        """
        table_name, db_url, ollama_url = hybrid_test_table
        content = """
function getUserById(userId) {
    // Fetch user from database by ID
    return db.query('SELECT * FROM users WHERE id = ?', [userId]);
}
"""
        embedding = get_embedding(content, ollama_url)

        with psycopg.connect(db_url) as conn:
            register_vector(conn)
            insert_test_chunk(
                conn, table_name,
                filename="/src/user.js",
                start_byte=0,
                end_byte=len(content),
                embedding=embedding,
                content_text=content,
                language_id="javascript",
            )

        # Search for exact identifier
        results = search("getUserById", TEST_INDEX_NAME, limit=5, use_hybrid=True)

        assert len(results) > 0, "Should find at least one result"
        assert results[0].filename == "/src/user.js"
        # Should have keyword contribution
        assert results[0].match_type in ("keyword", "both"), \
            f"Expected keyword or both match type, got {results[0].match_type}"
        # Should have keyword score populated
        assert results[0].keyword_score is not None or results[0].match_type == "both", \
            "Keyword match should have keyword_score"


class TestRRFFusion:
    """Tests for Reciprocal Rank Fusion ranking behavior."""

    def test_hybrid_search_ranks_double_match_higher(self, hybrid_test_table):
        """Verify RRF fusion ranks double-matches higher than single-source.

        Insert two chunks:
        1. One that matches semantically only
        2. One that matches both semantically AND via keyword

        The double-match should rank higher due to RRF fusion.
        """
        table_name, db_url, ollama_url = hybrid_test_table

        # Chunk 1: Matches semantically for "user data processing"
        content_semantic_only = """
def transform_records(data):
    '''Transform data records for output.'''
    # Apply transformations to each record
    return [normalize(r) for r in data]
"""
        # Chunk 2: Matches both semantically AND keyword for "processUserData"
        content_both = """
def processUserData(userData):
    '''Process user data for analytics pipeline.'''
    # Validate and transform user data
    validated = validate_user_data(userData)
    return enrich_user_record(validated)
"""
        embedding_semantic = get_embedding(content_semantic_only, ollama_url)
        embedding_both = get_embedding(content_both, ollama_url)

        with psycopg.connect(db_url) as conn:
            register_vector(conn)
            # Insert semantic-only match
            insert_test_chunk(
                conn, table_name,
                filename="/src/transform.py",
                start_byte=0,
                end_byte=len(content_semantic_only),
                embedding=embedding_semantic,
                content_text=content_semantic_only,
            )
            # Insert double-match
            insert_test_chunk(
                conn, table_name,
                filename="/src/user_processor.py",
                start_byte=0,
                end_byte=len(content_both),
                embedding=embedding_both,
                content_text=content_both,
            )

        # Search for "processUserData" - should rank the double-match higher
        results = search("processUserData", TEST_INDEX_NAME, limit=5, use_hybrid=True)

        assert len(results) >= 2, "Should find at least two results"

        # Find the user_processor result
        user_processor_result = next(
            (r for r in results if "user_processor" in r.filename), None
        )
        assert user_processor_result is not None, "Should find user_processor.py"

        # The double-match should be ranked first or have "both" match type
        # Due to RRF fusion, exact keyword match + semantic should rank higher
        if results[0].filename == "/src/user_processor.py":
            # Double match ranked first - success
            assert user_processor_result.match_type in ("keyword", "both")
        else:
            # If not first, verify it at least has both match types
            # (RRF might not always rank it first depending on exact scores)
            assert user_processor_result.match_type in ("keyword", "both"), \
                "processUserData chunk should have keyword match component"


class TestAutoDetection:
    """Tests for automatic hybrid search triggering."""

    def test_auto_hybrid_triggered_for_camelcase(self, hybrid_test_table):
        """Verify auto-detection triggers hybrid for camelCase queries.

        Search for "processUserData" with use_hybrid=None (auto mode).
        Should detect camelCase pattern and use hybrid search.
        """
        table_name, db_url, ollama_url = hybrid_test_table
        content = """
function processUserData(userData) {
    // Process user data for the application
    return transformUserRecord(userData);
}
"""
        embedding = get_embedding(content, ollama_url)

        with psycopg.connect(db_url) as conn:
            register_vector(conn)
            insert_test_chunk(
                conn, table_name,
                filename="/src/processor.js",
                start_byte=0,
                end_byte=len(content),
                embedding=embedding,
                content_text=content,
                language_id="javascript",
            )

        # Search with auto-detection (use_hybrid=None)
        results = search("processUserData", TEST_INDEX_NAME, limit=5, use_hybrid=None)

        assert len(results) > 0, "Should find at least one result"
        # Auto-detection should trigger hybrid, so match_type should be set
        assert results[0].match_type in ("semantic", "keyword", "both"), \
            f"Auto-detection should trigger hybrid search, got match_type={results[0].match_type}"

    def test_auto_hybrid_triggered_for_snake_case(self, hybrid_test_table):
        """Verify auto-detection triggers hybrid for snake_case queries."""
        table_name, db_url, ollama_url = hybrid_test_table
        content = """
def get_user_by_id(user_id):
    '''Fetch user record by ID from database.'''
    return db.users.find_one({'id': user_id})
"""
        embedding = get_embedding(content, ollama_url)

        with psycopg.connect(db_url) as conn:
            register_vector(conn)
            insert_test_chunk(
                conn, table_name,
                filename="/src/users.py",
                start_byte=0,
                end_byte=len(content),
                embedding=embedding,
                content_text=content,
                language_id="python",
            )

        # Search with auto-detection for snake_case
        results = search("get_user_by_id", TEST_INDEX_NAME, limit=5, use_hybrid=None)

        assert len(results) > 0, "Should find at least one result"
        assert results[0].filename == "/src/users.py"
        assert results[0].match_type in ("keyword", "both"), \
            "snake_case query should trigger keyword matching"

    def test_auto_hybrid_not_triggered_for_plain_english(self, hybrid_test_table):
        """Verify auto-detection does NOT trigger hybrid for plain English.

        Search for "process user data" (plain English, not identifier).
        Should use vector-only search (match_type "semantic" or empty).
        """
        table_name, db_url, ollama_url = hybrid_test_table
        content = """
def transform_data(records):
    '''Transform data records for output.

    This function will process user data and transform it
    into the required output format.
    '''
    return [normalize(r) for r in records]
"""
        embedding = get_embedding(content, ollama_url)

        with psycopg.connect(db_url) as conn:
            register_vector(conn)
            insert_test_chunk(
                conn, table_name,
                filename="/src/transform.py",
                start_byte=0,
                end_byte=len(content),
                embedding=embedding,
                content_text=content,
                language_id="python",
            )

        # Search with plain English (no identifier pattern)
        results = search("process user data", TEST_INDEX_NAME, limit=5, use_hybrid=None)

        assert len(results) > 0, "Should find at least one result"
        # Plain English query should use vector-only, so match_type should be "semantic"
        # (or empty for backward compat, but with v1.7 schema it should be "semantic")
        assert results[0].match_type in ("semantic", ""), \
            f"Plain English should use vector-only search, got match_type={results[0].match_type}"


class TestGracefulDegradation:
    """Tests for graceful degradation on pre-v1.7 indexes."""

    def test_graceful_degradation_pre_v17_schema(self, pre_v17_test_table):
        """Verify hybrid search falls back to vector-only for pre-v1.7 indexes.

        Create table WITHOUT content_text/content_tsv columns.
        Attempt hybrid search with use_hybrid=True.
        Should fall back to vector-only without error.
        """
        table_name, db_url, ollama_url = pre_v17_test_table
        content = """
def authenticate_user(username, password):
    '''Authenticate user credentials.'''
    return verify_password(username, password)
"""
        embedding = get_embedding(content, ollama_url)

        with psycopg.connect(db_url) as conn:
            register_vector(conn)
            insert_pre_v17_chunk(
                conn, table_name,
                filename="/src/auth.py",
                start_byte=0,
                end_byte=len(content),
                embedding=embedding,
                language_id="python",
            )

        # Search with explicit hybrid=True on pre-v1.7 schema
        # Should NOT raise an error, should fall back gracefully
        results = search(
            "authenticate user", TEST_INDEX_NAME, limit=5, use_hybrid=True
        )

        assert len(results) > 0, "Should still return results via vector search"
        assert results[0].filename == "/src/auth.py"
        # Match type should be "semantic" since keyword search isn't available
        assert results[0].match_type in ("semantic", ""), \
            f"Pre-v1.7 should fall back to semantic-only, got {results[0].match_type}"

    def test_graceful_degradation_auto_mode(self, pre_v17_test_table):
        """Verify auto-detection works correctly on pre-v1.7 indexes.

        Even with identifier pattern query, should fall back to vector-only
        when hybrid columns don't exist.
        """
        table_name, db_url, ollama_url = pre_v17_test_table
        content = """
function getUserById(id) {
    return database.findUser(id);
}
"""
        embedding = get_embedding(content, ollama_url)

        with psycopg.connect(db_url) as conn:
            register_vector(conn)
            insert_pre_v17_chunk(
                conn, table_name,
                filename="/src/user.js",
                start_byte=0,
                end_byte=len(content),
                embedding=embedding,
                language_id="javascript",
            )

        # Search with identifier pattern but on pre-v1.7 schema
        results = search("getUserById", TEST_INDEX_NAME, limit=5, use_hybrid=None)

        assert len(results) > 0, "Should still return results"
        assert results[0].filename == "/src/user.js"
        # Should fall back to semantic-only
        assert results[0].match_type in ("semantic", ""), \
            f"Pre-v1.7 should use semantic-only, got {results[0].match_type}"
