#!/usr/bin/env python3
"""Coconut — reusable AI chat assistant.

Main entry point. Polls configured adapters, classifies messages,
responds to REPLY messages, routes RELAY messages to external CCC.
Graceful shutdown on SIGTERM/SIGINT.
"""
import json
import os
import signal
import sys
import time
import urllib.request
import urllib.error

from core import config, cache, classifier, llm
from core.health import HealthWriter
from core.logrotate import RotatingLog
from core.ratelimit import RateLimiter
from adapters.base import Message

_shutdown = False
_log_file = None


def _handle_signal(signum, frame):
    global _shutdown
    _log('info', f'Received signal {signum}, shutting down...')
    _shutdown = True


def _log(level, msg, **fields):
    entry = {
        'ts': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'level': level,
        'msg': msg,
        'component': 'coconut',
    }
    entry.update(fields)
    line = json.dumps(entry, separators=(',', ':'))
    print(line, flush=True)
    if _log_file:
        try:
            _log_file.write(line + '\n')
            _log_file.flush()
        except OSError:
            pass


def _init_log_file(data_dir):
    global _log_file
    log_path = os.environ.get('COCONUT_LOG_FILE', '')
    if not log_path:
        log_path = os.path.join(data_dir, 'coconut.log')
    max_bytes = int(os.environ.get('COCONUT_LOG_MAX_BYTES', 5 * 1024 * 1024))
    backups = int(os.environ.get('COCONUT_LOG_BACKUPS', 3))
    _log_file = RotatingLog(log_path, max_bytes=max_bytes, backups=backups)


def _load_adapters(cfg):
    """Load enabled adapters based on config."""
    adapters = []
    if cfg.get('signal_enabled'):
        from adapters.signal_adapter import SignalAdapter
        adapters.append(SignalAdapter(cfg))
        _log('info', 'Signal adapter enabled')
    if cfg.get('teams_enabled'):
        from adapters.teams_adapter import TeamsAdapter
        adapters.append(TeamsAdapter(cfg))
        _log('info', 'Teams adapter enabled')
    if cfg.get('cli_enabled'):
        from adapters.cli_adapter import CLIAdapter
        adapters.append(CLIAdapter(cfg))
        _log('info', 'CLI adapter enabled')
    if cfg.get('slack_enabled'):
        from adapters.slack_adapter import SlackAdapter
        adapters.append(SlackAdapter(cfg))
        _log('info', 'Slack adapter enabled',
             channel=cfg.get('slack_channel_id', ''))
    if cfg.get('webhook_enabled'):
        from adapters.webhook_adapter import WebhookAdapter
        adapters.append(WebhookAdapter(cfg))
        _log('info', 'Webhook adapter enabled',
             port=cfg.get('webhook_port', 8000))
    return adapters


def _relay_message(cfg, message, classification):
    """Route a RELAY message to external CCC."""
    url = cfg.get('relay_url', '')
    if not url:
        _log('warn', 'RELAY message but no relay_url configured', text=message.text[:80])
        return

    payload = json.dumps({
        'text': message.text,
        'sender': message.sender,
        'classification': 'RELAY',
        'reason': classification.get('reason', ''),
        'timestamp': message.timestamp,
    }).encode()

    req = urllib.request.Request(url, data=payload, method='POST')
    req.add_header('Content-Type', 'application/json')
    relay_token = cfg.get('relay_token', '')
    if relay_token:
        req.add_header('Authorization', f'Bearer {relay_token}')
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp.read()
        _log('info', 'Relayed message', sender=message.sender)
    except (urllib.error.URLError, OSError) as e:
        _log('error', 'Relay failed', error=str(e))


