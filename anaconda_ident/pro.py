import getpass
import os
import platform
import sys
from logging import getLogger
from os.path import basename, join

import conda.base.context as c_context
from conda.auxlib.decorators import memoize
from conda.base.context import (
    Context,
    MapParameter,
    ParameterLoader,
    PrimitiveParameter,
    context,
    env_name,
)
from conda.gateways.connection.session import CondaHttpAuth

from . import __version__

log = getLogger(__name__)


BAKED_CONDARC = join(sys.prefix, "etc", "anaconda_ident.yml")
DEBUG = bool(os.environ.get("ANACONDA_IDENT_DEBUG"))


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


def get_environment_name():
    try:
        pfx = context.checked_prefix or context.target_prefix
        return basename(env_name(pfx))
    except Exception:
        return None


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


def get_config_value(key):
    for loc, rdict in context.raw_data.items():
        if key in rdict:
            return rdict[key]._raw_value, loc
    else:
        return None, None


def client_token_type():
    token_type, loc = get_config_value("anaconda_ident")
    if loc is None:
        log.debug("Selecting default token config")
        token_type = "default"
    elif loc == BAKED_CONDARC:
        log.debug("Hardcoded token config: %s", token_type)
    else:
        log.debug("Token config from context: %s", token_type)
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
    parts = ["ident/pro/" + __version__]
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
            from .patch import get_environment_token

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


def _new_apply_basic_auth(request):
    result = CondaHttpAuth._old_apply_basic_auth(request)
    token = client_token_string()
    if token:
        request.headers["X-Anaconda-Ident"] = token
    return result


# conda.base.context.SEARCH_PATH
# Add anaconda_ident's condarc location
if not hasattr(c_context, "_OLD_SEARCH_PATH"):
    sp = c_context._OLD_SEARCH_PATH = c_context.SEARCH_PATH
    n_sys = min(k for k, v in enumerate(sp) if v.startswith("$CONDA_ROOT"))
    c_context.SEARCH_PATH = sp[:n_sys] + (BAKED_CONDARC,) + sp[n_sys:]

# conda.gateways.connection.session.CondaHttpAuth
# Adds the X-Conda-Ident header to all conda requests
if not hasattr(CondaHttpAuth, "_old_apply_basic_auth"):
    CondaHttpAuth._old_apply_basic_auth = CondaHttpAuth._apply_basic_auth
    CondaHttpAuth._apply_basic_auth = staticmethod(_new_apply_basic_auth)

# conda.base.context.Context
# Adds anaconda_ident as a managed string config parameter
if not hasattr(Context, "anaconda_ident"):
    _param = ParameterLoader(PrimitiveParameter("default"))
    Context.anaconda_ident = _param
    Context.parameter_names += (_param._set_name("anaconda_ident"),)

# conda.base.context.Context
# Adds repo_tokens as a managed map config parameter
if not hasattr(Context, "repo_tokens"):
    _param = ParameterLoader(MapParameter(PrimitiveParameter("", str)))
    Context.repo_tokens = _param
    Context.parameter_names += (_param._set_name("repo_tokens"),)

if DEBUG:
    print(
        "| SEARCH_PATH:",
        "patched" if BAKED_CONDARC in c_context.SEARCH_PATH else "UNPATCHED",
    )
    print(
        "| CONDA_AUTH:",
        "patched"
        if getattr(CondaHttpAuth, "_old_apply_basic_auth", None)
        else "UNPATCHED",
    )
    print(
        "| ANACONDA_IDENT:",
        "patched" if hasattr(context, "anaconda_ident") else "UNPATCHED",
    )
    print(
        "| REPO_TOKENS:",
        "patched" if hasattr(context, "repo_tokens") else "UNPATCHED",
    )
    print("PRO patching completed")
