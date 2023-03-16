import base64
import getpass
import os
import platform
import sys
import hashlib

from conda.base.context import (
    Context,
    context,
    env_name,
    ParameterLoader,
    PrimitiveParameter,
)
from conda.gateways.connection import session as c_session
from conda.gateways.connection.session import CondaHttpAuth
from conda.gateways import anaconda_client as a_client
from conda.auxlib.decorators import memoize, memoizedproperty
from conda.cli import install as cli_install

from logging import getLogger
from os.path import join, isdir, basename, expanduser, exists
from urllib.parse import unquote_plus


log = getLogger(__name__)


BAKED_TOKEN_DIR = join(sys.prefix, "etc", "conda_ident")
BAKED_TOKEN_CONFIG = join(BAKED_TOKEN_DIR, "config")
DEBUG = bool(os.environ.get('CONDA_IDENT_DEBUG'))
if DEBUG:
    print("CONDA_IDENT DEBUGGING ENABLED")


_client_token_formats = {
    "none": "",
    "default": "cse",
    "username": "cseu",
    "hostname": "cseh",
    "environment": "csen",
    "userenv": "cseun",
    "userhost": "cseuh",
    "hostenv": "csehn",
    "full": "cseuhn",
}


def get_random_token(nchar, bytes=None):
    if bytes is None:
        bytes = os.urandom((nchar * 6 - 1) // 8 + 1)
    return base64.urlsafe_b64encode(bytes)[:nchar].decode("ascii")


def initialize_raw_tokens():
    Context.session_token = get_random_token(8)
    Context.client_token_raw = None
    cid_file = join(expanduser("~/.conda"), "client_token")
    client_token = ""
    if os.path.exists(cid_file):
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


def get_environment_name():
    target_prefix = get_environment_prefix()
    return basename(env_name(target_prefix)) if target_prefix else None


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


def get_username():
    try:
        return getpass.getuser()
    except Exception as exc:
        log.debug("getpass.getuser raised an exception: %s" % exc)


def get_hostname():
    value = platform.node()
    if not value:
        log.debug("platform.node returned an empty value")
    return value


# Separate this out so it can be called in testing
def get_baked_token_config():
    if exists(BAKED_TOKEN_CONFIG):
        with open(BAKED_TOKEN_CONFIG, "r") as fp:
            return fp.read().strip() or None


def client_token_type():
    token_type = get_baked_token_config()
    if token_type:
        log.debug("Hardcoded token config: %s", token_type)
    if token_type is None:
        token_type = context.client_token
        if token_type:
            log.debug("Token config from context: %s", token_type)
    if token_type is None:
        log.debug("Selecting default token config")
        token_type = "default"
    fmt_parts = token_type.split(":", 1)
    fmt = _client_token_formats.get(fmt_parts[0], fmt_parts[0])
    if len(fmt_parts) > 1:
        if not fmt and fmt_parts[0] != "none":
            fmt = "cseo"
        elif "o" not in fmt:
            fmt += "o"
    elif "o" in fmt:
        log.warning("Expected an organization string; none provided.")
        fmt = fmt.replace("o", "")
    fmt_parts[0] = "".join(c for c in fmt if c in "csuhoen")
    token_type = ":".join(fmt_parts)
    log.debug("Final token config: %s", token_type)
    return token_type


@memoize
def client_token_string():
    if not hasattr(Context, "session_token"):
        initialize_raw_tokens()
    parts = []
    token_type = client_token_type()
    fmt_parts = token_type.split(":", 1)
    for code in fmt_parts[0]:
        value = None
        if code == "c":
            value = Context.client_token_raw[:8]
        elif code == "s":
            value = Context.session_token
        elif code == "u":
            value = get_username()
        elif code == "h":
            value = get_hostname()
        elif code == "o":
            value = fmt_parts[1]
        elif code == "e":
            value = get_environment_token()
        elif code == "n":
            value = get_environment_name()
        else:
            log.warning("Unexpected client token code: %s", code)
            value = None
        if value:
            parts.append(code + "/" + value)
    result = " ".join(parts)
    log.debug("Full client token: %s", result)
    return result


def _new_user_agent(ctx):
    token = client_token_string()
    result = ctx._old_user_agent
    return result + " " + token if token else result


def _new_apply_basic_auth(request):
    result = CondaHttpAuth._old_apply_basic_auth(request)
    token = client_token_string()
    if token:
        request.headers["X-Conda-Ident"] = token
    return result


def _new_check_prefix(prefix, json=False):
    context.checked_prefix = prefix
    cli_install._old_check_prefix(prefix, json)


# Separate this out so it can be called in testing
def get_baked_binstar_tokens():
    tokens = {}
    if isdir(BAKED_TOKEN_DIR):
        for tkn_entry in os.scandir(BAKED_TOKEN_DIR):
            if tkn_entry.name.endswith(".token"):
                url = unquote_plus(tkn_entry.name[:-6])
                with open(tkn_entry.path) as f:
                    tokens[url] = f.read()
    return tokens


def _new_read_binstar_tokens():
    tokens = a_client._old_read_binstar_tokens()
    tokens.update(get_baked_binstar_tokens())
    return tokens


# Save the raw token data in Context class attributes
# to ensure they are passed between subprocesses
if not hasattr(Context, "client_token_raw"):
    initialize_raw_tokens()
    if DEBUG:
        print("RAW TOKEN:", "set" if getattr(context, 'client_token_raw', None) else "MISSING")

# conda.base.context.Context.user_agent
# Adds the ident token to the user agent string
if not hasattr(Context, "_old_user_agent"):
    Context._old_user_agent = Context.user_agent
    # Using a different name ensures that this is stored
    # in sthe cache in a different place than the original
    Context.user_agent = memoizedproperty(_new_user_agent)
    if DEBUG:
        print("USER_AGENT:", "patched" if getattr(Context, '_old_user_agent', None) else "UNPATCHED")

# conda.gateways.connection.session.CondaHttpAuth
# Adds the X-Conda-Ident header to all conda requests
if not hasattr(CondaHttpAuth, "_old_apply_basic_auth"):
    CondaHttpAuth._old_apply_basic_auth = CondaHttpAuth._apply_basic_auth
    CondaHttpAuth._apply_basic_auth = staticmethod(_new_apply_basic_auth)
    if DEBUG:
        print("CONDA_AUTH:", "patched" if getattr(CondaHttpAuth, '_old_apply_basic_auth', None) else "UNPATCHED")

# conda.cli.install.check_prefix
# Collects the prefix computed there so that we can properly
# detect the creation of environments using "conda env create"
if not hasattr(cli_install, "_old_check_prefix"):
    cli_install._old_check_prefix = cli_install.check_prefix
    cli_install.check_prefix = _new_check_prefix
    context.checked_prefix = None
    if DEBUG:
        print("CHECK_PREFIX:", "patched" if getattr(cli_install, '_old_check_prefix', None) else "UNPATCHED")

# conda.gateways.anaconda_client.read_binstar_tokens
# conda.gateways.connection.session.read_binstar_tokens
# Inserts hardcoded repo tokens
if not hasattr(a_client, "_old_read_binstar_tokens"):
    a_client._old_read_binstar_tokens = a_client.read_binstar_tokens
    a_client.read_binstar_tokens = _new_read_binstar_tokens
    c_session.read_binstar_tokens = _new_read_binstar_tokens
    if DEBUG:
        print("READ_BINSTAR_TOKENS:", "patched" if getattr(a_client, '_old_read_binstar_tokens', None) else "UNPATCHED")

# conda.base.context.Context
# Adds client_token as a managed string config parameter
if not hasattr(Context, "client_token"):
    _param = ParameterLoader(PrimitiveParameter("default"))
    Context.client_token = _param
    Context.parameter_names += (_param._set_name("client_token"),)
    if DEBUG:
        print("CLIENT_TOKEN_CONFIG:", "patched" if getattr(context, 'client_token', None) else "UNPATCHED")
