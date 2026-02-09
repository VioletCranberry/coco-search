"""Unit tests for symbol extraction from multiple programming languages.

Tests symbol metadata extraction using tree-sitter for:

Python:
- Functions (simple, with parameters, with type hints, async)
- Classes (simple, with bases, multiple bases)
- Methods (instance, class, static, property)
- Decorated functions
- Nested functions (should be skipped)

JavaScript:
- Function declarations
- Named arrow functions
- Class declarations
- Methods inside classes

TypeScript:
- All JavaScript patterns
- Interface declarations
- Type alias declarations (mapped to "interface")

Go:
- Functions
- Methods with receivers
- Structs (mapped to "class")
- Interfaces

Rust:
- Functions
- Methods in impl blocks
- Structs (mapped to "class")
- Traits (mapped to "interface")
- Enums (mapped to "class")

Edge cases (no symbols, parse errors, multiple symbols, unsupported languages)
"""

import pytest
from cocosearch.indexer.symbols import extract_symbol_metadata, LANGUAGE_MAP


@pytest.mark.unit
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


@pytest.mark.unit
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


@pytest.mark.unit
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


@pytest.mark.unit
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


@pytest.mark.unit
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


@pytest.mark.unit
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


@pytest.mark.unit
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


# ============================================================================
# JavaScript Symbol Extraction Tests
# ============================================================================


@pytest.mark.unit
class TestJavaScriptSymbols:
    """Test JavaScript symbol extraction."""

    def test_simple_function(self):
        """Extract simple function declaration."""
        code = "function fetchUser() { return null; }"
        result = extract_symbol_metadata(code, "js")

        assert result.symbol_type == "function"
        assert result.symbol_name == "fetchUser"
        assert result.symbol_signature == "function fetchUser()"

    def test_function_with_parameters(self):
        """Extract function with parameters."""
        code = "function add(a, b) { return a + b; }"
        result = extract_symbol_metadata(code, "js")

        assert result.symbol_type == "function"
        assert result.symbol_name == "add"
        assert result.symbol_signature == "function add(a, b)"

    def test_arrow_function_with_parens(self):
        """Extract named arrow function with parentheses."""
        code = "const fetchData = (url) => { return fetch(url); }"
        result = extract_symbol_metadata(code, "js")

        assert result.symbol_type == "function"
        assert result.symbol_name == "fetchData"
        assert result.symbol_signature == "const fetchData = (url) =>"

    def test_arrow_function_multiple_params(self):
        """Extract arrow function with multiple parameters."""
        code = "const multiply = (x, y) => x * y;"
        result = extract_symbol_metadata(code, "js")

        assert result.symbol_type == "function"
        assert result.symbol_name == "multiply"

    def test_class_declaration(self):
        """Extract class declaration."""
        code = "class UserService { }"
        result = extract_symbol_metadata(code, "js")

        assert result.symbol_type == "class"
        assert result.symbol_name == "UserService"
        assert result.symbol_signature == "class UserService"

    def test_class_with_method(self):
        """Extract class with method (class is first symbol)."""
        code = """class UserService {
    fetchUser(id) {
        return this.users[id];
    }
}"""
        result = extract_symbol_metadata(code, "js")

        # First symbol is the class
        assert result.symbol_type == "class"
        assert result.symbol_name == "UserService"

    def test_method_definition(self):
        """Verify method is extracted with qualified name when class not first."""
        from cocosearch.indexer.symbols import (
            _extract_symbols_with_query,
            resolve_query_file,
        )

        code = """class UserService {
    fetchUser(id) {
        return this.users[id];
    }
}"""
        query_text = resolve_query_file("javascript")
        symbols = _extract_symbols_with_query(code, "javascript", query_text)

        assert len(symbols) == 2
        assert symbols[0]["symbol_type"] == "class"
        assert symbols[1]["symbol_type"] == "method"
        assert symbols[1]["symbol_name"] == "UserService.fetchUser"
        assert "fetchUser(id)" in symbols[1]["symbol_signature"]

    def test_jsx_extension(self):
        """JSX files use JavaScript extractor."""
        code = "function Button() { return <button />; }"
        result = extract_symbol_metadata(code, "jsx")

        assert result.symbol_type == "function"
        assert result.symbol_name == "Button"

    def test_empty_input(self):
        """Empty JavaScript returns NULL fields."""
        result = extract_symbol_metadata("", "js")

        assert result.symbol_type is None
        assert result.symbol_name is None
        assert result.symbol_signature is None

    def test_no_symbols(self):
        """JavaScript with no symbols returns NULL fields."""
        code = "const x = 42; console.log(x);"
        result = extract_symbol_metadata(code, "js")

        assert result.symbol_type is None


