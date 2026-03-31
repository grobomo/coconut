"""Webhook adapter — HTTP server for generic platform integration.

Runs a lightweight HTTP server that:
- Receives inbound messages via POST /webhook/inbound
- Sends replies via POST to a configurable callback URL
- Exposes GET /webhook/health for liveness checks

Inbound JSON format:
  {"text": "...", "sender": "...", "message_id": "...", "callback_url": "..."}

Outbound (to callback_url):
  {"text": "...", "message_id": "...", "sender": "coconut"}

Env vars:
  COCONUT_WEBHOOK_PORT          — listen port (default 8000)
  COCONUT_WEBHOOK_PATH          — inbound path (default /webhook/inbound)
  COCONUT_WEBHOOK_SECRET        — shared secret for auth (optional)
  COCONUT_WEBHOOK_CALLBACK_URL  — default callback URL (override per-message)
"""
import hashlib
import hmac
import json
import threading
import time
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler

from adapters.base import BaseAdapter, Message

MAX_BODY_SIZE = 1024 * 64  # 64KB max inbound payload


class WebhookAdapter(BaseAdapter):
    """HTTP webhook adapter for generic integrations."""

    name = 'webhook'

    def __init__(self, config):
        super().__init__(config)
        self.port = config.get('webhook_port', 8000)
        self.inbound_path = config.get('webhook_path', '/webhook/inbound')
        self.secret = config.get('webhook_secret', '')
        self.callback_url = config.get('webhook_callback_url', '')
        self._queue = []
        self._lock = threading.Lock()
        self._last_callback = ''  # Track last inbound callback for send()
        self._server = None
        self._thread = None
        self._start_server()

    def _start_server(self):
        """Start HTTP server in a background thread."""
        adapter = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                if self.path.rstrip('/') != adapter.inbound_path.rstrip('/'):
                    self.send_error(404)
                    return

                length = int(self.headers.get('Content-Length', 0))
                if length == 0:
                    self.send_error(400, 'Empty body')
                    return
                if length > MAX_BODY_SIZE:
                    self.send_error(413, 'Payload too large')
                    return

                body = self.rfile.read(length)

                # Verify HMAC signature if secret is configured
                if adapter.secret:
                    sig = self.headers.get('X-Webhook-Signature', '')
                    expected = hmac.new(
                        adapter.secret.encode(), body, hashlib.sha256
                    ).hexdigest()
                    if not hmac.compare_digest(sig, expected):
                        self.send_error(403, 'Invalid signature')
                        return

                try:
                    data = json.loads(body)
                except json.JSONDecodeError:
                    self.send_error(400, 'Invalid JSON')
                    return

                text = data.get('text', '').strip()
                if not text:
                    self.send_error(400, 'Missing text field')
                    return

                sender = data.get('sender', 'webhook-user')
                message_id = data.get('message_id', Message.make_id(text, sender))
                callback = data.get('callback_url', adapter.callback_url)

                msg = Message(
                    message_id=message_id,
                    sender=sender,
                    text=text,
                    timestamp=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                    raw={'callback_url': callback},
                )

                with adapter._lock:
                    adapter._queue.append(msg)
                    if callback:
                        adapter._last_callback = callback

                self.send_response(202)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'status': 'accepted',
                    'message_id': message_id,
                }).encode())

            def do_GET(self):
                if self.path.rstrip('/') == '/webhook/health':
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    with adapter._lock:
                        queue_size = len(adapter._queue)
                    self.wfile.write(json.dumps({
                        'status': 'ok',
                        'adapter': 'webhook',
                        'queue_size': queue_size,
                    }).encode())
                else:
                    self.send_error(404)

            def log_message(self, fmt, *args):
                # Suppress default stderr logging
                pass

        self._server = HTTPServer(('0.0.0.0', self.port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def poll(self):
        """Drain the message queue (filled by HTTP handler)."""
        with self._lock:
            msgs = list(self._queue)
            self._queue.clear()
        return msgs

    def send(self, text):
        """Send reply to the callback URL (last inbound or default)."""
        formatted = self.format_outbound(text)
        callback = self._last_callback or self.callback_url

        if not callback:
            return

        payload = json.dumps({
            'text': formatted,
            'sender': self.config.get('name', 'Coconut'),
        }).encode()

        req = urllib.request.Request(callback, data=payload, method='POST')
        req.add_header('Content-Type', 'application/json')
        if self.secret:
            sig = hmac.new(
                self.secret.encode(), payload, hashlib.sha256
            ).hexdigest()
            req.add_header('X-Webhook-Signature', sig)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp.read()
        except (urllib.error.URLError, OSError) as e:
            print(f'Webhook send error: {e}', flush=True)

    def shutdown(self):
        """Stop the HTTP server."""
        if self._server:
            self._server.shutdown()
