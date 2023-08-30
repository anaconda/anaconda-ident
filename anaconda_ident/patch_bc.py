from binstar_client.utils import config as bc

from anaconda_ident.tokens import load_baked_token


def _new_load_token(url):
    return bc._old_load_token(url) or load_baked_token(url)


if not hasattr(bc, "_old_load_token"):
    bc._old_load_token = bc.load_token
    bc.load_token = _new_load_token
