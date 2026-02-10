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
        """Matches compose file in nested directory (basename matching)."""
        handler = DockerComposeHandler()
        content = "services:\n  app:\n    build: ."
        assert handler.matches("infra/docker-compose.yml", content) is True

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
        assert handler.SEPARATOR_SPEC.language_name == "docker-compose"

    def test_has_separators(self):
        """SEPARATOR_SPEC should have a non-empty separators_regex list."""
        handler = DockerComposeHandler()
        assert len(handler.SEPARATOR_SPEC.separators_regex) > 0

    def test_no_lookaheads_in_separators(self):
        """Separators must not contain lookahead/lookbehind patterns."""
        handler = DockerComposeHandler()
        for sep in handler.SEPARATOR_SPEC.separators_regex:
            assert "(?=" not in sep
            assert "(?<=" not in sep
            assert "(?!" not in sep
            assert "(?<!" not in sep


@pytest.mark.unit
class TestDockerComposeExtractMetadata:
    """Tests for DockerComposeHandler.extract_metadata()."""

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
        assert m["language_id"] == "docker-compose"

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
        assert m["language_id"] == "docker-compose"

    def test_top_level_version_with_inline_value(self):
        """Top-level key with inline value (version: '3') is identified."""
        handler = DockerComposeHandler()
        text = "version: '3'\nservices:\n  grafana:\n    image: grafana/grafana"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "version"
        assert m["hierarchy"] == "version"
        assert m["language_id"] == "docker-compose"

    def test_unrecognized_content(self):
        """Unrecognized content returns empty block_type."""
        handler = DockerComposeHandler()
        m = handler.extract_metadata("    some deeply indented content")
        assert m["block_type"] == ""
        assert m["hierarchy"] == ""
        assert m["language_id"] == "docker-compose"

    def test_comment_before_service(self):
        """Comment before service is correctly skipped."""
        handler = DockerComposeHandler()
        text = "# Web service\n  web:\n    image: nginx"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "service"
        assert m["hierarchy"] == "service:web"
        assert m["language_id"] == "docker-compose"


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
