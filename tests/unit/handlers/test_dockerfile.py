"""Tests for cocosearch.handlers.dockerfile module."""

import pytest

from cocosearch.handlers.dockerfile import DockerfileHandler


@pytest.mark.unit
class TestDockerfileHandlerExtensions:
    """Tests for DockerfileHandler EXTENSIONS."""

    def test_extensions_contains_dockerfile(self):
        """EXTENSIONS should contain .dockerfile."""
        handler = DockerfileHandler()
        assert ".dockerfile" in handler.EXTENSIONS


@pytest.mark.unit
class TestDockerfileHandlerSeparatorSpec:
    """Tests for DockerfileHandler SEPARATOR_SPEC."""

    def test_language_name_is_dockerfile(self):
        """SEPARATOR_SPEC.language_name should be 'dockerfile'."""
        handler = DockerfileHandler()
        assert handler.SEPARATOR_SPEC.language_name == "dockerfile"

    def test_aliases_empty(self):
        """SEPARATOR_SPEC.aliases should be empty (routing via extract_language)."""
        handler = DockerfileHandler()
        assert handler.SEPARATOR_SPEC.aliases == []

    def test_has_separators(self):
        """SEPARATOR_SPEC should have a non-empty separators_regex list."""
        handler = DockerfileHandler()
        assert len(handler.SEPARATOR_SPEC.separators_regex) > 0

    def test_from_is_higher_priority_than_other_instructions(self):
        """FROM should be a separate separator at higher priority than other instructions."""
        handler = DockerfileHandler()
        separators = handler.SEPARATOR_SPEC.separators_regex
        from_index = None
        instructions_index = None
        for i, sep in enumerate(separators):
            if "FROM" in sep and "RUN" not in sep:
                from_index = i
            if "RUN" in sep:
                instructions_index = i
        assert from_index is not None, "FROM separator not found"
        assert instructions_index is not None, "Instructions separator not found"
        assert from_index < instructions_index, (
            "FROM should be higher priority (lower index) than instructions"
        )

    def test_no_lookaheads_in_separators(self):
        """Dockerfile separators must not contain lookahead or lookbehind patterns."""
        handler = DockerfileHandler()
        for sep in handler.SEPARATOR_SPEC.separators_regex:
            assert "(?=" not in sep, f"Lookahead found in Dockerfile separator: {sep}"
            assert "(?<=" not in sep, f"Lookbehind found in Dockerfile separator: {sep}"
            assert "(?!" not in sep, (
                f"Negative lookahead found in Dockerfile separator: {sep}"
            )
            assert "(?<!" not in sep, (
                f"Negative lookbehind found in Dockerfile separator: {sep}"
            )