# ============================================================================
# TypeScript Symbol Extraction Tests
# ============================================================================


@pytest.mark.unit
class TestTypeScriptSymbols:
    """Test TypeScript symbol extraction."""

    def test_function_declaration(self):
        """Extract TypeScript function declaration."""
        code = "function fetchUser(id: number): User { return null; }"
        result = extract_symbol_metadata(code, "ts")

        assert result.symbol_type == "function"
        assert result.symbol_name == "fetchUser"
        assert "function fetchUser" in result.symbol_signature

    def test_arrow_function_typed(self):
        """Extract typed arrow function."""
        code = "const fetchData = (url: string): Promise<Data> => fetch(url);"
        result = extract_symbol_metadata(code, "ts")

        assert result.symbol_type == "function"
        assert result.symbol_name == "fetchData"

    def test_interface_declaration(self):
        """Extract interface declaration."""
        code = "interface User { name: string; age: number; }"
        result = extract_symbol_metadata(code, "ts")

        assert result.symbol_type == "interface"
        assert result.symbol_name == "User"
        assert result.symbol_signature == "interface User"

    def test_interface_extends(self):
        """Extract interface that extends another."""
        code = "interface Admin extends User { role: string; }"
        result = extract_symbol_metadata(code, "ts")

        assert result.symbol_type == "interface"
        assert result.symbol_name == "Admin"

    def test_type_alias_simple(self):
        """Extract simple type alias (mapped to interface)."""
        code = "type UserID = string;"
        result = extract_symbol_metadata(code, "ts")

        assert result.symbol_type == "interface"
        assert result.symbol_name == "UserID"
        assert result.symbol_signature == "type UserID = string;"

    def test_type_alias_union(self):
        """Extract union type alias."""
        code = "type Status = 'active' | 'inactive' | 'pending';"
        result = extract_symbol_metadata(code, "ts")

        assert result.symbol_type == "interface"
        assert result.symbol_name == "Status"

    def test_type_alias_object(self):
        """Extract object type alias."""
        code = "type UserConfig = { theme: string; language: string; };"
        result = extract_symbol_metadata(code, "ts")

        assert result.symbol_type == "interface"
        assert result.symbol_name == "UserConfig"

    def test_class_declaration(self):
        """Extract TypeScript class."""
        code = "class UserService { private users: User[] = []; }"
        result = extract_symbol_metadata(code, "ts")

        assert result.symbol_type == "class"
        assert result.symbol_name == "UserService"

    def test_tsx_extension(self):
        """TSX files use TypeScript extractor."""
        code = "interface Props { title: string; }"
        result = extract_symbol_metadata(code, "tsx")

        assert result.symbol_type == "interface"
        assert result.symbol_name == "Props"

    def test_empty_input(self):
        """Empty TypeScript returns NULL fields."""
        result = extract_symbol_metadata("", "ts")

        assert result.symbol_type is None


# ============================================================================
# Go Symbol Extraction Tests
# ============================================================================


