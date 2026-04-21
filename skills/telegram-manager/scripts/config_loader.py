import json
import os


DEFAULT_CONFIG = {
    'skillHubUrl': 'http://skillhub:4080',
    'skillSlug': 'telegram-manager',
    'providerSlug': 'telegram-bot',
    'requestTimeoutSeconds': 30,
    'signingContext': 'skillhub-internal-v1',
}


def _default_config_path():
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', 'assets', 'config.json')
    )


def load_runtime_config(explicit_path=None):
    config = dict(DEFAULT_CONFIG)
    config_path = explicit_path or os.environ.get('SKILL_CONFIG_PATH') or _default_config_path()

    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as handle:
            loaded = json.load(handle)
        if isinstance(loaded, dict):
            config.update(loaded)

    if os.environ.get('SKILLHUB_URL'):
        config['skillHubUrl'] = os.environ['SKILLHUB_URL']

    if os.environ.get('TELEGRAM_MANAGER_PROVIDER_SLUG'):
        config['providerSlug'] = os.environ['TELEGRAM_MANAGER_PROVIDER_SLUG']

    return config
