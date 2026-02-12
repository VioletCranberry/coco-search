"""Tests for Python symbol extraction."""

from cocosearch.indexer.symbols import extract_symbol_metadata


class TestFunctionExtraction:
    """Test function symbol extraction."""

    def test_simple_function(self):
        """Extract simple function definition."""
        code = "def foo(): pass"
        result = extract_symbol_metadata(code, "py")

        assert result.symbol_type == "function"
        assert result.symbol_name == "foo"
        assert result.symbol_signature == "def foo():"

    def test_function_with_parameters(self):
        """Extract function with parameters."""
        code = "def bar(x, y=10): pass"
        result = extract_symbol_metadata(code, "py")

        assert result.symbol_type == "function"
        assert result.symbol_name == "bar"
        assert result.symbol_signature == "def bar(x, y=10):"

    def test_function_with_type_hints(self):
        """Extract function with type hints."""
        code = "def baz(x: int, y: str = 'default') -> dict:\n    pass"
        result = extract_symbol_metadata(code, "py")

        assert result.symbol_type == "function"
        assert result.symbol_name == "baz"
        assert result.symbol_signature == "def baz(x: int, y: str = 'default') -> dict:"

    def test_async_function(self):
        """Extract async function."""
        code = "async def fetch(url: str) -> str:\n    pass"
        result = extract_symbol_metadata(code, "py")

        assert result.symbol_type == "function"
        assert result.symbol_name == "fetch"
        assert result.symbol_signature == "async def fetch(url: str) -> str:"

    def test_decorated_function(self):
        """Extract decorated function (decorator not in signature)."""
        code = "@property\ndef name(self):\n    pass"
        result = extract_symbol_metadata(code, "py")

        assert result.symbol_type == "function"
        assert result.symbol_name == "name"
        assert result.symbol_signature == "def name(self):"

    def test_multiple_decorators(self):
        """Extract function with multiple decorators."""
        code = """@staticmethod
@lru_cache(maxsize=128)
def compute(x: int) -> int:
    pass"""
        result = extract_symbol_metadata(code, "py")

        assert result.symbol_type == "function"
        assert result.symbol_name == "compute"
        assert "def compute(x: int) -> int:" in result.symbol_signature


class TestClassExtraction:
    """Test class symbol extraction."""

    def test_simple_class(self):
        """Extract simple class definition."""
        code = "class Foo:\n    pass"
        result = extract_symbol_metadata(code, "py")

        assert result.symbol_type == "class"
        assert result.symbol_name == "Foo"
        assert result.symbol_signature == "class Foo:"

    def test_class_with_base(self):
        """Extract class with single base class."""
        code = "class Bar(Foo):\n    pass"
        result = extract_symbol_metadata(code, "py")

        assert result.symbol_type == "class"
        assert result.symbol_name == "Bar"
        assert result.symbol_signature == "class Bar(Foo):"

    def test_class_with_multiple_bases(self):
        """Extract class with multiple base classes."""
        code = "class Baz(Foo, Mixin):\n    pass"
        result = extract_symbol_metadata(code, "py")

        assert result.symbol_type == "class"
        assert result.symbol_name == "Baz"
        assert result.symbol_signature == "class Baz(Foo, Mixin):"

    def test_class_with_generic_bases(self):
        """Extract class with generic/parameterized bases."""
        code = "class Container(Generic[T], Iterable[T]):\n    pass"
        result = extract_symbol_metadata(code, "py")

        assert result.symbol_type == "class"
        assert result.symbol_name == "Container"
        assert "Generic[T]" in result.symbol_signature


