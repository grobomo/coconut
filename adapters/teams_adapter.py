"""Teams adapter using MS Graph API with refresh token flow.

Uses OAuth2 refresh token to get access tokens, then polls chat messages.
"""

import json
import time
import urllib.request
import urllib.error
import urllib.parse

from adapters.base import BaseAdapter, Message

GRAPH_URL = "https://graph.microsoft.com/v1.0"
TOKEN_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"


class TeamsAdapter(BaseAdapter):
    """Adapter for Microsoft Teams via Graph API."""

    def __init__(self, cfg):
        self._tenant_id = cfg["COCONUT_TEAMS_TENANT_ID"]
        self._client_id = cfg["COCONUT_TEAMS_CLIENT_ID"]
        self._client_secret = cfg["COCONUT_TEAMS_CLIENT_SECRET"]
        self._refresh_token = cfg["COCONUT_TEAMS_REFRESH_TOKEN"]
        self._chat_id = cfg["COCONUT_TEAMS_CHAT_ID"]
        self._bot_name = cfg.get("COCONUT_BOT_NAME", "Coconut")
        self._access_token = ""
        self._token_expires = 0
        self._last_msg_id = ""

    def poll(self):
        """Poll Graph API for new chat messages."""
        self._ensure_token()
        url = f"{GRAPH_URL}/chats/{self._chat_id}/messages?$top=10&$orderby=createdDateTime desc"
        headers = {
            "authorization": f"Bearer {self._access_token}",
            "content-type": "application/json",
        }
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
        except (urllib.error.URLError, json.JSONDecodeError):
            return []

        messages = []
        for item in reversed(data.get("value", [])):
            msg = self._parse_message(item)
            if msg and msg.id != self._last_msg_id:
                messages.append(msg)

        if messages:
            self._last_msg_id = messages[-1].id
        return messages

    def send(self, text):
        """Send a message to the Teams chat."""
        self._ensure_token()
        url = f"{GRAPH_URL}/chats/{self._chat_id}/messages"
        body = json.dumps({
            "body": {"contentType": "text", "content": text}
        }).encode()
        headers = {
            "authorization": f"Bearer {self._access_token}",
            "content-type": "application/json",
        }
        req = urllib.request.Request(url, data=body, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15):
                pass
        except urllib.error.URLError:
            pass

    def _ensure_token(self):
        """Refresh access token if expired or missing."""
        if self._access_token and time.time() < self._token_expires - 60:
            return
        url = TOKEN_URL.format(tenant=self._tenant_id)
        params = urllib.parse.urlencode({
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "refresh_token": self._refresh_token,
            "grant_type": "refresh_token",
            "scope": "https://graph.microsoft.com/.default",
        }).encode()
        req = urllib.request.Request(url, data=params)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
            self._access_token = data["access_token"]
            self._token_expires = time.time() + data.get("expires_in", 3600)
            if "refresh_token" in data:
                self._refresh_token = data["refresh_token"]
        except (urllib.error.URLError, json.JSONDecodeError, KeyError):
            pass

    def _parse_message(self, item):
        """Parse a Graph API message into a normalized Message."""
        body = item.get("body", {})
        text = body.get("content", "").strip()
        if not text:
            return None
        sender_info = item.get("from", {}).get("user", {})
        sender = sender_info.get("displayName", "unknown")
        msg_id = item.get("id", "")
        created = item.get("createdDateTime", "")
        return Message(
            id=msg_id,
            sender=sender,
            text=text,
            timestamp=created,
            raw=item,
        )