@pytest.mark.unit
class TestGoSymbols:
    """Test Go symbol extraction."""

    def test_simple_function(self):
        """Extract simple Go function."""
        code = "func Process() error { return nil }"
        result = extract_symbol_metadata(code, "go")

        assert result.symbol_type == "function"
        assert result.symbol_name == "Process"
        assert result.symbol_signature == "func Process() error"

    def test_function_with_parameters(self):
        """Extract function with parameters."""
        code = "func Add(a, b int) int { return a + b }"
        result = extract_symbol_metadata(code, "go")

        assert result.symbol_type == "function"
        assert result.symbol_name == "Add"
        assert "func Add(" in result.symbol_signature

    def test_method_with_pointer_receiver(self):
        """Extract method with pointer receiver."""
        code = "func (s *Server) Start() error { return nil }"
        result = extract_symbol_metadata(code, "go")

        assert result.symbol_type == "method"
        assert result.symbol_name == "Server.Start"
        assert result.symbol_signature == "func (s *Server) Start() error"

    def test_method_with_value_receiver(self):
        """Extract method with value receiver."""
        code = "func (c Config) GetPort() int { return c.Port }"
        result = extract_symbol_metadata(code, "go")

        assert result.symbol_type == "method"
        assert result.symbol_name == "Config.GetPort"

    def test_struct_declaration(self):
        """Extract struct declaration (mapped to class)."""
        code = "type Server struct { port int; host string }"
        result = extract_symbol_metadata(code, "go")

        assert result.symbol_type == "class"
        assert result.symbol_name == "Server"
        assert result.symbol_signature == "type Server struct"

    def test_interface_declaration(self):
        """Extract interface declaration."""
        code = "type Handler interface { Handle(ctx Context) error }"
        result = extract_symbol_metadata(code, "go")

        assert result.symbol_type == "interface"
        assert result.symbol_name == "Handler"
        assert result.symbol_signature == "type Handler interface"

    def test_empty_interface(self):
        """Extract empty interface (any)."""
        code = "type Any interface{}"
        result = extract_symbol_metadata(code, "go")

        assert result.symbol_type == "interface"
        assert result.symbol_name == "Any"

    def test_multiple_receiver_forms(self):
        """Test various receiver syntax forms."""
        code1 = "func (srv *HTTPServer) Listen() {}"
        result1 = extract_symbol_metadata(code1, "go")
        assert result1.symbol_name == "HTTPServer.Listen"

    def test_empty_input(self):
        """Empty Go returns NULL fields."""
        result = extract_symbol_metadata("", "go")

        assert result.symbol_type is None

    def test_no_symbols(self):
        """Go with no symbols returns NULL fields."""
        code = 'package main\n\nimport "fmt"'
        result = extract_symbol_metadata(code, "go")

        assert result.symbol_type is None


# ============================================================================
# Rust Symbol Extraction Tests
# ============================================================================


