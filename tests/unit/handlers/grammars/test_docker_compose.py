"""Tests for cocosearch.handlers.grammars.docker_compose module."""

import pytest

from cocosearch.handlers.grammars.docker_compose import DockerComposeHandler


@pytest.mark.unit
class TestDockerComposeMatching:
    """Tests for DockerComposeHandler.matches()."""

    def test_matches_docker_compose_yml(self):
        """Matches docker-compose.yml with 'services:' content."""
        handler = DockerComposeHandler()
        content = "services:\n  web:\n    image: nginx"
        assert handler.matches("docker-compose.yml", content) is True

    def test_matches_docker_compose_yaml(self):
        """Matches docker-compose.yaml with 'services:' content."""
        handler = DockerComposeHandler()
        content = "services:\n  db:\n    image: postgres"
        assert handler.matches("docker-compose.yaml", content) is True

    def test_matches_compose_yml(self):
        """Matches compose.yml with 'services:' content."""
        handler = DockerComposeHandler()
        content = "services:\n  app:\n    build: ."
        assert handler.matches("compose.yml", content) is True

    def test_matches_compose_yaml(self):
        """Matches compose.yaml with 'services:' content."""
        handler = DockerComposeHandler()
        content = "services:\n  app:\n    build: ."
        assert handler.matches("compose.yaml", content) is True

    def test_matches_docker_compose_override(self):
        """Matches docker-compose.override.yml."""
        handler = DockerComposeHandler()
        content = "services:\n  web:\n    ports:\n      - '8080:80'"
        assert handler.matches("docker-compose.override.yml", content) is True

    def test_rejects_missing_services(self):
        """Rejects compose file without 'services:' key."""
        handler = DockerComposeHandler()
        content = "version: '3'\nvolumes:\n  data:"
        assert handler.matches("docker-compose.yml", content) is False

    def test_rejects_non_compose_path(self):
        """Rejects files that don't match compose naming patterns."""
        handler = DockerComposeHandler()
        content = "services:\n  web:\n    image: nginx"
        assert handler.matches("config.yml", content) is False

    def test_matches_path_only_without_content(self):
        """Matches by path alone when content is None."""
        handler = DockerComposeHandler()
        assert handler.matches("docker-compose.yml") is True

    def test_matches_nested_path(self):
        """Matches compose file in nested directory."""
        handler = DockerComposeHandler()
        content = "services:\n  app:\n    build: ."
        assert handler.matches("infra/docker-compose.yml", content) is True

    def test_matches_deeply_nested_path(self):
        """Matches compose file in deeply nested directory."""
        handler = DockerComposeHandler()
        content = "services:\n  app:\n    build: ."
        assert handler.matches("project/deploy/infra/compose.yml", content) is True

    def test_matches_nested_path_without_content(self):
        """Matches nested path by path alone when content is None."""
        handler = DockerComposeHandler()
        assert handler.matches("infra/docker-compose.yml") is True

    def test_rejects_wrong_path_without_content(self):
        """Rejects wrong path when content is None."""
        handler = DockerComposeHandler()
        assert handler.matches("config.yml") is False


@pytest.mark.unit
class TestDockerComposeSeparatorSpec:
    """Tests for DockerComposeHandler.SEPARATOR_SPEC."""

    def test_language_name(self):
        """SEPARATOR_SPEC.language_name should be 'docker-compose'."""
        handler = DockerComposeHandler()
        assert handler.SEPARATOR_SPEC._config.language_name == "docker-compose"

    def test_separator_count(self):
        """SEPARATOR_SPEC should have 7 separator levels."""
        handler = DockerComposeHandler()
        assert len(handler.SEPARATOR_SPEC._config.separators_regex) == 7

    def test_has_yaml_document_separator(self):
        """First separator should be YAML document separator (---)."""
        handler = DockerComposeHandler()
        assert r"\n---" in handler.SEPARATOR_SPEC._config.separators_regex[0]

    def test_no_lookaheads_in_separators(self):
        """Separators must not contain lookahead/lookbehind patterns."""
        handler = DockerComposeHandler()
        for sep in handler.SEPARATOR_SPEC._config.separators_regex:
            assert "(?=" not in sep
            assert "(?<=" not in sep
            assert "(?!" not in sep
            assert "(?<!" not in sep


