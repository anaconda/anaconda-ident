_baked_tokens = None


def get_baked_tokens():
    global _baked_tokens
    if _baked_tokens is None:
        try:
            from conda.base.context import context

            # When importing the context module outside of
            # conda, the context object will not be initialized.
            # We detect this by looking for evidence that
            # anaconda_anon_usage has fully loaded
            if not getattr(context, "_aau_initialized", False):
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