class TestMethodExtraction:
    """Test method symbol extraction."""

    def test_instance_method(self):
        """Extract instance method with qualified name."""
        code = """class MyClass:
    def my_method(self):
        pass
"""
        result = extract_symbol_metadata(code, "py")

        # First symbol in chunk is the class
        assert result.symbol_type == "class"
        assert result.symbol_name == "MyClass"

    def test_method_with_parameters(self):
        """Extract method with parameters."""
        code = """class Calculator:
    def add(self, x: int, y: int) -> int:
        return x + y
"""
        result = extract_symbol_metadata(code, "py")

        assert result.symbol_type == "class"
        assert result.symbol_name == "Calculator"

    def test_classmethod(self):
        """Extract classmethod (decorator doesn't change symbol_type)."""
        code = """class MyClass:
    @classmethod
    def from_dict(cls, data: dict):
        pass
"""
        result = extract_symbol_metadata(code, "py")

        assert result.symbol_type == "class"
        assert result.symbol_name == "MyClass"

    def test_staticmethod(self):
        """Extract staticmethod."""
        code = """class Utils:
    @staticmethod
    def helper(x: int) -> str:
        pass
"""
        result = extract_symbol_metadata(code, "py")

        assert result.symbol_type == "class"
        assert result.symbol_name == "Utils"

    def test_property_method(self):
        """Extract property method."""
        code = """class Person:
    @property
    def name(self) -> str:
        pass
"""
        result = extract_symbol_metadata(code, "py")

        assert result.symbol_type == "class"
        assert result.symbol_name == "Person"

    def test_async_method(self):
        """Extract async method."""
        code = """class AsyncClient:
    async def fetch(self, url: str) -> str:
        pass
"""
        result = extract_symbol_metadata(code, "py")

        assert result.symbol_type == "class"
        assert result.symbol_name == "AsyncClient"


class TestNestedFunctions:
    """Test that nested functions are skipped."""

    def test_nested_function_skipped(self):
        """Nested function should not appear as symbol."""
        code = """def outer():
    def inner():
        pass
    return inner
"""
        result = extract_symbol_metadata(code, "py")

        # Should return outer function only
        assert result.symbol_type == "function"
        assert result.symbol_name == "outer"
        assert "inner" not in result.symbol_name

    def test_helper_in_method_skipped(self):
        """Helper function inside method should be skipped."""
        code = """class MyClass:
    def process(self):
        def helper(x):
            return x * 2
        return helper(10)
"""
        result = extract_symbol_metadata(code, "py")

        # Should return class (first symbol)
        assert result.symbol_type == "class"
        assert result.symbol_name == "MyClass"


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_string(self):
        """Empty input returns NULL fields."""
        result = extract_symbol_metadata("", "py")

        assert result.symbol_type is None
        assert result.symbol_name is None
        assert result.symbol_signature is None

    def test_whitespace_only(self):
        """Whitespace-only input returns NULL fields."""
        result = extract_symbol_metadata("   \n\n   ", "py")

        assert result.symbol_type is None
        assert result.symbol_name is None
        assert result.symbol_signature is None

    def test_no_symbols(self):
        """Code with no symbols returns NULL fields."""
        code = """x = 42
y = 'hello'
z = [1, 2, 3]
"""
        result = extract_symbol_metadata(code, "py")

        assert result.symbol_type is None
        assert result.symbol_name is None
        assert result.symbol_signature is None

    def test_syntax_error(self):
        """Syntax error returns NULL fields without crashing."""
        code = "def foo("  # Incomplete function
        result = extract_symbol_metadata(code, "py")

        # Should return NULL fields, not crash
        assert result.symbol_type is None
        assert result.symbol_name is None
        assert result.symbol_signature is None

    def test_partial_code(self):
        """Partial code (chunk boundary) returns NULL or partial."""
        code = "    pass"  # Just pass statement
        result = extract_symbol_metadata(code, "py")

        assert result.symbol_type is None

    def test_unsupported_language(self):
        """Unsupported language returns NULL fields."""
        code = "def foo(): pass"
        result = extract_symbol_metadata(code, "ruby")  # Ruby not supported

        assert result.symbol_type is None
        assert result.symbol_name is None
        assert result.symbol_signature is None

    def test_multiple_symbols_returns_first(self):
        """Multiple symbols in chunk returns first one."""
        code = """def foo():
    pass

def bar():
    pass
"""
        result = extract_symbol_metadata(code, "py")

        # Should return first symbol
        assert result.symbol_type == "function"
        assert result.symbol_name == "foo"

    def test_class_and_function(self):
        """Class and function in same chunk returns first."""
        code = """class MyClass:
    pass

def my_function():
    pass
"""
        result = extract_symbol_metadata(code, "py")

        # Should return first symbol (class)
        assert result.symbol_type == "class"
        assert result.symbol_name == "MyClass"