def main():
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    cfg = config.load()
    data_dir = os.environ.get('COCONUT_DATA_DIR', 'data')
    _init_log_file(data_dir)

    adapters = _load_adapters(cfg)
    if not adapters:
        _log('error', 'No adapters enabled. Set COCONUT_ADAPTER_*_ENABLED=true')
        sys.exit(1)

    api_key = cfg.get('api_key', '')
    if not api_key:
        _log('error', 'No ANTHROPIC_API_KEY set')
        sys.exit(1)

    msg_cache = cache.MessageCache(
        data_dir=data_dir,
        cache_size=cfg.get('cache_size', 50),
    )

    health = HealthWriter(data_dir=data_dir)
    rate_limiter = RateLimiter(
        window_seconds=cfg.get('rate_limit_window', 60),
        max_per_window=cfg.get('rate_limit_max', 10),
        enabled=cfg.get('rate_limit_enabled', True),
    )
    poll_interval = cfg.get('poll_interval', 3)
    model = cfg.get('model', 'claude-haiku-4-5-20251001')

    _log('info', 'Coconut starting',
         adapters=[a.name for a in adapters],
         poll_interval=poll_interval,
         model=model)

    while not _shutdown:
        new_messages = []
        # Track which adapter produced which messages
        msg_source = {}

        for adapter in adapters:
            try:
                msgs = adapter.poll()
                for m in msgs:
                    msg_source[m.message_id] = adapter
                new_messages.extend(msgs)
                health.record_poll(adapter.name, len(msgs))
            except Exception as e:
                _log('error', f'Poll error ({adapter.name})', error=str(e))
                health.record_adapter_error(adapter.name)

        health.update(extra={
            'usage': llm.get_usage(),
            'rate_limits': rate_limiter.stats(),
        })

        if not new_messages:
            if not _shutdown:
                time.sleep(poll_interval)
            continue

        # Update cache
        cache_msgs = [m.to_dict() for m in new_messages]
        for m in cache_msgs:
            m['classify'] = True
        cached, archived = msg_cache.add(cache_msgs)

        _log('info', 'New messages',
             count=len(new_messages),
             cache_size=len(cached),
             archived=archived)

        # Classify using full cache as context
        context = msg_cache.load()
        try:
            classifications = classifier.classify(context, api_key, model)
        except Exception as e:
            _log('error', 'Classification failed', error=str(e))
            health.errors += 1
            classifications = []

        class_map = {c.get('message_id'): c for c in classifications}

        for msg in new_messages:
            cl = class_map.get(msg.message_id, {})
            action = cl.get('classification', 'IGNORE')
            source_adapter = msg_source.get(msg.message_id)

            _log('info', 'Classified',
                 message_id=msg.message_id,
                 sender=msg.sender,
                 action=action,
                 reason=cl.get('reason', ''))

            if action == 'REPLY' and source_adapter:
                if not rate_limiter.allow(source_adapter.name):
                    _log('warn', 'Rate limited',
                         adapter=source_adapter.name,
                         remaining=rate_limiter.remaining(source_adapter.name))
                    continue
                recent = context[:10]
                ctx_text = '\n'.join(
                    f"  {m.get('sender', '?')}: {m.get('text', '')}"
                    for m in reversed(recent)
                )
                prompt = (
                    f'Recent conversation:\n{ctx_text}\n\n'
                    f'Message from {msg.sender}: {msg.text}\n\n'
                    f'Respond helpfully and concisely.'
                )

                try:
                    system_prompt = llm.build_system_prompt(cfg)
                    response = llm.chat(api_key, system_prompt, prompt,
                                        model=model,
                                        max_tokens=cfg.get('max_tokens', 512))
                    # Reply only through the adapter that received the message
                    source_adapter.send(response)
                    health.processed += 1
                    _log('info', 'Replied', sender=msg.sender,
                         adapter=source_adapter.name,
                         usage=llm.get_usage())
                except Exception as e:
                    _log('error', 'Reply failed', error=str(e))
                    health.errors += 1

            elif action == 'RELAY' and cfg.get('relay_enabled'):
                _relay_message(cfg, msg, cl)
                health.processed += 1

        if not _shutdown:
            time.sleep(poll_interval)

    # Graceful adapter shutdown (webhook HTTP server, etc.)
    for adapter in adapters:
        if hasattr(adapter, 'shutdown'):
            try:
                adapter.shutdown()
            except Exception:
                pass

    health.update(extra={'status': 'stopped', 'usage': llm.get_usage()})
    _log('info', 'Coconut stopped', usage=llm.get_usage())
    if _log_file:
        _log_file.close()


def health_check():
    """Check health status for K8s liveness probes. Exit 0=healthy, 1=stale."""
    data_dir = os.environ.get('COCONUT_DATA_DIR', 'data')
    from core.health import HealthWriter
    hw = HealthWriter(data_dir=data_dir)
    status = hw.check()
    if status == 0:
        health_file = os.path.join(data_dir, 'health.json')
        try:
            with open(health_file) as f:
                health = json.load(f)
            print(json.dumps(health, indent=2))
        except (FileNotFoundError, json.JSONDecodeError):
            print('{"status": "healthy"}')
    else:
        print('{"status": "stale"}')
    sys.exit(status)


if __name__ == '__main__':
    if '--health' in sys.argv:
        health_check()
    else:
        main()
