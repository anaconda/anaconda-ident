import base64
import getpass
import platform
import sys
from os import environ
from os.path import basename

from anaconda_anon_usage import tokens
from anaconda_anon_usage import utils as aau_utils
from anaconda_anon_usage.utils import _debug, cached
from conda.activate import _Activator
from conda.auxlib.decorators import memoizedproperty
from conda.base.context import (
    Context,
    MapParameter,
    ParameterLoader,
    PrimitiveParameter,
    context,
    env_name,
)
from conda.gateways import anaconda_client as ac
from conda.gateways.connection import session as cs

from . import __version__
from .tokens import hash_string, include_baked_tokens

# Provide ANACONDA_IDENT_DEBUG and ANACONDA_IDENT_DEBUG_PREFIX
# as synonyms to their a-a-u equivalents. *_DEBUG enables debug
# logging of course; _PREFIX does so as well but prepends the
# given string to each debug log value.
DPREFIX = environ.get("ANACONDA_IDENT_DEBUG_PREFIX") or aau_utils.DPREFIX or ""
DEBUG = environ.get("ANACONDA_IDENT_DEBUG") or aau_utils.DEBUG or DPREFIX
if DEBUG:
    aau_utils.DPREFIX = DPREFIX
    aau_utils.DEBUG = True


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
    "fullhash": "cseUHN",
}


def get_environment_prefix():
    return (
        getattr(context, "checked_prefix", None) or context.target_prefix or sys.prefix
    )


def get_environment_name(prefix=None, hash=False, pepper=None):
    prefix = prefix or get_environment_prefix()
    if not prefix:
        return None
    value = basename(env_name(prefix))
    if hash:
        value = hash_string("environment", value, pepper)
    return value


def get_username(hash=False, pepper=None):
    try:
        result = getpass.getuser()
        if hash:
            result = hash_string("username", result, pepper)
        return result
    except Exception as exc:
        _debug("getpass.getuser raised an exception: %s" % exc)


def get_hostname(hash=False, pepper=None):
    value = platform.node()
    if not value:
        _debug("platform.node returned an empty value")
    if hash:
        value = hash_string("hostname", value, pepper)
    return value


def client_token_type():
    token_type = context.anaconda_ident
    if DEBUG:
        token_disp = token_type
        if token_disp.count(":") > 1:
            token_disp = token_disp.rsplit(":", 1)[0] + ":<pepper>"
        _debug("Token config from context: %s", token_disp)
    org = pepper = None
    if ":" in token_type:
        token_type, org = token_type.split(":", 1)
        if ":" in org:
            org, pepper = org.split(":", 1)
            try:
                npad = len(pepper) % 3
                npad = 3 - npad if npad else 0
                pepper = base64.b64decode(pepper + "=" * npad)
            except Exception:
                pass
    fmt = _client_token_formats.get(token_type, token_type)
    _debug("Preliminary usage tokens: %s", fmt)
    if org and "o" not in fmt:
        _debug("Organization string provided; adding o to format")
        fmt += "o"
    elif not org and "o" in fmt:
        _debug("Expected an organization string; none provided.")
        fmt = fmt.replace("o", "")
    fmt = "cse" + "".join(dict.fromkeys(c for c in fmt if c in "uhonUHN"))
    _debug("Final token config: %s %s", fmt, org)
    return fmt, org, pepper


@cached
def client_token_string():
    _debug("Entering client_token_string")
    parts = ["aau/" + tokens.version_token(), "aid/" + __version__]
    fmt, org, pepper = client_token_type()
    pfx = get_environment_prefix()
    _debug("Environmment: %s", pfx)
    for code in fmt:
        value = None
        if code == "c":
            value = tokens.client_token()
        elif code == "s":
            value = tokens.session_token()
        elif code == "e":
            value = tokens.environment_token(pfx)
        elif code in "uU":
            value = get_username(hash=code == "U", pepper=pepper)
        elif code in "hH":
            value = get_hostname(hash=code == "H", pepper=pepper)
        elif code == "o":
            value = org
        elif code in "nN":
            value = get_environment_name(pfx, hash=code == "N", pepper=pepper)
        else:
            _debug("Unexpected client token code: %s", code)
            value = None
        if value:
            parts.append(code + "/" + value)
    result = " ".join(parts)
    _debug("Full client token: %s", result)
    return result


def _aid_user_agent(ctx):
    result = ctx._old_user_agent
    tokens = client_token_string()
    if tokens:
        result = result + " " + tokens
    return result


def _aid_read_binstar_tokens():
    tokens = ac._old_read_binstar_tokens()
    include_baked_tokens(tokens)
    return tokens


def main():
    if getattr(context, "_aid_initialized", None) is not None:
        _debug("anaconda_ident already active")
        return False
    _debug("Applying anaconda_ident context patch")

    # This helps us determine if the patching is comlpete
    context._aid_initialized = False

    if getattr(context, "_aau_initialized", None) is None:
        from anaconda_anon_usage import patch

        patch.main(plugin=True)

    # conda.base.context.Context
    # Adds anaconda_ident as a managed string config parameter
    _debug("Adding the anaconda_ident config parameter")
    _param = ParameterLoader(PrimitiveParameter("default"))
    Context.anaconda_ident = _param
    Context.parameter_names += (_param._set_name("anaconda_ident"),)

    # conda.base.context.Context
    # Adds repo_tokens as a managed map config parameter
    _debug("Adding the repo_tokens config parameter")
    _param = ParameterLoader(MapParameter(PrimitiveParameter("", str)))
    Context.repo_tokens = _param
    Context.parameter_names += (_param._set_name("repo_tokens"),)

    # conda.base.context.Context
    # Adds anaconda_heartbeat as a managed boolean config parameter
    _debug("Adding the anaconda_heartbeat config parameter")
    _param = ParameterLoader(PrimitiveParameter(False))
    Context.anaconda_heartbeat = _param
    Context.parameter_names += (_param._set_name("anaconda_heartbeat"),)

    # conda.base.context.Context.user_agent
    # Adds the ident token to the user agent string
    _debug("Replacing anaconda_anon_usage user agent in module")
    assert hasattr(Context, "_old_user_agent")
    Context.user_agent = memoizedproperty(_aid_user_agent)

    _debug("Replacing read_binstar_tokens")
    ac._old_read_binstar_tokens = ac.read_binstar_tokens
    ac.read_binstar_tokens = cs.read_binstar_tokens = _aid_read_binstar_tokens

    if hasattr(_Activator, "_old_activate"):
        _debug("Verified heartbeat patch")
    else:
        _debug("Applying heartbeat patch")
        try:
            from anaconda_ident import install

            install._patch_heartbeat(None)
        except Exception as exc:
            _debug("Error installing heartbeat: %s", exc)

    context._aid_initialized = True

    return True