class TestComplexCases:
    """Test complex real-world code patterns."""

    def test_complex_type_hints(self):
        """Extract function with complex type hints."""
        code = """def process(
    data: list[dict[str, Any]],
    limit: int = 10,
    callback: Callable[[str], None] | None = None
) -> dict[str, list[str]]:
    pass
"""
        result = extract_symbol_metadata(code, "py")

        assert result.symbol_type == "function"
        assert result.symbol_name == "process"
        assert "def process(" in result.symbol_signature
        assert "-> dict[str, list[str]]:" in result.symbol_signature

    def test_multiline_signature(self):
        """Extract function with multiline signature."""
        code = """def long_function(
    param1: int,
    param2: str,
    param3: bool = True
) -> tuple[int, str]:
    pass
"""
        result = extract_symbol_metadata(code, "py")

        assert result.symbol_type == "function"
        assert result.symbol_name == "long_function"
        assert "tuple[int, str]:" in result.symbol_signature

    def test_class_with_docstring(self):
        """Extract class that has docstring."""
        code = '''class MyClass:
    """This is a class docstring."""

    def method(self):
        """Method docstring."""
        pass
'''
        result = extract_symbol_metadata(code, "py")

        assert result.symbol_type == "class"
        assert result.symbol_name == "MyClass"

    def test_async_context_manager(self):
        """Extract async context manager methods."""
        code = """class AsyncResource:
    async def __aenter__(self):
        pass

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
"""
        result = extract_symbol_metadata(code, "py")

        assert result.symbol_type == "class"
        assert result.symbol_name == "AsyncResource"

    def test_function_with_decorator_args(self):
        """Extract function with decorator that has arguments."""
        code = """@app.route('/api/users', methods=['GET', 'POST'])
@require_auth(role='admin')
def users_endpoint(request):
    pass
"""
        result = extract_symbol_metadata(code, "py")

        assert result.symbol_type == "function"
        assert result.symbol_name == "users_endpoint"

    def test_nested_class(self):
        """Extract outer class (nested class is not a top-level symbol)."""
        code = """class Outer:
    class Inner:
        pass
"""
        result = extract_symbol_metadata(code, "py")

        # Should return outer class
        assert result.symbol_type == "class"
        assert result.symbol_name == "Outer"


class TestReturnTypeFormats:
    """Test various return type annotation formats."""

    def test_simple_return_type(self):
        """Extract function with simple return type."""
        code = "def foo() -> int:\n    pass"
        result = extract_symbol_metadata(code, "py")

        assert "-> int" in result.symbol_signature

    def test_optional_return_type(self):
        """Extract function with Optional return type."""
        code = "def maybe() -> str | None:\n    pass"
        result = extract_symbol_metadata(code, "py")

        assert "-> str | None" in result.symbol_signature

    def test_generic_return_type(self):
        """Extract function with generic return type."""
        code = "def items() -> list[tuple[str, int]]:\n    pass"
        result = extract_symbol_metadata(code, "py")

        assert "-> list[tuple[str, int]]" in result.symbol_signature

    def test_callable_return_type(self):
        """Extract function returning callable."""
        code = "def factory() -> Callable[[int], str]:\n    pass"
        result = extract_symbol_metadata(code, "py")

        assert "-> Callable[[int], str]" in result.symbol_signature