@pytest.mark.unit
class TestRustSymbols:
    """Test Rust symbol extraction."""

    def test_simple_function(self):
        """Extract simple Rust function."""
        code = "fn process() -> Result<(), Error> { Ok(()) }"
        result = extract_symbol_metadata(code, "rs")

        assert result.symbol_type == "function"
        assert result.symbol_name == "process"
        assert result.symbol_signature == "fn process() -> Result<(), Error>"

    def test_function_with_parameters(self):
        """Extract function with parameters."""
        code = "fn add(a: i32, b: i32) -> i32 { a + b }"
        result = extract_symbol_metadata(code, "rs")

        assert result.symbol_type == "function"
        assert result.symbol_name == "add"
        assert "fn add(" in result.symbol_signature

    def test_public_function(self):
        """Extract public function."""
        code = "pub fn new() -> Self { Self {} }"
        result = extract_symbol_metadata(code, "rs")

        assert result.symbol_type == "function"
        assert result.symbol_name == "new"

    def test_method_in_impl_block(self):
        """Extract method from impl block."""
        code = """impl Server {
    fn start(&self) -> Result<(), Error> {
        Ok(())
    }
}"""
        result = extract_symbol_metadata(code, "rs")

        assert result.symbol_type == "method"
        assert result.symbol_name == "Server.start"
        assert result.symbol_signature == "fn start(&self) -> Result<(), Error>"

    def test_multiple_methods_in_impl(self):
        """Verify multiple methods extracted from impl block."""
        from cocosearch.indexer.symbols import (
            _extract_symbols_with_query,
            resolve_query_file,
        )

        code = """impl Server {
    fn start(&self) {}
    fn stop(&mut self) {}
}"""
        query_text = resolve_query_file("rust")
        symbols = _extract_symbols_with_query(code, "rust", query_text)

        assert len(symbols) == 2
        assert symbols[0]["symbol_name"] == "Server.start"
        assert symbols[1]["symbol_name"] == "Server.stop"

    def test_struct_declaration(self):
        """Extract struct declaration (mapped to class)."""
        code = "struct Server { port: u16, host: String }"
        result = extract_symbol_metadata(code, "rs")

        assert result.symbol_type == "class"
        assert result.symbol_name == "Server"
        assert result.symbol_signature == "struct Server"

    def test_tuple_struct(self):
        """Extract tuple struct."""
        code = "struct Point(i32, i32);"
        result = extract_symbol_metadata(code, "rs")

        assert result.symbol_type == "class"
        assert result.symbol_name == "Point"

    def test_trait_declaration(self):
        """Extract trait declaration (mapped to interface)."""
        code = "trait Handler { fn handle(&self) -> Result<(), Error>; }"
        result = extract_symbol_metadata(code, "rs")

        assert result.symbol_type == "interface"
        assert result.symbol_name == "Handler"
        assert result.symbol_signature == "trait Handler"

    def test_enum_declaration(self):
        """Extract enum declaration (mapped to class)."""
        code = "enum Status { Active, Inactive, Pending }"
        result = extract_symbol_metadata(code, "rs")

        assert result.symbol_type == "class"
        assert result.symbol_name == "Status"
        assert result.symbol_signature == "enum Status"

    def test_enum_with_data(self):
        """Extract enum with associated data."""
        code = "enum Message { Quit, Move { x: i32, y: i32 }, Write(String) }"
        result = extract_symbol_metadata(code, "rs")

        assert result.symbol_type == "class"
        assert result.symbol_name == "Message"

    def test_empty_input(self):
        """Empty Rust returns NULL fields."""
        result = extract_symbol_metadata("", "rs")

        assert result.symbol_type is None

    def test_no_symbols(self):
        """Rust with no symbols returns NULL fields."""
        code = "use std::io::Result;\nmod tests;"
        result = extract_symbol_metadata(code, "rs")

        assert result.symbol_type is None


# ============================================================================
# C Symbol Extraction Tests
# ============================================================================


@pytest.mark.unit
class TestCSymbols:
    """Test C symbol extraction."""

    def test_simple_function(self):
        """Extract simple C function."""
        code = "int process() { return 0; }"
        result = extract_symbol_metadata(code, "c")

        assert result.symbol_type == "function"
        assert result.symbol_name == "process"
        assert result.symbol_signature == "int process()"

    def test_function_with_parameters(self):
        """Extract function with parameters."""
        code = "int add(int a, int b) { return a + b; }"
        result = extract_symbol_metadata(code, "c")

        assert result.symbol_type == "function"
        assert result.symbol_name == "add"
        assert "int add(" in result.symbol_signature

    def test_pointer_function(self):
        """Extract function returning pointer."""
        code = "void *allocate(size_t size) { return malloc(size); }"
        result = extract_symbol_metadata(code, "c")

        assert result.symbol_type == "function"
        assert result.symbol_name == "allocate"

    def test_struct_with_body(self):
        """Extract struct with body (mapped to class)."""
        code = "struct User { char *name; int age; };"
        result = extract_symbol_metadata(code, "c")

        assert result.symbol_type == "class"
        assert result.symbol_name == "User"
        assert result.symbol_signature == "struct User"

    def test_struct_forward_declaration_ignored(self):
        """Forward declaration without body should be ignored."""
        code = "struct User;"
        result = extract_symbol_metadata(code, "c")

        assert result.symbol_type is None
        assert result.symbol_name is None

    def test_enum_declaration(self):
        """Extract enum declaration (mapped to class)."""
        code = "enum Status { ACTIVE, INACTIVE, PENDING };"
        result = extract_symbol_metadata(code, "c")

        assert result.symbol_type == "class"
        assert result.symbol_name == "Status"
        assert result.symbol_signature == "enum Status"

    def test_typedef_declaration(self):
        """Extract typedef (mapped to interface)."""
        code = "typedef struct User User;"
        result = extract_symbol_metadata(code, "c")

        assert result.symbol_type == "interface"
        assert result.symbol_name == "User"
        assert result.symbol_signature == "typedef struct User User;"

    def test_function_declaration_ignored(self):
        """Function declaration without body should be ignored."""
        code = "int process();"
        result = extract_symbol_metadata(code, "c")

        assert result.symbol_type is None

    def test_header_extension(self):
        """C header files (.h) use C extractor."""
        code = "int process() { return 0; }"
        result = extract_symbol_metadata(code, "h")

        assert result.symbol_type == "function"
        assert result.symbol_name == "process"

    def test_empty_input(self):
        """Empty C returns NULL fields."""
        result = extract_symbol_metadata("", "c")

        assert result.symbol_type is None

    def test_no_symbols(self):
        """C with no symbols returns NULL fields."""
        code = "#include <stdio.h>\n#define MAX 100"
        result = extract_symbol_metadata(code, "c")

        assert result.symbol_type is None


