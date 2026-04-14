"""Tests for the dashboard URL module-level state helpers."""

from cocosearch.dashboard.server import (
    get_dashboard_url,
    set_dashboard_url,
    stop_dashboard_server,
)


def test_get_returns_none_when_unset():
    set_dashboard_url(None)
    assert get_dashboard_url() is None


def test_set_and_get_round_trip():
    set_dashboard_url("http://127.0.0.1:9999/dashboard")
    try:
        assert get_dashboard_url() == "http://127.0.0.1:9999/dashboard"
    finally:
        set_dashboard_url(None)


def test_stop_clears_url():
    set_dashboard_url("http://127.0.0.1:9999/dashboard")
    stop_dashboard_server()
    assert get_dashboard_url() is None
