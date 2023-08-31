import base64
import hashlib
import os
import sys
from logging import getLogger
from os.path import dirname, exists, expanduser, join

from conda.auxlib.decorators import memoize, memoizedproperty
from conda.base.context import Context, context
from conda.cli import install as cli_install

from . import __version__

log = getLogger(__name__)


BAKED_CONDARC = join(sys.prefix, "etc", "anaconda_ident.yml")
DEBUG = bool(os.environ.get("ANACONDA_IDENT_DEBUG"))


def get_random_token(nchar, bytes=None):
    if bytes is None:
        bytes = os.urandom((nchar * 6 - 1) // 8 + 1)
    return base64.urlsafe_b64encode(bytes)[:nchar].decode("ascii")


def initialize_raw_tokens():
    Context.session_token = get_random_token(8)
    Context.client_token_raw = None
    cid_file = join(expanduser("~/.conda"), "anaconda_ident")
    client_token = ""
    if exists(cid_file):
        try:
            # Use just the first line of the file, if it exists
            client_token = "".join(open(cid_file).read().splitlines()[:1])
            log.debug("Retrieved client token: %s", client_token)
        except Exception as exc:
            log.debug("Unexpected error reading client token: %s", exc)
    if len(client_token) < 64:
        if len(client_token) > 0:
            log.debug("Creating longer token for hashing")
        client_token = get_random_token(64)
        try:
            with open(cid_file, "w") as fp:
                fp.write(client_token)
            log.debug("Generated new client token: %s", client_token)
            log.debug("Client token saved: %s", cid_file)
        except Exception as exc:
            log.debug("Unexpected error writing client token file: %s", exc)
            client_token = ""
    Context.client_token_raw = client_token


def get_environment_prefix():
    try:
        return context.checked_prefix or context.target_prefix
    except Exception:
        pass


def get_environment_token():
    value = get_environment_prefix()
    if value is None:
        return None
    # Do not create an environment token if we don't have
    # enough salt to hash it
    if len(Context.client_token_raw) < 64:
        log.debug("client_token_raw not long enough to hash")
        return None
    # Use the client token as salt for the hash function to
    # ensure the receiver cannot decode the environment name
    hashval = Context.client_token_raw + value
    hash = hashlib.sha1(hashval.encode("utf-8"))
    return get_random_token(8, hash.digest())


def get_config_value(key):
    for loc, rdict in context.raw_data.items():
        if key in rdict:
            return rdict[key]._raw_value, loc
    else:
        return None, None


@memoize
def client_token_string():
    parts = ["ident/" + __version__]
    parts.append("c/" + Context.client_token_raw[:8])
    parts.append("s/" + Context.session_token)
    value = get_environment_token()
    if value:
        parts.append("e/" + value)
    result = " ".join(parts)
    log.debug("Full client token: %s", result)
    return result


def _new_user_agent(ctx):
    token = client_token_string()
    result = ctx._old_user_agent
    return result + " " + token if token else result


def _new_check_prefix(prefix, json=False):
    context.checked_prefix = prefix
    cli_install._old_check_prefix(prefix, json)


if DEBUG:
    print("ANACONDA_IDENT DEBUGGING ENABLED")

# Save the raw token data in Context class attributes
# to ensure they are passed between subprocesses
if not hasattr(Context, "client_token_raw"):
    initialize_raw_tokens()

# conda.base.context.Context.user_agent
# Adds the ident token to the user agent string
if not hasattr(Context, "_old_user_agent"):
    Context._old_user_agent = Context.user_agent
    # Using a different name ensures that this is stored
    # in sthe cache in a different place than the original
    Context.user_agent = memoizedproperty(_new_user_agent)

# conda.cli.install.check_prefix
# Collects the prefix computed there so that we can properly
# detect the creation of environments using "conda env create"
if not hasattr(cli_install, "_old_check_prefix"):
    cli_install._old_check_prefix = cli_install.check_prefix
    cli_install.check_prefix = _new_check_prefix
    context.checked_prefix = None

if DEBUG:
    print(
        "| RAW TOKEN:",
        "loaded" if getattr(context, "client_token_raw", None) else "MISSING",
    )
    print(
        "| USER AGENT:",
        "patched" if getattr(Context, "_old_user_agent", None) else "UNPATCHED",
    )
    print(
        "| CHECK_PREFIX:",
        "patched" if getattr(cli_install, "_old_check_prefix", None) else "UNPATCHED",
    )


if exists(join(dirname(__file__), "pro.py")) and not os.environ.get(
    "ANACONDA_IDENT_DEBUG_NO_PRO"
):
    from .pro import *  # noqa
elif DEBUG:
    print("BASE patching completed")
