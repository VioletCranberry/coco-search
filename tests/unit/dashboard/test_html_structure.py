"""Tests that validate HTML structure against JS module references.

These tests catch breakage from the dashboard split by ensuring:
- All element IDs referenced in JS exist in HTML
- All static file references point to real files on disk
- All JS module imports resolve to existing files
- The HTML is well-formed
"""

import re

from tests.unit.dashboard.conftest import CSS_DIR, JS_DIR, STATIC_DIR


def test_required_ids_exist(soup, referenced_ids):
    """All getElementById('...') calls in JS must have matching id in HTML."""
    html_ids = {tag["id"] for tag in soup.find_all(id=True)}

    missing = referenced_ids - html_ids
    assert not missing, (
        f"JS references these element IDs that don't exist in HTML: {sorted(missing)}"
    )


def test_js_files_exist(soup):
    """Every <script src="/static/..."> in HTML must point to a real file."""
    for script in soup.find_all("script", src=True):
        src = script["src"]
        if not src.startswith("/static/"):
            continue
        rel_path = src.removeprefix("/static/")
        file_path = STATIC_DIR / rel_path
        assert file_path.is_file(), f"Script src references missing file: {src}"


def test_css_files_exist(soup):
    """Every <link href="/static/..."> must point to a real file."""
    for link in soup.find_all("link", href=True):
        href = link["href"]
        if not href.startswith("/static/"):
            continue
        rel_path = href.removeprefix("/static/")
        file_path = STATIC_DIR / rel_path
        assert file_path.is_file(), f"CSS link references missing file: {href}"


def test_module_imports_resolve(js_files):
    """All import ... from './...' statements in JS must resolve to existing files."""
    import_pattern = re.compile(r"""from\s+['"](\./[^'"]+)['"]""")

    for filename, content in js_files.items():
        source_path = JS_DIR / filename
        for match in import_pattern.finditer(content):
            import_path = match.group(1)
            resolved = (source_path.parent / import_path).resolve()
            assert resolved.is_file(), (
                f"{filename}: import from '{import_path}' resolves to "
                f"missing file: {resolved}"
            )


def test_html_is_well_formed(soup):
    """HTML must parse without structural errors."""
    # BeautifulSoup is lenient, but we can check for basic structure
    assert soup.find("html") is not None, "Missing <html> tag"
    assert soup.find("head") is not None, "Missing <head> tag"
    assert soup.find("body") is not None, "Missing <body> tag"
    # The title should exist
    title = soup.find("title")
    assert title is not None, "Missing <title> tag"
    assert "Coco" in title.string, "Title doesn't contain expected text"


def test_no_inline_script_blocks(soup):
    """After the split, there should be no inline <script> blocks (only src-based)."""
    for script in soup.find_all("script"):
        if script.string and script.string.strip():
            # Allow CDN scripts that might have inline fallbacks
            assert False, (
                f"Found inline <script> block with content: {script.string[:80]}..."
            )


def test_no_inline_style_blocks(soup):
    """After the split, there should be no inline <style> blocks."""
    style_tags = soup.find_all("style")
    assert len(style_tags) == 0, (
        f"Found {len(style_tags)} inline <style> block(s) — "
        f"CSS should be in external files"
    )


def test_app_js_is_module(soup):
    """The app.js script tag must use type='module'."""
    app_scripts = [s for s in soup.find_all("script", src=True) if "app.js" in s["src"]]
    assert len(app_scripts) == 1, "Expected exactly one app.js script tag"
    assert app_scripts[0].get("type") == "module", (
        "app.js must be loaded as type='module'"
    )


def test_css_file_not_empty():
    """The extracted CSS file must have substantial content."""
    css_path = CSS_DIR / "styles.css"
    assert css_path.is_file(), "styles.css not found"
    content = css_path.read_text()
    # Original CSS was ~1450 lines
    assert len(content.splitlines()) > 1000, (
        f"styles.css seems too small ({len(content.splitlines())} lines) — "
        f"expected the full extracted CSS"
    )


def test_all_expected_js_modules_exist():
    """All planned JS modules must exist."""
    expected_modules = [
        "app.js",
        "state.js",
        "api.js",
        "utils.js",
        "charts.js",
        "dashboard.js",
        "index-mgmt.js",
        "search.js",
        "chat.js",
        "logs.js",
    ]
    for module in expected_modules:
        path = JS_DIR / module
        assert path.is_file(), f"Expected JS module not found: {module}"


def test_state_module_exports_state():
    """state.js must export the shared state object."""
    content = (JS_DIR / "state.js").read_text()
    assert "export const state" in content, "state.js must export a 'state' constant"


def test_app_js_imports_all_modules():
    """app.js should import from all other modules."""
    content = (JS_DIR / "app.js").read_text()
    expected_imports = [
        "./state.js",
        "./utils.js",
        "./dashboard.js",
        "./index-mgmt.js",
        "./search.js",
        "./chat.js",
        "./logs.js",
    ]
    for module in expected_imports:
        assert module in content, f"app.js missing import from '{module}'"
