"""Web dashboard module for cocosearch.

Provides browser-based dashboard with Chart.js visualizations.
"""

from pathlib import Path

STATIC_DIR = Path(__file__).parent / "static"


def get_dashboard_html() -> str:
    """Return the dashboard HTML content."""
    html_path = STATIC_DIR / "index.html"
    return html_path.read_text()