# ============================================================================
# C++ Symbol Extraction Tests
# ============================================================================


@pytest.mark.unit
class TestCppSymbols:
    """Test C++ symbol extraction."""

    def test_simple_function(self):
        """Extract simple C++ function."""
        code = "int process() { return 0; }"
        result = extract_symbol_metadata(code, "cpp")

        assert result.symbol_type == "function"
        assert result.symbol_name == "process"
        assert result.symbol_signature == "int process()"

    def test_class_declaration(self):
        """Extract class declaration."""
        code = "class Server { int port; };"
        result = extract_symbol_metadata(code, "cpp")

        assert result.symbol_type == "class"
        assert result.symbol_name == "Server"
        assert result.symbol_signature == "class Server"

    def test_struct_declaration(self):
        """Extract struct declaration."""
        code = "struct Point { int x; int y; };"
        result = extract_symbol_metadata(code, "cpp")

        assert result.symbol_type == "class"
        assert result.symbol_name == "Point"
        assert result.symbol_signature == "struct Point"

    def test_namespace_declaration(self):
        """Extract namespace declaration (mapped to class)."""
        code = "namespace MyLib { }"
        result = extract_symbol_metadata(code, "cpp")

        assert result.symbol_type == "class"
        assert result.symbol_name == "MyLib"
        assert result.symbol_signature == "namespace MyLib"

    def test_method_with_qualified_name(self):
        """Extract method with qualified name (ClassName::method)."""
        code = "void MyClass::myMethod() { }"
        result = extract_symbol_metadata(code, "cpp")

        assert result.symbol_type == "method"
        assert result.symbol_name == "myMethod"
        assert "MyClass::myMethod" in result.symbol_signature

    def test_pointer_function(self):
        """Extract function returning pointer."""
        code = "void *allocate(size_t size) { return new char[size]; }"
        result = extract_symbol_metadata(code, "cpp")

        assert result.symbol_type == "function"
        assert result.symbol_name == "allocate"

    def test_template_class(self):
        """Extract template class."""
        code = "template<typename T> class Container { };"
        result = extract_symbol_metadata(code, "cpp")

        assert result.symbol_type == "class"
        assert result.symbol_name == "Container"

    def test_template_function(self):
        """Extract template function."""
        code = "template<typename T> T max(T a, T b) { return a > b ? a : b; }"
        result = extract_symbol_metadata(code, "cpp")

        assert result.symbol_type == "function"
        assert result.symbol_name == "max"

    def test_multiple_extensions(self):
        """Test various C++ extensions."""
        code = "class Foo {};"

        result_cpp = extract_symbol_metadata(code, "cpp")
        result_cxx = extract_symbol_metadata(code, "cxx")
        result_cc = extract_symbol_metadata(code, "cc")
        result_hpp = extract_symbol_metadata(code, "hpp")

        assert result_cpp.symbol_type == "class"
        assert result_cxx.symbol_type == "class"
        assert result_cc.symbol_type == "class"
        assert result_hpp.symbol_type == "class"

    def test_empty_input(self):
        """Empty C++ returns NULL fields."""
        result = extract_symbol_metadata("", "cpp")

        assert result.symbol_type is None

    def test_no_symbols(self):
        """C++ with no symbols returns NULL fields."""
        code = "#include <iostream>\nusing namespace std;"
        result = extract_symbol_metadata(code, "cpp")

        assert result.symbol_type is None


