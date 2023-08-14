from conda.gateways import anaconda_client as ac
from anaconda_ident.tokens import include_baked_tokens


def _new_read_binstar_tokens():
    tokens = ac._old_read_binstar_tokens()
    include_baked_tokens(tokens)
    return tokens


if not hasattr(ac, "_old_read_binstar_tokens"):
    ac._old_read_binstar_tokens = ac.read_binstar_tokens
    ac.read_binstar_tokens = _new_read_binstar_tokens
