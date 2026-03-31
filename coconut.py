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
from adapters.base import Message

_shutdown = False


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
    print(json.dumps(entry, separators=(',', ':')), flush=True)


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
    return adapters


def _relay_message(cfg, message, classification):
    """Route a RELAY message to external CCC."""
    url = cfg.get('relay_url', '')
    token = cfg.get('relay_token', '')
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
    if token:
        req.add_header('Authorization', f'Bearer {token}')
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
    adapters = _load_adapters(cfg)

    if not adapters:
        _log('error', 'No adapters enabled. Set COCONUT_ADAPTER_*_ENABLED=true')
        sys.exit(1)

    api_key = cfg.get('api_key', '')
    if not api_key:
        _log('error', 'No ANTHROPIC_API_KEY set')
        sys.exit(1)

    msg_cache = cache.MessageCache(
        data_dir=os.environ.get('COCONUT_DATA_DIR', 'data'),
        cache_size=cfg.get('cache_size', 50),
    )

    poll_interval = cfg.get('poll_interval', 3)
    model = cfg.get('model', 'claude-haiku-4-5-20251001')
    system_prompt = llm.build_system_prompt(cfg)

    _log('info', 'Coconut starting',
         adapters=[a.name for a in adapters],
         poll_interval=poll_interval,
         model=model)

    cycle = 0
    while not _shutdown:
        cycle += 1
        new_messages = []

        # Poll all adapters
        for adapter in adapters:
            try:
                msgs = adapter.poll()
                new_messages.extend(msgs)
            except Exception as e:
                _log('error', f'Poll error ({adapter.name})', error=str(e))

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
            classifications = []

        # Build lookup
        class_map = {c.get('message_id'): c for c in classifications}

        # Process each new message
        for msg in new_messages:
            cl = class_map.get(msg.message_id, {})
            action = cl.get('classification', 'IGNORE')

            _log('info', 'Classified',
                 message_id=msg.message_id,
                 sender=msg.sender,
                 action=action,
                 reason=cl.get('reason', ''))

            if action == 'REPLY':
                # Build prompt with conversation context
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
                    # Refresh system prompt with current time
                    system_prompt = llm.build_system_prompt(cfg)
                    response = llm.chat(api_key, system_prompt, prompt,
                                        model=model,
                                        max_tokens=cfg.get('max_tokens', 512))
                    # Send reply through the adapter that received it
                    for adapter in adapters:
                        adapter.send(response)
                    _log('info', 'Replied', sender=msg.sender,
                         usage=llm.get_usage())
                except Exception as e:
                    _log('error', 'Reply failed', error=str(e))

            elif action == 'RELAY' and cfg.get('relay_enabled'):
                _relay_message(cfg, msg, cl)

        if not _shutdown:
            time.sleep(poll_interval)

    _log('info', 'Coconut stopped', usage=llm.get_usage())


if __name__ == '__main__':
    main()