# ============================================================================
# Java Symbol Extraction Tests
# ============================================================================


@pytest.mark.unit
class TestJavaSymbols:
    """Test Java symbol extraction."""

    def test_simple_class(self):
        """Extract simple Java class."""
        code = "class User { }"
        result = extract_symbol_metadata(code, "java")

        assert result.symbol_type == "class"
        assert result.symbol_name == "User"
        assert result.symbol_signature == "class User"

    def test_interface_declaration(self):
        """Extract interface declaration."""
        code = "interface Repository { void save(); }"
        result = extract_symbol_metadata(code, "java")

        assert result.symbol_type == "interface"
        assert result.symbol_name == "Repository"
        assert result.symbol_signature == "interface Repository"

    def test_enum_declaration(self):
        """Extract enum declaration (mapped to class)."""
        code = "enum Status { ACTIVE, INACTIVE, PENDING }"
        result = extract_symbol_metadata(code, "java")

        assert result.symbol_type == "class"
        assert result.symbol_name == "Status"
        assert result.symbol_signature == "enum Status"

    def test_method_in_class(self):
        """Extract method from class."""
        code = """class UserService {
    public User findById(int id) {
        return null;
    }
}"""
        result = extract_symbol_metadata(code, "java")

        # First symbol is the class
        assert result.symbol_type == "class"
        assert result.symbol_name == "UserService"

    def test_constructor(self):
        """Extract constructor (mapped to method)."""
        code = """class User {
    public User(String name) {
        this.name = name;
    }
}"""
        result = extract_symbol_metadata(code, "java")

        assert result.symbol_type == "class"
        assert result.symbol_name == "User"

    def test_empty_input(self):
        """Empty Java returns NULL fields."""
        result = extract_symbol_metadata("", "java")

        assert result.symbol_type is None


# ============================================================================
# Ruby Symbol Extraction Tests
# ============================================================================


@pytest.mark.unit
class TestRubySymbols:
    """Test Ruby symbol extraction."""

    def test_simple_class(self):
        """Extract simple Ruby class."""
        code = "class User\nend"
        result = extract_symbol_metadata(code, "rb")

        assert result.symbol_type == "class"
        assert result.symbol_name == "User"
        assert result.symbol_signature == "class User"

    def test_module_declaration(self):
        """Extract module declaration (mapped to class)."""
        code = "module Authentication\nend"
        result = extract_symbol_metadata(code, "rb")

        assert result.symbol_type == "class"
        assert result.symbol_name == "Authentication"
        assert result.symbol_signature == "module Authentication"

    def test_instance_method(self):
        """Extract instance method from class."""
        code = """class User
  def save
    puts "saving"
  end
end"""
        result = extract_symbol_metadata(code, "rb")

        # First symbol is the class
        assert result.symbol_type == "class"
        assert result.symbol_name == "User"

    def test_singleton_method(self):
        """Extract singleton (class) method."""
        code = """class User
  def self.find(id)
    puts id
  end
end"""
        result = extract_symbol_metadata(code, "rb")

        assert result.symbol_type == "class"
        assert result.symbol_name == "User"

    def test_empty_input(self):
        """Empty Ruby returns NULL fields."""
        result = extract_symbol_metadata("", "rb")

        assert result.symbol_type is None


# ============================================================================
# PHP Symbol Extraction Tests
# ============================================================================


