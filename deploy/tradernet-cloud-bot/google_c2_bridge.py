"""Google Drive / Google Apps Script C2 Bridge for Bybit Standalone Bot.

Enables bidirectional communication, remote commands, and cloud telemetry
without Telegram polling conflicts, port forwarding, or heavy dependencies.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Callable, Dict, List, Optional
import requests

logger = logging.getLogger("GoogleDriveC2")


class GoogleDriveC2Bridge:
    """Lightweight C2 bridge talking to Google Apps Script Webhook."""

    def __init__(
        self,
        webhook_url: str = "",
        poll_interval_sec: float = 15.0,
        telemetry_interval_sec: float = 30.0,
    ) -> None:
        self.webhook_url = webhook_url.strip()
        self.poll_interval_sec = poll_interval_sec
        self.telemetry_interval_sec = telemetry_interval_sec
        self.last_poll_time = 0.0
        self.last_telemetry_time = 0.0
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "BybitBot-C2Bridge/1.0",
            "Accept": "application/json",
        })
        self.executed_commands = set()

    @property
    def is_configured(self) -> bool:
        return bool(self.webhook_url and self.webhook_url.startswith("https://script.google.com/"))

    def check_commands(self) -> List[Dict[str, Any]]:
        """Polls Google Apps Script for PENDING commands."""
        if not self.is_configured:
            return []

        now = time.time()
        if (now - self.last_poll_time) < self.poll_interval_sec:
            return []

        self.last_poll_time = now
        try:
            # Google Apps Script redirects (302) to googleusercontent.com, requests handles allow_redirects=True
            resp = self.session.get(self.webhook_url, timeout=10, allow_redirects=True)
            if resp.status_code == 200:
                data = resp.json()
                pending = data.get("pending_commands", [])
                new_cmds = [c for c in pending if c.get("command_id") not in self.executed_commands]
                return new_cmds
        except Exception as e:
            logger.debug(f"Google C2 Poll error: {e}")
        return []

    def acknowledge_command(self, command_id: str, status: str = "EXECUTED", message: str = "") -> bool:
        """Sends ACK back to Google Sheet."""
        if not self.is_configured:
            return False

        self.executed_commands.add(command_id)
        payload = {
            "type": "ACK_COMMAND",
            "command_id": command_id,
            "status": status,
            "message": message,
            "timestamp": time.time(),
        }
        try:
            resp = self.session.post(self.webhook_url, json=payload, timeout=10, allow_redirects=True)
            return resp.status_code == 200
        except Exception as e:
            logger.warning(f"Google C2 ACK error for {command_id}: {e}")
            return False

    def push_telemetry(self, telemetry_data: Dict[str, Any], force: bool = False) -> bool:
        """Sends live status update to Google Sheet."""
        if not self.is_configured:
            return False

        now = time.time()
        if not force and (now - self.last_telemetry_time) < self.telemetry_interval_sec:
            return False

        self.last_telemetry_time = now
        payload = {
            "type": "TELEMETRY",
            **telemetry_data,
        }
        try:
            resp = self.session.post(self.webhook_url, json=payload, timeout=10, allow_redirects=True)
            return resp.status_code == 200
        except Exception as e:
            logger.debug(f"Google C2 Telemetry push error: {e}")
            return False