@pytest.mark.unit
class TestDockerComposeExtractMetadata:
    """Tests for DockerComposeHandler.extract_metadata()."""

    # --- Service detection (2-space indented) ---

    def test_service_definition(self):
        """Service definition extracts service name."""
        handler = DockerComposeHandler()
        text = "  web:\n    image: nginx\n    ports:\n      - '80:80'"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "service"
        assert m["hierarchy"] == "service:web"
        assert m["language_id"] == "docker-compose"

    def test_service_db(self):
        """Database service extracts correctly."""
        handler = DockerComposeHandler()
        text = "  db:\n    image: postgres:15\n    environment:\n      POSTGRES_DB: app"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "service"
        assert m["hierarchy"] == "service:db"

    def test_service_with_hyphen(self):
        """Service name with hyphen extracts correctly."""
        handler = DockerComposeHandler()
        text = "  my-service:\n    image: alpine"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "service"
        assert m["hierarchy"] == "service:my-service"

    # --- Nested key detection (4+ space indented) ---

    def test_nested_key_ports(self):
        """4-space indented 'ports:' detected as nested-key."""
        handler = DockerComposeHandler()
        text = "    ports:\n      - '8080:80'"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "nested-key"
        assert m["hierarchy"] == "nested-key:ports"

    def test_nested_key_environment(self):
        """4-space indented 'environment:' detected as nested-key."""
        handler = DockerComposeHandler()
        text = "    environment:\n      POSTGRES_DB: mydb"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "nested-key"
        assert m["hierarchy"] == "nested-key:environment"

    def test_nested_key_deploy(self):
        """4-space indented 'deploy:' detected as nested-key."""
        handler = DockerComposeHandler()
        text = "    deploy:\n      replicas: 3"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "nested-key"
        assert m["hierarchy"] == "nested-key:deploy"

    def test_deeply_nested_key(self):
        """6-space indented key still detected as nested-key."""
        handler = DockerComposeHandler()
        text = "      resources:\n        limits:\n          cpus: '0.5'"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "nested-key"
        assert m["hierarchy"] == "nested-key:resources"

    def test_four_space_is_not_service(self):
        """4-space indented key is nested-key, not service."""
        handler = DockerComposeHandler()
        text = "    image: nginx"
        m = handler.extract_metadata(text)
        # 'image: nginx' has no colon-newline pattern for nested-key regex,
        # but the nested_key regex matches 'image:'
        assert m["block_type"] == "nested-key"
        assert m["hierarchy"] == "nested-key:image"

    # --- List item detection ---

    def test_list_item_key(self):
        """YAML list item with key detected as list-item."""
        handler = DockerComposeHandler()
        text = "- path: ./docker-compose.override.yml"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "list-item"
        assert m["hierarchy"] == "list-item:path"

    def test_list_item_indented(self):
        """Indented YAML list item with key detected as list-item."""
        handler = DockerComposeHandler()
        text = "      - name: web\n        image: nginx"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "list-item"
        assert m["hierarchy"] == "list-item:name"

    # --- Top-level key detection ---

    def test_top_level_services_key(self):
        """Top-level 'services:' key is identified."""
        handler = DockerComposeHandler()
        text = "services:\n"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "services"
        assert m["hierarchy"] == "services"
        assert m["language_id"] == "docker-compose"

    def test_top_level_volumes_key(self):
        """Top-level 'volumes:' key is identified."""
        handler = DockerComposeHandler()
        text = "volumes:\n"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "volumes"
        assert m["hierarchy"] == "volumes"

    def test_top_level_version_with_inline_value(self):
        """Top-level key with inline value (version: '3') is identified."""
        handler = DockerComposeHandler()
        text = "version: '3'\nservices:\n  grafana:\n    image: grafana/grafana"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "version"
        assert m["hierarchy"] == "version"

    def test_top_level_networks_key(self):
        """Top-level 'networks:' key is identified."""
        handler = DockerComposeHandler()
        text = "networks:\n  frontend:\n    driver: bridge"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "networks"
        assert m["hierarchy"] == "networks"

    # --- Document separator detection ---

    def test_document_separator(self):
        """Chunk with --- detected as document."""
        handler = DockerComposeHandler()
        text = "---"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "document"
        assert m["hierarchy"] == "document"
        assert m["language_id"] == "docker-compose"

    def test_document_separator_with_content(self):
        """Chunk containing --- among whitespace detected as document."""
        handler = DockerComposeHandler()
        text = "\n---\n"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "document"
        assert m["hierarchy"] == "document"

    # --- Value continuation detection ---

    def test_value_continuation(self):
        """Chunk with content but no recognizable key detected as value."""
        handler = DockerComposeHandler()
        text = "    some deeply indented content"
        m = handler.extract_metadata(text)
        # "some" doesn't have a colon after it, so no key match
        assert m["block_type"] == "value"
        assert m["hierarchy"] == "value"
        assert m["language_id"] == "docker-compose"

    # --- Comment handling ---

    def test_comment_before_service(self):
        """Comment before service is correctly skipped."""
        handler = DockerComposeHandler()
        text = "# Web service\n  web:\n    image: nginx"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "service"
        assert m["hierarchy"] == "service:web"

    def test_comment_before_top_level(self):
        """Comment before top-level key is correctly skipped."""
        handler = DockerComposeHandler()
        text = "# Service definitions\nservices:\n"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "services"
        assert m["hierarchy"] == "services"

    # --- Empty / whitespace ---

    def test_empty_content(self):
        """Empty content returns empty block_type."""
        handler = DockerComposeHandler()
        m = handler.extract_metadata("")
        assert m["block_type"] == ""
        assert m["hierarchy"] == ""
        assert m["language_id"] == "docker-compose"

    def test_whitespace_only(self):
        """Whitespace-only content returns empty block_type."""
        handler = DockerComposeHandler()
        m = handler.extract_metadata("   \n   \n")
        assert m["block_type"] == ""
        assert m["hierarchy"] == ""

    # --- Indentation precision ---

    def test_two_space_is_service_not_top_level(self):
        """2-space indented key is service, not top-level."""
        handler = DockerComposeHandler()
        text = "  redis:\n    image: redis:7"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "service"
        assert m["hierarchy"] == "service:redis"

    def test_four_space_is_nested_not_service(self):
        """4-space indented key is nested-key, not service."""
        handler = DockerComposeHandler()
        text = "    volumes:\n      - ./data:/data"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "nested-key"
        assert m["hierarchy"] == "nested-key:volumes"


@pytest.mark.unit
class TestDockerComposeProtocol:
    """Tests for DockerComposeHandler protocol compliance."""

    def test_has_grammar_name(self):
        handler = DockerComposeHandler()
        assert handler.GRAMMAR_NAME == "docker-compose"

    def test_has_base_language(self):
        handler = DockerComposeHandler()
        assert handler.BASE_LANGUAGE == "yaml"

    def test_has_path_patterns(self):
        handler = DockerComposeHandler()
        assert len(handler.PATH_PATTERNS) > 0

    def test_include_in_top_level_keys(self):
        """'include' should be in _TOP_LEVEL_KEYS for Compose v2+."""
        handler = DockerComposeHandler()
        assert "include" in handler._TOP_LEVEL_KEYS