@pytest.mark.unit
class TestDockerfileHandlerExtractMetadata:
    """Tests for DockerfileHandler.extract_metadata()."""

    def test_from_with_as_produces_stage_hierarchy(self):
        """FROM with AS clause produces stage hierarchy."""
        handler = DockerfileHandler()
        m = handler.extract_metadata("FROM golang:1.21 AS builder")
        assert m["block_type"] == "FROM"
        assert m["hierarchy"] == "stage:builder"
        assert m["language_id"] == "dockerfile"

    def test_from_without_as_produces_image_hierarchy(self):
        """FROM without AS clause produces image hierarchy."""
        handler = DockerfileHandler()
        m = handler.extract_metadata("FROM ubuntu:22.04")
        assert m["block_type"] == "FROM"
        assert m["hierarchy"] == "image:ubuntu:22.04"
        assert m["language_id"] == "dockerfile"

    def test_from_with_platform_and_as(self):
        """FROM with --platform flag and AS clause produces stage hierarchy."""
        handler = DockerfileHandler()
        m = handler.extract_metadata(
            "FROM --platform=linux/amd64 golang:1.21 AS builder"
        )
        assert m["block_type"] == "FROM"
        assert m["hierarchy"] == "stage:builder"
        assert m["language_id"] == "dockerfile"

    def test_from_scratch(self):
        """FROM scratch produces image:scratch hierarchy."""
        handler = DockerfileHandler()
        m = handler.extract_metadata("FROM scratch")
        assert m["block_type"] == "FROM"
        assert m["hierarchy"] == "image:scratch"
        assert m["language_id"] == "dockerfile"

    def test_from_case_insensitive_as(self):
        """FROM with lowercase 'as' clause is recognized."""
        handler = DockerfileHandler()
        m = handler.extract_metadata("FROM golang:1.21 as builder")
        assert m["block_type"] == "FROM"
        assert m["hierarchy"] == "stage:builder"
        assert m["language_id"] == "dockerfile"

    def test_run_instruction_empty_hierarchy(self):
        """RUN instruction produces empty hierarchy."""
        handler = DockerfileHandler()
        m = handler.extract_metadata("RUN apt-get update")
        assert m["block_type"] == "RUN"
        assert m["hierarchy"] == ""
        assert m["language_id"] == "dockerfile"

    def test_copy_instruction_empty_hierarchy(self):
        """COPY without --from produces empty hierarchy."""
        handler = DockerfileHandler()
        m = handler.extract_metadata("COPY . /app")
        assert m["block_type"] == "COPY"
        assert m["hierarchy"] == ""
        assert m["language_id"] == "dockerfile"

    def test_copy_from_produces_hierarchy(self):
        """COPY --from produces from:<stage> hierarchy."""
        handler = DockerfileHandler()
        m = handler.extract_metadata("COPY --from=builder /app /app")
        assert m["block_type"] == "COPY"
        assert m["hierarchy"] == "from:builder"
        assert m["language_id"] == "dockerfile"

    def test_copy_from_numeric_stage(self):
        """COPY --from with numeric stage produces from:<number> hierarchy."""
        handler = DockerfileHandler()
        m = handler.extract_metadata("COPY --from=0 /app /app")
        assert m["block_type"] == "COPY"
        assert m["hierarchy"] == "from:0"

    def test_arg_produces_hierarchy(self):
        """ARG instruction produces arg:<name> hierarchy."""
        handler = DockerfileHandler()
        m = handler.extract_metadata("ARG VERSION=dev")
        assert m["block_type"] == "ARG"
        assert m["hierarchy"] == "arg:VERSION"
        assert m["language_id"] == "dockerfile"

    def test_arg_without_default(self):
        """ARG without default value produces arg:<name> hierarchy."""
        handler = DockerfileHandler()
        m = handler.extract_metadata("ARG COMMIT_SHA")
        assert m["block_type"] == "ARG"
        assert m["hierarchy"] == "arg:COMMIT_SHA"

    def test_env_produces_hierarchy(self):
        """ENV instruction produces env:<key> hierarchy."""
        handler = DockerfileHandler()
        m = handler.extract_metadata("ENV NODE_ENV=production")
        assert m["block_type"] == "ENV"
        assert m["hierarchy"] == "env:NODE_ENV"
        assert m["language_id"] == "dockerfile"

    def test_env_space_separated(self):
        """ENV with space-separated key/value produces env:<key> hierarchy."""
        handler = DockerfileHandler()
        m = handler.extract_metadata("ENV PATH /usr/local/bin")
        assert m["block_type"] == "ENV"
        assert m["hierarchy"] == "env:PATH"

    def test_add_instruction_empty_hierarchy(self):
        """ADD instruction produces empty hierarchy."""
        handler = DockerfileHandler()
        m = handler.extract_metadata("ADD src.tar.gz /app")
        assert m["block_type"] == "ADD"
        assert m["hierarchy"] == ""
        assert m["language_id"] == "dockerfile"

    def test_expose_produces_hierarchy(self):
        """EXPOSE instruction produces port:<port> hierarchy."""
        handler = DockerfileHandler()
        m = handler.extract_metadata("EXPOSE 8080")
        assert m["block_type"] == "EXPOSE"
        assert m["hierarchy"] == "port:8080"
        assert m["language_id"] == "dockerfile"

    def test_expose_with_protocol(self):
        """EXPOSE with protocol produces port:<port/proto> hierarchy."""
        handler = DockerfileHandler()
        m = handler.extract_metadata("EXPOSE 8080/tcp")
        assert m["block_type"] == "EXPOSE"
        assert m["hierarchy"] == "port:8080/tcp"

    def test_workdir_produces_hierarchy(self):
        """WORKDIR instruction produces workdir:<path> hierarchy."""
        handler = DockerfileHandler()
        m = handler.extract_metadata("WORKDIR /app")
        assert m["block_type"] == "WORKDIR"
        assert m["hierarchy"] == "workdir:/app"
        assert m["language_id"] == "dockerfile"

    def test_label_produces_hierarchy(self):
        """LABEL instruction produces label:<key> hierarchy."""
        handler = DockerfileHandler()
        m = handler.extract_metadata('LABEL maintainer="me"')
        assert m["block_type"] == "LABEL"
        assert m["hierarchy"] == "label:maintainer"
        assert m["language_id"] == "dockerfile"

    def test_label_dotted_key(self):
        """LABEL with dotted key produces label:<key> hierarchy."""
        handler = DockerfileHandler()
        m = handler.extract_metadata(
            'LABEL org.opencontainers.image.title="CocoSearch"'
        )
        assert m["block_type"] == "LABEL"
        assert m["hierarchy"] == "label:org.opencontainers.image.title"

    def test_comment_before_instruction(self):
        """Comment line before instruction is correctly skipped."""
        handler = DockerfileHandler()
        m = handler.extract_metadata("# install deps\nRUN apt-get install")
        assert m["block_type"] == "RUN"
        assert m["hierarchy"] == ""
        assert m["language_id"] == "dockerfile"

    def test_comment_before_from(self):
        """Comment line before FROM is correctly skipped."""
        handler = DockerfileHandler()
        m = handler.extract_metadata("# base stage\nFROM golang:1.21 AS builder")
        assert m["block_type"] == "FROM"
        assert m["hierarchy"] == "stage:builder"
        assert m["language_id"] == "dockerfile"

    def test_leading_newline(self):
        """Leading newline from separator split is handled."""
        handler = DockerfileHandler()
        m = handler.extract_metadata("\nFROM golang:1.21 AS builder")
        assert m["block_type"] == "FROM"
        assert m["hierarchy"] == "stage:builder"
        assert m["language_id"] == "dockerfile"

    def test_unrecognized_content_returns_empty(self):
        """Unrecognized content produces empty block_type and hierarchy."""
        handler = DockerfileHandler()
        m = handler.extract_metadata('echo "not a dockerfile instruction"')
        assert m["block_type"] == ""
        assert m["hierarchy"] == ""
        assert m["language_id"] == "dockerfile"