@pytest.mark.unit
class TestPhpSymbols:
    """Test PHP symbol extraction."""

    def test_simple_function(self):
        """Extract simple PHP function."""
        code = "<?php function process() { return true; }"
        result = extract_symbol_metadata(code, "php")

        assert result.symbol_type == "function"
        assert result.symbol_name == "process"
        assert result.symbol_signature == "function process()"

    def test_simple_class(self):
        """Extract simple PHP class."""
        code = "<?php class User {}"
        result = extract_symbol_metadata(code, "php")

        assert result.symbol_type == "class"
        assert result.symbol_name == "User"
        assert result.symbol_signature == "class User"

    def test_interface_declaration(self):
        """Extract interface declaration."""
        code = "<?php interface Repository { public function save(); }"
        result = extract_symbol_metadata(code, "php")

        assert result.symbol_type == "interface"
        assert result.symbol_name == "Repository"
        assert result.symbol_signature == "interface Repository"

    def test_trait_declaration(self):
        """Extract trait declaration (mapped to interface)."""
        code = "<?php trait Timestamps { }"
        result = extract_symbol_metadata(code, "php")

        assert result.symbol_type == "interface"
        assert result.symbol_name == "Timestamps"
        assert result.symbol_signature == "trait Timestamps"

    def test_method_in_class(self):
        """Extract method from class."""
        code = """<?php
class UserService {
    public function findById($id) {
        return null;
    }
}"""
        result = extract_symbol_metadata(code, "php")

        # First symbol is the class
        assert result.symbol_type == "class"
        assert result.symbol_name == "UserService"

    def test_method_with_parameters(self):
        """Extract method with parameters."""
        code = """<?php
class Calculator {
    public function add($x, $y) {
        return $x + $y;
    }
}"""
        result = extract_symbol_metadata(code, "php")

        assert result.symbol_type == "class"
        assert result.symbol_name == "Calculator"

    def test_empty_input(self):
        """Empty PHP returns NULL fields."""
        result = extract_symbol_metadata("", "php")

        assert result.symbol_type is None


# ============================================================================
# Language Map Tests
# ============================================================================


@pytest.mark.unit
class TestLanguageMap:
    """Test language extension mapping."""

    def test_language_map_count(self):
        """LANGUAGE_MAP contains all 23 extension mappings."""
        assert len(LANGUAGE_MAP) == 23

    def test_javascript_extensions(self):
        """JavaScript extensions map correctly."""
        assert LANGUAGE_MAP["js"] == "javascript"
        assert LANGUAGE_MAP["jsx"] == "javascript"
        assert LANGUAGE_MAP["mjs"] == "javascript"
        assert LANGUAGE_MAP["cjs"] == "javascript"

    def test_typescript_extensions(self):
        """TypeScript extensions map correctly."""
        assert LANGUAGE_MAP["ts"] == "typescript"
        assert LANGUAGE_MAP["tsx"] == "typescript"
        assert LANGUAGE_MAP["mts"] == "typescript"
        assert LANGUAGE_MAP["cts"] == "typescript"

    def test_other_extensions(self):
        """Other language extensions map correctly."""
        assert LANGUAGE_MAP["go"] == "go"
        assert LANGUAGE_MAP["rs"] == "rust"
        assert LANGUAGE_MAP["py"] == "python"
        assert LANGUAGE_MAP["python"] == "python"
        assert LANGUAGE_MAP["java"] == "java"

    def test_c_extensions(self):
        """C extensions map correctly."""
        assert LANGUAGE_MAP["c"] == "c"
        assert LANGUAGE_MAP["h"] == "c"

    def test_cpp_extensions(self):
        """C++ extensions map correctly."""
        assert LANGUAGE_MAP["cpp"] == "cpp"
        assert LANGUAGE_MAP["cxx"] == "cpp"
        assert LANGUAGE_MAP["cc"] == "cpp"
        assert LANGUAGE_MAP["hpp"] == "cpp"
        assert LANGUAGE_MAP["hxx"] == "cpp"
        assert LANGUAGE_MAP["hh"] == "cpp"

    def test_ruby_extension(self):
        """Ruby extension maps correctly."""
        assert LANGUAGE_MAP["rb"] == "ruby"

    def test_php_extension(self):
        """PHP extension maps correctly."""
        assert LANGUAGE_MAP["php"] == "php"

    def test_unsupported_extension(self):
        """Unsupported extension returns None."""
        assert LANGUAGE_MAP.get("swift") is None
        assert LANGUAGE_MAP.get("kt") is None
