"""Configuration loader — all values from environment variables.

Every COCONUT_* env var maps to a config key. No hardcoded values.
Supports loading from a .env file as fallback (simple key=value parsing).
"""
import os


def _load_env_file(path):
    """Parse a simple key=value .env file into os.environ."""
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' not in line:
                continue
            key, _, value = line.partition('=')
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def load(env_file=None):
    """Load configuration from env vars. Returns a dict."""
    if env_file:
        _load_env_file(env_file)
    else:
        for candidate in ['coconut.env', 'config/coconut.env', '.env']:
            _load_env_file(candidate)

    def _get(key, default=''):
        return os.environ.get(key, default)

    def _bool(key, default=False):
        val = _get(key, str(default)).lower()
        return val in ('true', '1', 'yes')

    def _int(key, default=0):
        try:
            return int(_get(key, str(default)))
        except ValueError:
            return default

    return {
        # Identity
        'name': _get('COCONUT_NAME', 'Coconut'),
        'tagline': _get('COCONUT_TAGLINE', 'AI Technical Advisor'),
        'emoji': _get('COCONUT_EMOJI', '\U0001F334'),

        # LLM
        'model': _get('COCONUT_MODEL', 'claude-haiku-4-5-20251001'),
        'max_tokens': _int('COCONUT_MAX_TOKENS', 512),
        'api_key': _get('ANTHROPIC_API_KEY', ''),

        # Polling
        'poll_interval': _int('COCONUT_POLL_INTERVAL', 3),
        'cache_size': _int('COCONUT_CACHE_SIZE', 50),

        # Adapters
        'signal_enabled': _bool('COCONUT_ADAPTER_SIGNAL_ENABLED'),
        'signal_cli_url': _get('COCONUT_SIGNAL_CLI_URL', 'http://localhost:8080'),
        'signal_group_id': _get('COCONUT_SIGNAL_GROUP_ID', ''),
        'signal_phone': _get('COCONUT_SIGNAL_PHONE_NUMBER', ''),

        'teams_enabled': _bool('COCONUT_ADAPTER_TEAMS_ENABLED'),
        'teams_chat_id': _get('COCONUT_TEAMS_CHAT_ID', ''),
        'teams_tenant_id': _get('COCONUT_TEAMS_TENANT_ID', ''),
        'teams_client_id': _get('COCONUT_TEAMS_CLIENT_ID', ''),
        'teams_refresh_token': _get('COCONUT_TEAMS_REFRESH_TOKEN', ''),

        'cli_enabled': _bool('COCONUT_ADAPTER_CLI_ENABLED'),

        'webhook_enabled': _bool('COCONUT_ADAPTER_WEBHOOK_ENABLED'),
        'webhook_port': _int('COCONUT_WEBHOOK_PORT', 8000),
        'webhook_path': _get('COCONUT_WEBHOOK_PATH', '/webhook/inbound'),
        'webhook_secret': _get('COCONUT_WEBHOOK_SECRET', ''),
        'webhook_callback_url': _get('COCONUT_WEBHOOK_CALLBACK_URL', ''),

        # Rate limiting
        'rate_limit_enabled': _bool('COCONUT_RATE_LIMIT_ENABLED', True),
        'rate_limit_window': _int('COCONUT_RATE_LIMIT_WINDOW', 60),
        'rate_limit_max': _int('COCONUT_RATE_LIMIT_MAX', 10),

        # Persona
        'system_prompt_file': _get('COCONUT_SYSTEM_PROMPT_FILE', 'config/system-prompt.md'),

        # Relay
        'relay_enabled': _bool('COCONUT_RELAY_ENABLED'),
        'relay_url': _get('COCONUT_RELAY_URL', ''),
        'relay_token': _get('COCONUT_RELAY_TOKEN', ''),
    }
