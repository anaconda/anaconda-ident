from binstar_client.utils import config
from .tokens import load_baked_token


def _new_load_token(url):
    return config._old_load_token(url) or load_baked_token(url)


if not hasattr(config, "_old_load_token"):
    config._old_load_token = config.load_token
    config.load_token = _new_load_token
