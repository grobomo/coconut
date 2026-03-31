#!/usr/bin/env python3
"""Coconut -- reusable AI chat assistant.

Main polling loop: poll adapter -> update cache -> classify -> respond/relay.
"""

import json
import os
import signal
import sys
import time
import urllib.request
import urllib.error

from core import config, llm, classifier, cache
from adapters.base import Message


_RUNNING = True


def _shutdown(signum, frame):
    global _RUNNING
    _RUNNING = False
    sys.stderr.write("\n[coconut] Shutting down...\n")


def _load_system_prompt(cfg):
    """Load system prompt from file or return default."""
    path = cfg.get("COCONUT_SYSTEM_PROMPT_FILE", "config/system-prompt.md")
    if os.path.exists(path):
        with open(path) as f:
            return f.read().strip()
    return f"You are {cfg['COCONUT_BOT_NAME']}, a helpful AI assistant."


def _get_adapter(cfg):
    """Instantiate the configured adapter."""
    adapter_name = cfg["COCONUT_ADAPTER"].lower()
    if adapter_name == "signal":
        from adapters.signal_adapter import SignalAdapter
        return SignalAdapter(cfg)
    elif adapter_name == "teams":
        from adapters.teams_adapter import TeamsAdapter
        return TeamsAdapter(cfg)
    elif adapter_name == "cli":
        from adapters.cli_adapter import CLIAdapter
        return CLIAdapter(cfg)
    else:
        raise SystemExit(f"Unknown adapter: {adapter_name}")


def _respond(cfg, system_prompt, msg_cache, message):
    """Generate an LLM response for a REPLY-classified message."""
    # Build conversation for LLM from recent cache
    recent = msg_cache.recent(20)
    bot_name = cfg["COCONUT_BOT_NAME"]
    llm_messages = []
    for m in recent:
        if isinstance(m, dict):
            sender = m.get("sender", "")
            text = m.get("text", "")
        else:
            sender = m.sender
            text = m.text
        role = "assistant" if sender.lower() == bot_name.lower() else "user"
        content = f"{sender}: {text}" if role == "user" else text
        llm_messages.append({"role": role, "content": content})

    # Ensure last message is user role (API requirement)
    if llm_messages and llm_messages[-1]["role"] != "user":
        llm_messages.append({"role": "user", "content": "(continue)"})

    try:
        return llm.chat(
            api_key=cfg["COCONUT_API_KEY"],
            model=cfg["COCONUT_MODEL"],
            messages=llm_messages,
            system=system_prompt,
            max_tokens=int(cfg["COCONUT_MAX_TOKENS"]),
        )
    except llm.LLMError as e:
        sys.stderr.write(f"[coconut] LLM error: {e}\n")
        return None


def _relay(cfg, message):
    """Forward a RELAY-classified message to the relay URL."""
    relay_url = cfg.get("COCONUT_RELAY_URL")
    if not relay_url:
        sys.stderr.write("[coconut] RELAY message but no COCONUT_RELAY_URL set\n")
        return
    body = json.dumps({
        "sender": message.get("sender", "") if isinstance(message, dict) else message.sender,
        "text": message.get("text", "") if isinstance(message, dict) else message.text,
        "timestamp": message.get("timestamp", "") if isinstance(message, dict) else message.timestamp,
    }).encode()
    req = urllib.request.Request(
        relay_url, data=body,
        headers={"content-type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10):
            pass
    except urllib.error.URLError as e:
        sys.stderr.write(f"[coconut] Relay failed: {e}\n")


def main():
    global _RUNNING

    # Load env file if present
    config.load_env_file("coconut.env")
    config.load_env_file(os.path.expanduser("~/.coconut.env"))

    cfg = config.load()
    config.require(cfg, "COCONUT_API_KEY")

    adapter = _get_adapter(cfg)
    adapter.setup(cfg)

    system_prompt = _load_system_prompt(cfg)
    poll_interval = int(cfg["COCONUT_POLL_INTERVAL"])
    cache_size = int(cfg["COCONUT_CACHE_SIZE"])

    msg_cache = cache.MessageCache(
        max_size=cache_size,
        archive_path="data/archive.jsonl",
    )

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    sys.stderr.write(
        f"[coconut] Started -- adapter={cfg['COCONUT_ADAPTER']}, "
        f"model={cfg['COCONUT_MODEL']}, poll={poll_interval}s\n"
    )

    while _RUNNING:
        try:
            new_messages = adapter.poll()
        except Exception as e:
            sys.stderr.write(f"[coconut] Poll error: {e}\n")
            new_messages = []

        for msg in new_messages:
            msg_dict = msg.to_dict() if isinstance(msg, Message) else msg
            is_new = msg_cache.add(msg_dict)
            if not is_new:
                continue

            # Classify
            classification, reason = classifier.classify(
                api_key=cfg["COCONUT_API_KEY"],
                model=cfg["COCONUT_MODEL"],
                messages=msg_cache.recent(15),
                bot_name=cfg["COCONUT_BOT_NAME"],
            )

            sender = msg_dict.get("sender", "?")
            text_preview = msg_dict.get("text", "")[:60]
            sys.stderr.write(
                f"[coconut] [{classification}] {sender}: {text_preview} "
                f"({reason})\n"
            )

            if classification == "REPLY":
                response = _respond(cfg, system_prompt, msg_cache, msg_dict)
                if response:
                    adapter.send(response)
                    # Add bot response to cache
                    msg_cache.add({
                        "sender": cfg["COCONUT_BOT_NAME"],
                        "text": response,
                        "timestamp": time.strftime(
                            "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
                        ),
                    })
            elif classification == "RELAY":
                _relay(cfg, msg_dict)

        time.sleep(poll_interval)

    adapter.teardown()
    sys.stderr.write("[coconut] Stopped.\n")


if __name__ == "__main__":
    main()
