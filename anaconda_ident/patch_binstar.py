from binstar_client.utils import config

import sys
from os import environ
from os.path import isdir, isfile, join, dirname


_baked_tokens = None


def get_baked_tokens():
    global _baked_tokens
    if _baked_tokens is not None:
        return _baked_tokens
    _baked_tokens = {}
    paths = set(
        (
            dirname(dirname(environ.get("CONDA_EXE", ""))),
            dirname(dirname(environ.get("CONDA_PYTHON_EXE", ""))),
            sys.prefix,
        )
    )
    for prefix in paths:
        if not prefix or not isdir(prefix):
            continue
        fname = join(prefix, "etc", "anaconda_ident.yml")
        if not isfile(fname):
            continue
        try:
            import yaml

            with open(fname, "r") as fp:
                data = yaml.safe_load(fp)
            _baked_tokens = data.get("repo_tokens") or {}
            break
        except Exception:
            pass
    return _baked_tokens


def _new_load_token(url):
    token = config._old_load_token(url)
    if token:
        return token
    baked = get_baked_tokens()
    if baked:
        url = url.rstrip("/") + "/"
        for k, v in baked.items():
            if url.startswith(k):
                return v


if not hasattr(config, "_old_load_token"):
    config._old_load_token = config.load_token
    config.load_token = _new_load_token
