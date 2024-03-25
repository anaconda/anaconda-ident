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


def hash_string(what, s, pepper=None):
    from base64 import urlsafe_b64encode
    from hashlib import blake2b

    from anaconda_anon_usage.utils import _debug

    if isinstance(pepper, str):
        pepper = pepper.encode("utf-8")
    person = what.encode("utf-8")
    pepper = (pepper or b"")[: blake2b.SALT_SIZE]
    hfunc = blake2b(s.encode("utf-8"), digest_size=16, person=person, salt=pepper)
    data = hfunc.digest()
    result = urlsafe_b64encode(data).strip(b"=").decode("ascii")
    _debug("Hashed %s token: %s", what, result)
    return result


def main():
    import sys

    if len(sys.argv) != 4 or sys.argv[1] not in ("username", "hostname", "environment"):
        from os.path import basename

        ename = basename(sys.argv[0])
        print(
            f"Usage: {ename} <username|hostname|environment> <value> <organization>",
            file=sys.stderr,
        )
        sys.exit(0 if len(sys.argv) == 1 or "--help" in sys.argv else -1)
    print(hash_string(*sys.argv[1:]))
