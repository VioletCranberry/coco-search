"""Tests for cocosearch.handlers registry autodiscovery and public API."""

import pytest

from cocosearch.handlers import (
    get_handler,
    get_custom_languages,
    _HANDLER_REGISTRY,
)
from cocosearch.handlers.hcl import HclHandler
from cocosearch.handlers.dockerfile import DockerfileHandler
from cocosearch.handlers.bash import BashHandler
from cocosearch.handlers.text import TextHandler


@pytest.mark.unit
class TestHandlerRegistryDiscovery:
    """Tests for handler registry autodiscovery."""

    def test_discover_finds_all_handlers(self):
        """_HANDLER_REGISTRY should have at least 4 handlers registered."""
        # Should have .tf, .hcl, .tfvars, .dockerfile, .sh, .bash, .zsh, .tpl, .gotmpl
        assert len(_HANDLER_REGISTRY) >= 9

    def test_template_excluded_from_discovery(self):
        """_template.py should be excluded from discovery."""
        # No extension starting with underscore should be in registry
        for ext in _HANDLER_REGISTRY.keys():
            assert not ext.startswith("_"), (
                f"Template extension {ext} should not be registered"
            )

    def test_hcl_extensions_registered(self):
        """.tf, .hcl, and .tfvars should be in registry."""
        assert ".tf" in _HANDLER_REGISTRY
        assert ".hcl" in _HANDLER_REGISTRY
        assert ".tfvars" in _HANDLER_REGISTRY

    def test_dockerfile_extension_registered(self):
        """.dockerfile should be in registry."""
        assert ".dockerfile" in _HANDLER_REGISTRY

    def test_bash_extensions_registered(self):
        """.sh, .bash, and .zsh should be in registry."""
        assert ".sh" in _HANDLER_REGISTRY
        assert ".bash" in _HANDLER_REGISTRY
        assert ".zsh" in _HANDLER_REGISTRY

    def test_all_hcl_extensions_map_to_same_handler(self):
        """All HCL extensions should map to the same handler instance."""
        handler_tf = _HANDLER_REGISTRY[".tf"]
        handler_hcl = _HANDLER_REGISTRY[".hcl"]
        handler_tfvars = _HANDLER_REGISTRY[".tfvars"]
        assert handler_tf is handler_hcl
        assert handler_hcl is handler_tfvars

    def test_all_bash_extensions_map_to_same_handler(self):
        """All Bash extensions should map to the same handler instance."""
        handler_sh = _HANDLER_REGISTRY[".sh"]
        handler_bash = _HANDLER_REGISTRY[".bash"]
        handler_zsh = _HANDLER_REGISTRY[".zsh"]
        assert handler_sh is handler_bash
        assert handler_bash is handler_zsh


@pytest.mark.unit
class TestGetHandler:
    """Tests for get_handler() public API."""

    def test_get_handler_tf_returns_hcl_handler(self):
        """get_handler('.tf') should return HclHandler."""
        handler = get_handler(".tf")
        assert isinstance(handler, HclHandler)

    def test_get_handler_hcl_returns_hcl_handler(self):
        """get_handler('.hcl') should return HclHandler."""
        handler = get_handler(".hcl")
        assert isinstance(handler, HclHandler)

    def test_get_handler_tfvars_returns_hcl_handler(self):
        """get_handler('.tfvars') should return HclHandler."""
        handler = get_handler(".tfvars")
        assert isinstance(handler, HclHandler)

    def test_get_handler_dockerfile_returns_dockerfile_handler(self):
        """get_handler('.dockerfile') should return DockerfileHandler."""
        handler = get_handler(".dockerfile")
        assert isinstance(handler, DockerfileHandler)

    def test_get_handler_sh_returns_bash_handler(self):
        """get_handler('.sh') should return BashHandler."""
        handler = get_handler(".sh")
        assert isinstance(handler, BashHandler)

    def test_get_handler_bash_returns_bash_handler(self):
        """get_handler('.bash') should return BashHandler."""
        handler = get_handler(".bash")
        assert isinstance(handler, BashHandler)

    def test_get_handler_zsh_returns_bash_handler(self):
        """get_handler('.zsh') should return BashHandler."""
        handler = get_handler(".zsh")
        assert isinstance(handler, BashHandler)

    def test_get_handler_unknown_returns_text_handler(self):
        """get_handler() with unknown extension should return TextHandler."""
        handler = get_handler(".unknown")
        assert isinstance(handler, TextHandler)

    def test_get_handler_py_returns_text_handler(self):
        """get_handler('.py') should return TextHandler (not a handler language)."""
        handler = get_handler(".py")
        assert isinstance(handler, TextHandler)

    def test_get_handler_js_returns_text_handler(self):
        """get_handler('.js') should return TextHandler (not a handler language)."""
        handler = get_handler(".js")
        assert isinstance(handler, TextHandler)


@pytest.mark.unit
class TestGetCustomLanguages:
    """Tests for get_custom_languages() public API."""

    def test_returns_list_of_specs(self):
        """get_custom_languages() should return a list."""
        specs = get_custom_languages()
        assert isinstance(specs, list)

    def test_returns_twelve_specs(self):
        """get_custom_languages() should return 12 specs (6 language + 6 grammar)."""
        specs = get_custom_languages()
        assert len(specs) == 12

    def test_all_specs_have_language_name(self):
        """All specs should have language_name attribute."""
        specs = get_custom_languages()
        for spec in specs:
            assert hasattr(spec, "language_name")
            assert spec.language_name != ""

    def test_spec_language_names(self):
        """Specs should include hcl, dockerfile, and bash language names."""
        specs = get_custom_languages()
        language_names = {spec.language_name for spec in specs}
        assert "hcl" in language_names
        assert "dockerfile" in language_names
        assert "bash" in language_names

    def test_no_duplicate_specs(self):
        """get_custom_languages() should not return duplicate specs."""
        specs = get_custom_languages()
        # Check by object identity (id)
        spec_ids = [id(spec) for spec in specs]
        assert len(spec_ids) == len(set(spec_ids)), "Duplicate specs found"


@pytest.mark.unit
class TestTextHandlerNotInRegistry:
    """Tests for TextHandler fallback behavior."""

    def test_text_handler_has_empty_extensions(self):
        """TextHandler should have empty EXTENSIONS list."""
        handler = TextHandler()
        assert handler.EXTENSIONS == []

    def test_text_handler_not_in_registry(self):
        """TextHandler should not be registered for any extension."""
        # No extension should map to TextHandler in registry
        for ext, handler in _HANDLER_REGISTRY.items():
            assert not isinstance(handler, TextHandler), (
                f"TextHandler should not be in registry, found at {ext}"
            )

    def test_text_handler_used_as_fallback(self):
        """TextHandler should be used as fallback via get_handler()."""
        handler = get_handler(".unknown")
        assert isinstance(handler, TextHandler)
