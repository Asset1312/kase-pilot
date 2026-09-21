import io
import json
import os
import sys
from unittest.mock import MagicMock, patch
import pytest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from bybit_standalone_bot import (
    StandaloneBybitBot,
    SimpleDashboardHandler,
    send_telegram,
    read_cluster_state,
    write_cluster_state,
    init_cluster_role,
    is_desktop_schedule_window,
)
import bybit_standalone_bot


def test_no_telegram_flag_disables_telegram_on_bot(monkeypatch):
    bot = StandaloneBybitBot(mode="desktop", enable_telegram=False)
    assert bot.enable_telegram is False

    monkeypatch.setattr(bybit_standalone_bot, "ENABLE_TELEGRAM", False)
    bot2 = StandaloneBybitBot(mode="desktop", enable_telegram=True)
    assert bot2.enable_telegram is False


def test_send_telegram_makes_no_http_calls_when_disabled(monkeypatch):
    with patch("urllib.request.urlopen") as mock_urlopen:
        monkeypatch.setattr(bybit_standalone_bot, "ENABLE_TELEGRAM", False)
        send_telegram("Test message that should not be sent")
        mock_urlopen.assert_not_called()


def test_cluster_state_uses_clock_schedule_when_telegram_disabled(monkeypatch):
    with patch("urllib.request.urlopen") as mock_urlopen:
        monkeypatch.setattr(bybit_standalone_bot, "ENABLE_TELEGRAM", False)
        res = write_cluster_state("desktop", "test note")
        assert res is None
        mock_urlopen.assert_not_called()

        state = read_cluster_state()
        assert state["note"] == "Clock Schedule"
        assert state["active_host"] in ("desktop", "mobile")
        mock_urlopen.assert_not_called()


def test_init_cluster_role_standalone_schedule():
    bot_desktop = StandaloneBybitBot(mode="desktop", enable_telegram=False)
    with patch("bybit_standalone_bot.is_desktop_schedule_window", return_value=True):
        init_cluster_role(bot_desktop)
        assert bot_desktop.is_active_controller is True
        assert bot_desktop.role == "ACTIVE_CONTROLLER"

    with patch("bybit_standalone_bot.is_desktop_schedule_window", return_value=False):
        init_cluster_role(bot_desktop)
        assert bot_desktop.is_active_controller is False
        assert bot_desktop.role == "PASSIVE_OBSERVER"

    bot_mobile = StandaloneBybitBot(mode="mobile", enable_telegram=False)
    with patch("bybit_standalone_bot.is_desktop_schedule_window", return_value=True):
        init_cluster_role(bot_mobile)
        assert bot_mobile.is_active_controller is False
        assert bot_mobile.role == "PASSIVE_OBSERVER"

    with patch("bybit_standalone_bot.is_desktop_schedule_window", return_value=False):
        init_cluster_role(bot_mobile)
        assert bot_mobile.is_active_controller is True
        assert bot_mobile.role == "ACTIVE_CONTROLLER"


class MockServer:
    def __init__(self, bot):
        self.bot = bot


def _create_handler(bot, path, method="GET"):
    request_text = f"{method} {path} HTTP/1.1\r\nHost: localhost\r\n\r\n"
    rfile = io.BytesIO(request_text.encode("utf-8"))
    wfile = io.BytesIO()

    SimpleDashboardHandler.bot_instance = bot
    handler = SimpleDashboardHandler.__new__(SimpleDashboardHandler)
    handler.rfile = rfile
    handler.wfile = wfile
    handler.server = MockServer(bot)
    handler.path = path
    handler.command = method
    handler.requestline = f"{method} {path} HTTP/1.1"
    handler.request_version = "HTTP/1.1"
    handler.close_connection = True
    handler.headers = {}
    handler.log_message = MagicMock()
    return handler, wfile


def test_web_dashboard_get_contains_controls():
    bot = StandaloneBybitBot(mode="desktop", enable_telegram=False)
    handler, wfile = _create_handler(bot, "/")
    handler.do_GET()

    output = wfile.getvalue().decode("utf-8")
    assert "/api/pause" in output
    assert "/api/resume" in output
    assert "/api/panic" in output
    assert "botAction" in output
    assert "location.reload()" in output


def test_web_dashboard_post_pause():
    bot = StandaloneBybitBot(mode="desktop", enable_telegram=False)
    bot.cancel_all_portfolio_buys = MagicMock()

    handler, wfile = _create_handler(bot, "/api/pause", method="POST")
    handler.do_POST()

    assert bot.is_paused is True
    bot.cancel_all_portfolio_buys.assert_called_once()
    output = wfile.getvalue().decode("utf-8")
    assert '"status": "PAUSED"' in output


def test_web_dashboard_post_resume():
    bot = StandaloneBybitBot(mode="desktop", enable_telegram=False)
    bot.is_paused = True
    bot.circuit_breaker_active = True

    handler, wfile = _create_handler(bot, "/api/resume", method="POST")
    handler.do_POST()

    assert bot.is_paused is False
    assert bot.circuit_breaker_active is False
    output = wfile.getvalue().decode("utf-8")
    assert '"status": "ACTIVE"' in output


def test_web_dashboard_post_panic():
    bot = StandaloneBybitBot(mode="desktop", enable_telegram=False)
    bot.cancel_all_portfolio_buys = MagicMock()

    handler, wfile = _create_handler(bot, "/api/panic", method="POST")
    handler.do_POST()

    assert bot.is_paused is True
    bot.cancel_all_portfolio_buys.assert_called_once()
    output = wfile.getvalue().decode("utf-8")
    assert '"status": "PANIC_STOPPED"' in output
