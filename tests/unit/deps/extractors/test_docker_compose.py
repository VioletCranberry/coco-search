"""Tests for cocosearch.deps.extractors.docker_compose module."""

from cocosearch.deps.extractors.docker_compose import DockerComposeExtractor
from cocosearch.deps.models import DepType


def _extract(content: str, file_path: str = "docker-compose.yml"):
    extractor = DockerComposeExtractor()
    return extractor.extract(file_path, content)


class TestImageReferences:
    """Tests for image: reference extraction."""

    def test_extracts_image_ref(self):
        content = """\
services:
  web:
    image: nginx:latest
"""
        edges = _extract(content)
        image_edges = [e for e in edges if e.metadata.get("kind") == "image"]
        assert len(image_edges) == 1
        assert image_edges[0].metadata["ref"] == "nginx:latest"
        assert image_edges[0].source_symbol == "web"
        assert image_edges[0].dep_type == DepType.REFERENCE

    def test_multiple_services_with_images(self):
        content = """\
services:
  web:
    image: nginx:latest
  db:
    image: postgres:16
"""
        edges = _extract(content)
        image_edges = [e for e in edges if e.metadata.get("kind") == "image"]
        refs = {e.metadata["ref"] for e in image_edges}
        assert "nginx:latest" in refs
        assert "postgres:16" in refs


class TestDependsOn:
    """Tests for depends_on: reference extraction."""

    def test_depends_on_list(self):
        content = """\
services:
  web:
    depends_on:
      - db
      - redis
"""
        edges = _extract(content)
        deps = [e for e in edges if e.metadata.get("kind") == "depends_on"]
        assert len(deps) == 2
        targets = {e.target_symbol for e in deps}
        assert targets == {"db", "redis"}

    def test_depends_on_dict(self):
        content = """\
services:
  web:
    depends_on:
      db:
        condition: service_healthy
"""
        edges = _extract(content)
        deps = [e for e in edges if e.metadata.get("kind") == "depends_on"]
        assert len(deps) == 1
        assert deps[0].target_symbol == "db"


class TestExtends:
    """Tests for extends: reference extraction."""

    def test_extends_service(self):
        content = """\
services:
  web:
    extends:
      service: base
"""
        edges = _extract(content)
        ext = [e for e in edges if e.metadata.get("kind") == "extends"]
        assert len(ext) == 1
        assert ext[0].target_symbol == "base"

    def test_extends_with_file(self):
        content = """\
services:
  web:
    extends:
      file: common.yml
      service: base
"""
        edges = _extract(content)
        ext = [e for e in edges if e.metadata.get("kind") == "extends"]
        assert len(ext) == 1
        assert ext[0].target_file == "common.yml"
        assert ext[0].target_symbol == "base"


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_file(self):
        assert _extract("") == []

    def test_invalid_yaml(self):
        assert _extract("{{invalid") == []

    def test_no_services(self):
        assert _extract("version: '3'\n") == []

    def test_languages_set(self):
        extractor = DockerComposeExtractor()
        assert extractor.LANGUAGES == {"docker-compose"}
