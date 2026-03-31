"""Configuration loader -- all values from COCONUT_* env vars."""

import os


_DEFAULTS = {
    "COCONUT_API_KEY": "",
    "COCONUT_MODEL": "claude-haiku-4-5-20251001",
    "COCONUT_MAX_TOKENS": "1024",
    "COCONUT_ADAPTER": "cli",
    "COCONUT_POLL_INTERVAL": "3",
    "COCONUT_CACHE_SIZE": "50",
    "COCONUT_SIGNAL_CLI_URL": "http://localhost:8080",
    "COCONUT_SIGNAL_NUMBER": "",
    "COCONUT_SIGNAL_GROUP_ID": "",
    "COCONUT_TEAMS_TENANT_ID": "",
    "COCONUT_TEAMS_CLIENT_ID": "",
    "COCONUT_TEAMS_CLIENT_SECRET": "",
    "COCONUT_TEAMS_REFRESH_TOKEN": "",
    "COCONUT_TEAMS_CHAT_ID": "",
    "COCONUT_RELAY_URL": "",
    "COCONUT_SYSTEM_PROMPT_FILE": "config/system-prompt.md",
    "COCONUT_BOT_NAME": "Coconut",
}


def load():
    """Return dict of all COCONUT_* config values from env."""
    cfg = {}
    for key, default in _DEFAULTS.items():
        cfg[key] = os.environ.get(key, default)
    return cfg


def load_env_file(path):
    """Load a .env file into os.environ. Ignores comments and blank lines."""
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if value and value[0] in ('"', "'") and value[-1] == value[0]:
                value = value[1:-1]
            os.environ.setdefault(key, value)


def require(cfg, *keys):
    """Raise if any required keys are empty."""
    missing = [k for k in keys if not cfg.get(k)]
    if missing:
        raise SystemExit("Missing required config: " + ", ".join(missing))
