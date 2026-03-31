"""Signal adapter using signal-cli REST API.

Endpoints:
- GET  /v1/receive/{number}     -- poll for new messages
- POST /v2/send                 -- send a message
"""

import json
import time
import urllib.request
import urllib.error

from adapters.base import BaseAdapter, Message


class SignalAdapter(BaseAdapter):
    """Adapter for Signal via signal-cli REST API."""

    def __init__(self, cfg):
        self._base_url = cfg["COCONUT_SIGNAL_CLI_URL"].rstrip("/")
        self._number = cfg["COCONUT_SIGNAL_NUMBER"]
        self._group_id = cfg.get("COCONUT_SIGNAL_GROUP_ID", "")
        self._bot_name = cfg.get("COCONUT_BOT_NAME", "Coconut")

    def poll(self):
        """GET /v1/receive/{number} and return normalized messages."""
        url = f"{self._base_url}/v1/receive/{self._number}"
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
        except (urllib.error.URLError, json.JSONDecodeError):
            return []

        messages = []
        for envelope in data:
            msg = self._parse_envelope(envelope)
            if msg:
                messages.append(msg)
        return messages

    def send(self, text):
        """POST /v2/send to the configured group or number."""
        url = f"{self._base_url}/v2/send"
        body = {
            "message": text,
            "number": self._number,
            "text_mode": "normal",
        }
        if self._group_id:
            body["recipients"] = [self._group_id]
        else:
            body["recipients"] = []

        data = json.dumps(body).encode()
        req = urllib.request.Request(
            url, data=data,
            headers={"content-type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=10):
                pass
        except urllib.error.URLError:
            pass

    def _parse_envelope(self, envelope):
        """Extract a Message from a signal-cli envelope."""
        data_msg = envelope.get("envelope", {}).get("dataMessage")
        if not data_msg:
            return None

        text = data_msg.get("message", "")
        if not text:
            return None

        # Filter to group messages if group_id is set
        group_info = data_msg.get("groupInfo", {})
        if self._group_id and group_info.get("groupId") != self._group_id:
            return None

        sender = envelope.get("envelope", {}).get("sourceName", "")
        timestamp = data_msg.get("timestamp", 0)
        ts_str = time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime(timestamp / 1000)
        ) if timestamp else time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        return Message(
            id=f"signal-{timestamp}",
            sender=sender,
            text=text,
            timestamp=ts_str,
            raw=envelope,
        )
