"""Web dashboard module for cocosearch.

Provides browser-based dashboard with Chart.js visualizations.
"""

from pathlib import Path

STATIC_DIR = Path(__file__).parent / "static"


def get_dashboard_html() -> str:
    """Return the dashboard HTML content with cache-busting static URLs."""
    import json

    from cocosearch import __version__

    v = __version__
    html_path = STATIC_DIR / "index.html"
    html = html_path.read_text()

    # Cache-bust the CSS and JS entry point referenced directly in HTML.
    html = html.replace("/static/css/styles.css", f"/static/css/styles.css?v={v}")
    html = html.replace("/static/js/app.js", f"/static/js/app.js?v={v}")

    # Inject an import map so ES module sub-imports (./state.js, ./logs.js, …)
    # also get cache-busted.  Without this, browsers resolve `./logs.js` to the
    # unversioned URL and may serve a stale cached copy.
    js_dir = STATIC_DIR / "js"
    imports = {
        f"/static/js/{f.name}": f"/static/js/{f.name}?v={v}"
        for f in sorted(js_dir.glob("*.js"))
        if f.name != "app.js"  # entry point already versioned above
    }
    importmap = (
        '<script type="importmap">\n'
        f"{json.dumps({'imports': imports}, indent=2)}\n"
        "</script>"
    )
    html = html.replace("</head>", f"{importmap}\n</head>")

    return html
