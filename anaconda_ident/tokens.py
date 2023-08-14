_baked_tokens = None


def get_baked_tokens():
    global _baked_tokens
    if _baked_tokens is None:
        try:
            from conda.base.context import context

            if not getattr(context, "repo_tokens", None):
                context.__init__()
            _baked_tokens = context.repo_tokens
        except Exception:
            _baked_tokens = {}
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
