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
    """After the split, there should be no inline <script> blocks (only src-based).

    Exception: the FOUC-prevention script that applies the theme attribute
    synchronously before stylesheets paint. It is identified by the
    'cocosearch-theme' localStorage key string.
    """
    for script in soup.find_all("script"):
        if script.string and script.string.strip():
            if "cocosearch-theme" in script.string:
                continue  # FOUC prevention script is allowed
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
        "logs.js",
        "theme.js",
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
        "./logs.js",
        "./theme.js",
    ]
    for module in expected_imports:
        assert module in content, f"app.js missing import from '{module}'"


def test_deps_graph_modal_exists(soup):
    """The dependency graph modal backdrop and SVG must exist."""
    backdrop = soup.find(id="depsGraphBackdrop")
    assert backdrop is not None, "Missing #depsGraphBackdrop element"
    svg = soup.find(id="depsGraphSvg")
    assert svg is not None, "Missing #depsGraphSvg element"


def test_deps_checkbox_exists(soup):
    """The searchIncludeDeps checkbox must exist in the HTML."""
    checkbox = soup.find(id="searchIncludeDeps")
    assert checkbox is not None, "Missing #searchIncludeDeps checkbox"
    assert checkbox.get("type") == "checkbox", "searchIncludeDeps should be a checkbox"


def test_linked_indexes_card_exists(soup):
    """The linked indexes summary card must exist with its child elements."""
    card = soup.find(id="linkedIndexesCard")
    assert card is not None, "Missing #linkedIndexesCard element"
    assert "linked-indexes-card" in card.get("class", []), (
        "linkedIndexesCard should have 'linked-indexes-card' class"
    )
    # Card should be hidden by default
    assert card.get("style") and "display: none" in card["style"], (
        "linkedIndexesCard should be hidden by default"
    )
    # Child elements
    count_el = soup.find(id="linkedIndexesCount")
    assert count_el is not None, "Missing #linkedIndexesCount element"
    names_el = soup.find(id="linkedIndexesNames")
    assert names_el is not None, "Missing #linkedIndexesNames element"
    warnings_el = soup.find(id="linkedIndexWarnings")
    assert warnings_el is not None, "Missing #linkedIndexWarnings element"
    assert "linked-warnings" in warnings_el.get("class", []), (
        "linkedIndexWarnings should have 'linked-warnings' class"
    )


def test_deps_graph_depth_selector_exists(soup):
    """The depth selector for the dependency graph modal must exist."""
    select = soup.find(id="depsGraphDepth")
    assert select is not None, "Missing #depsGraphDepth select element"
    options = select.find_all("option")
    values = [opt.get("value") for opt in options]
    assert "1" in values and "3" in values, (
        f"Expected depth options 1 and 3, got {values}"
    )


# --- Light mode (theme toggle) ---


def test_theme_toggle_button_exists(soup):
    """Header must contain the theme toggle button inside the status line."""
    btn = soup.find(id="themeToggleBtn")
    assert btn is not None, "Missing #themeToggleBtn"
    assert "theme-btn" in btn.get("class", []), (
        "themeToggleBtn must have class 'theme-btn'"
    )
    status_line = soup.find(class_="terminal-status-line")
    assert status_line is not None, "Missing .terminal-status-line container"
    assert btn in status_line.find_all(id="themeToggleBtn"), (
        "themeToggleBtn must live inside .terminal-status-line"
    )


def test_both_prism_themes_linked(soup):
    """Both Prism syntax themes must be linked, with the light one starting disabled."""
    dark = soup.find(id="prismThemeDark")
    light = soup.find(id="prismThemeLight")
    assert dark is not None, "Missing #prismThemeDark <link>"
    assert "prism-tomorrow" in dark.get("href", ""), (
        "prismThemeDark should point at prism-tomorrow"
    )
    assert light is not None, "Missing #prismThemeLight <link>"
    assert "prismjs@" in light.get("href", ""), (
        "prismThemeLight should be a prismjs CDN stylesheet"
    )
    assert light.has_attr("disabled"), (
        "prismThemeLight should start disabled so dark renders by default"
    )


def test_fouc_prevention_script_present(soup):
    """The inline FOUC script must be in <head> and run before styles.css paints."""
    scripts = [
        s
        for s in soup.find_all("script")
        if s.string and "cocosearch-theme" in s.string
    ]
    assert len(scripts) == 1, (
        f"Expected exactly one FOUC prevention inline script, got {len(scripts)}"
    )
    head = soup.find("head")
    head_children = [c for c in head.children if getattr(c, "name", None)]
    styles_link = next(
        (
            c
            for c in head_children
            if c.name == "link" and "styles.css" in (c.get("href") or "")
        ),
        None,
    )
    assert styles_link is not None, "Could not find styles.css <link> in <head>"
    script_tag = scripts[0]
    assert head_children.index(script_tag) < head_children.index(styles_link), (
        "FOUC script must appear before styles.css to avoid a flash of dark content"
    )


def test_light_theme_css_vars_defined():
    """styles.css must define a [data-theme=light] block with the expected overrides."""
    content = (CSS_DIR / "styles.css").read_text()
    assert ':root[data-theme="light"]' in content, (
        "Missing :root[data-theme='light'] block in styles.css"
    )
    light_block = content.split(':root[data-theme="light"]', 1)[1].split("}", 1)[0]
    required = [
        "--bg-primary",
        "--text-primary",
        "--accent-orange",
        "--border-color",
        "--log-cat-search",
        "--log-tab-indexed-primary",
    ]
    for var in required:
        assert var in light_block, f"Light theme block missing override for {var}"


def test_crt_effects_disabled_in_light_mode():
    """Light mode must hide the CRT scanlines and vignette."""
    content = (CSS_DIR / "styles.css").read_text()
    assert ':root[data-theme="light"] body::before' in content, (
        "Missing rule to hide body::before scanlines in light mode"
    )
    assert ':root[data-theme="light"] body::after' in content, (
        "Missing rule to hide body::after vignette in light mode"
    )
