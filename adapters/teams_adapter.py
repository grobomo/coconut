"""Teams adapter — MS Graph API with refresh token flow.

Env vars:
  COCONUT_TEAMS_CHAT_ID       — chat thread ID
  COCONUT_TEAMS_TENANT_ID     — Azure AD tenant
  COCONUT_TEAMS_CLIENT_ID     — App registration client ID
  COCONUT_TEAMS_REFRESH_TOKEN — OAuth refresh token (or path to file)
"""
import json
import os
import re
import time
import urllib.request
import urllib.parse

from adapters.base import BaseAdapter, Message
from core.quotes import strip_html, resolve_teams_chain

SCOPES = 'Chat.Read Chat.ReadWrite User.Read offline_access'


class TeamsAdapter(BaseAdapter):
    """Teams messaging via MS Graph API."""

    name = 'teams'

    def __init__(self, config):
        super().__init__(config)
        self.chat_id = config.get('teams_chat_id', '')
        self.tenant_id = config.get('teams_tenant_id', '')
        self.client_id = config.get('teams_client_id', '')
        self._refresh_token = self._load_refresh_token(config)
        self._access_token = ''
        self._token_expires = 0
        self._last_poll_ts = '1970-01-01T00:00:00Z'
        self._seen_ids = set()

    def _load_refresh_token(self, config):
        """Load refresh token from env var or file."""
        token = config.get('teams_refresh_token', '')
        if token and os.path.isfile(token):
            with open(token) as f:
                return f.read().strip()
        return token

    def _get_access_token(self):
        """Refresh the access token if expired."""
        if self._access_token and time.time() < self._token_expires - 300:
            return self._access_token

        data = urllib.parse.urlencode({
            'grant_type': 'refresh_token',
            'client_id': self.client_id,
            'refresh_token': self._refresh_token,
            'scope': SCOPES,
        }).encode()

        url = f'https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token'
        req = urllib.request.Request(url, data=data, method='POST')
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')

        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())

        self._refresh_token = result.get('refresh_token', self._refresh_token)
        self._access_token = result['access_token']
        self._token_expires = time.time() + result.get('expires_in', 3600)
        return self._access_token

    def _graph_get(self, path):
        token = self._get_access_token()
        url = f'https://graph.microsoft.com/v1.0{path}'
        req = urllib.request.Request(url)
        req.add_header('Authorization', f'Bearer {token}')
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())

    def _graph_post(self, path, body):
        token = self._get_access_token()
        url = f'https://graph.microsoft.com/v1.0{path}'
        payload = json.dumps(body).encode()
        req = urllib.request.Request(url, data=payload, method='POST')
        req.add_header('Authorization', f'Bearer {token}')
        req.add_header('Content-Type', 'application/json')
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())

    def poll(self):
        """Fetch new messages from Teams chat with quote chain resolution."""
        try:
            path = f'/me/chats/{self.chat_id}/messages?$top=10&$orderby=createdDateTime desc'
            data = self._graph_get(path)
        except Exception:
            return []

        messages = []
        for item in reversed(data.get('value', [])):
            msg_id = item.get('id', '')
            if msg_id in self._seen_ids:
                continue
            self._seen_ids.add(msg_id)

            body = item.get('body', {}).get('content', '')
            sender_info = item.get('from', {})
            sender = ''
            if sender_info and sender_info.get('user'):
                sender = sender_info['user'].get('displayName', '')

            text = strip_html(body)
            if not text:
                continue

            # Resolve quote chain for threaded context
            quoted_context = []
            if item.get('attachments'):
                try:
                    chain = resolve_teams_chain(
                        self.chat_id, item, self._graph_get)
                    # Exclude the current message from chain (it's the last one)
                    quoted_context = chain[:-1] if len(chain) > 1 else []
                except Exception:
                    pass

            raw = dict(item)
            if quoted_context:
                raw['_quoted_context'] = quoted_context

            messages.append(Message(
                message_id=msg_id,
                sender=sender,
                text=text,
                timestamp=item.get('createdDateTime', ''),
                raw=raw,
            ))

        # Prune seen set
        if len(self._seen_ids) > 500:
            self._seen_ids = set(list(self._seen_ids)[-250:])

        return messages

    def send(self, text):
        """Send a message to the Teams chat."""
        formatted = self.format_outbound(text)
        try:
            self._graph_post(
                f'/me/chats/{self.chat_id}/messages',
                {'body': {'contentType': 'text', 'content': formatted}},
            )
        except Exception as e:
            print(f'Teams send error: {e}', flush=True)
