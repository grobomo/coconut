"""Anthropic API client — stdlib only (urllib).

Supports both sk-ant API keys and OAuth JWT tokens.
"""
import json
import time
import urllib.request
import urllib.error

API_URL = 'https://api.anthropic.com/v1/messages'

# Token tracking (cumulative)
_usage = {'input_tokens': 0, 'output_tokens': 0, 'calls': 0}


def get_usage():
    """Return cumulative token usage stats."""
    return dict(_usage)


def _add_auth(req, api_key):
    """Add auth headers — Bearer for OAuth JWTs, x-api-key for sk-ant keys."""
    if api_key.startswith('eyJ'):
        req.add_header('Authorization', f'Bearer {api_key}')
    else:
        req.add_header('x-api-key', api_key)
    req.add_header('anthropic-version', '2023-06-01')
    req.add_header('Content-Type', 'application/json')


_RETRYABLE_CODES = (429, 500, 502, 503, 529)


def chat(api_key, system_prompt, user_message, model='claude-haiku-4-5-20251001',
         max_tokens=512, retries=3):
    """Send a message to the Anthropic API. Returns response text.

    Retries on transient errors (429, 500, 502, 503, 529) with exponential backoff.
    """
    body = json.dumps({
        'model': model,
        'max_tokens': max_tokens,
        'system': system_prompt,
        'messages': [{'role': 'user', 'content': user_message}],
    }).encode()

    last_err = None
    for attempt in range(retries):
        req = urllib.request.Request(API_URL, data=body, method='POST')
        _add_auth(req, api_key)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read())
            usage = result.get('usage', {})
            _usage['input_tokens'] += usage.get('input_tokens', 0)
            _usage['output_tokens'] += usage.get('output_tokens', 0)
            _usage['calls'] += 1
            return result['content'][0]['text'].strip()
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in _RETRYABLE_CODES and attempt < retries - 1:
                time.sleep(2 ** attempt + 1)
                continue
            raise
        except (urllib.error.URLError, OSError) as e:
            last_err = e
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise
    raise last_err


def build_system_prompt(config):
    """Load system prompt from file and fill in identity placeholders."""
    prompt_file = config.get('system_prompt_file', 'config/system-prompt.md')
    try:
        with open(prompt_file) as f:
            template = f.read()
    except FileNotFoundError:
        template = 'You are {name}, {tagline}. Current time: {current_datetime} UTC.'

    return template.format(
        name=config.get('name', 'Coconut'),
        tagline=config.get('tagline', 'AI Technical Advisor'),
        current_datetime=time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime()),
    )
