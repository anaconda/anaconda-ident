import sys
from os import environ, stat
from os.path import isdir, isfile, join, dirname


_baked_tokens = None
_baked_token_path = None
_baked_token_mtime = None


def get_baked_tokens():
    global _baked_tokens
    global _baked_token_path
    global _baked_token_mtime
    if _baked_tokens:
        if (
            isfile(_baked_token_path)
            and stat(_baked_token_path).st_mtime == _baked_token_mtime
        ):
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
            _baked_token_path = fname
            _baked_token_mtime = stat(fname).st_mtime
            break
        except Exception:
            pass
    return _baked_tokens


def load_baked_token(url):
    url = url.rstrip("/") + "/"
    for k, v in get_baked_tokens().items():
        if url.startswith(k):
            return v


def include_baked_tokens(tdict):
    for k, v in get_baked_tokens().items():
        for k2 in tdict:
            if k2.startswith(k):
                break
        else:
            tdict[k] = v
            if k == "https://repo.anaconda.cloud/":
                tdict[k + "repo/"] = v
