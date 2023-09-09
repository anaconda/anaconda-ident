import functools
import getpass
import os
import platform
import sys
from os.path import basename, join

import conda.base.context as c_context
from anaconda_anon_usage import patch as aau_patch
from anaconda_anon_usage import tokens
from anaconda_anon_usage.utils import _debug
from conda.base.context import (
    Context,
    MapParameter,
    ParameterLoader,
    PrimitiveParameter,
    context,
    env_name,
)

from . import __version__

BAKED_CONDARC = join(sys.prefix, "etc", "anaconda_ident.yml")
DEBUG = bool(
    os.environ.get("ANACONDA_IDENT_DEBUG")
    or os.environ.get("ANACONDA_ANON_USAGE_DEBUG")
)


_client_token_formats = {
    "none": "",
    "default": "",
    "username": "u",
    "hostname": "h",
    "environment": "n",
    "userenv": "un",
    "userhost": "uh",
    "hostenv": "hn",
    "full": "uhn",
}


def get_environment_name():
    prefix = context.checked_prefix or context.target_prefix or sys.prefix
    return basename(env_name(prefix)) if prefix else None


def get_username():
    try:
        return getpass.getuser()
    except Exception as exc:
        _debug("getpass.getuser raised an exception: %s" % exc)


def get_hostname():
    value = platform.node()
    if not value:
        _debug("platform.node returned an empty value")
    return value


def get_config_value(key, default=None, boolify=False):
    for loc, rdict in context.raw_data.items():
        if key in rdict:
            result = rdict[key]._raw_value
            break
    else:
        loc = None
        result = default
    if boolify and isinstance(result, str):
        result = result.lower() in ("y", "yes", "t", "true", "on")
    return result, loc


def client_token_type():
    token_type, loc = get_config_value("anaconda_ident", "default")
    if loc is None:
        _debug("Default token config: %s", token_type)
    elif loc == BAKED_CONDARC:
        _debug("Hardcoded token config: %s", token_type)
    else:
        _debug("Token config from context: %s", token_type)
    fmt_parts = token_type.split(":", 1)
    fmt = _client_token_formats.get(fmt_parts[0], fmt_parts[0])
    if len(fmt_parts) > 1:
        if not fmt and fmt_parts[0] != "none":
            fmt = "o"
        elif "o" not in fmt:
            fmt += "o"
    elif "o" in fmt:
        _debug("Expected an organization string; none provided.")
        fmt = fmt.replace("o", "")
    _debug("Preliminary usage tokens: %s", fmt)
    anon_usage, _ = get_config_value("anaconda_anon_usage", True, True)
    if anon_usage is None or anon_usage:
        _debug("Adding anon_usage tokens")
        fmt = "cse" + fmt
    fmt_parts[0] = "".join(dict.fromkeys(c for c in fmt if c in "cseuhon"))
    token_type = ":".join(fmt_parts)
    _debug("Final token config: %s", token_type)
    return token_type


@functools.lru_cache(maxsize=None)
def client_token_string():
    parts = ["aau/" + tokens.version_token(), "aid/" + __version__]
    token_type = client_token_type()
    fmt_parts = token_type.split(":", 1)
    for code in fmt_parts[0]:
        value = None
        if code == "c":
            value = tokens.client_token()
        elif code == "s":
            value = tokens.session_token()
        elif code == "e":
            value = tokens.environment_token()
        elif code == "u":
            value = get_username()
        elif code == "h":
            value = get_hostname()
        elif code == "o":
            value = fmt_parts[1]
        elif code == "n":
            value = get_environment_name()
        else:
            _debug("Unexpected client token code: %s", code)
            value = None
        if value:
            parts.append(code + "/" + value)
    result = " ".join(parts)
    _debug("Full client token: %s", result)
    return result


def _aid_user_agent(ctx):
    return ctx._old_user_agent + " " + client_token_string()


# conda.base.context.SEARCH_PATH
# Add anaconda_ident's condarc location
if not hasattr(c_context, "_OLD_SEARCH_PATH"):
    _debug("Adding anaconda_ident.yml to the search path")
    sp = c_context._OLD_SEARCH_PATH = c_context.SEARCH_PATH
    n_sys = min(k for k, v in enumerate(sp) if v.startswith("$CONDA_ROOT"))
    c_context.SEARCH_PATH = sp[:n_sys] + (BAKED_CONDARC,) + sp[n_sys:]

# conda.base.context.Context
# Adds anaconda_ident as a managed string config parameter
if not hasattr(Context, "anaconda_ident"):
    _debug("Adding the anaconda_ident config parameter")
    _param = ParameterLoader(PrimitiveParameter("default"))
    Context.anaconda_ident = _param
    Context.parameter_names += (_param._set_name("anaconda_ident"),)

# conda.base.context.Context
# Adds repo_tokens as a managed map config parameter
if not hasattr(Context, "repo_tokens"):
    _debug("Adding the repo_tokens config parameter")
    _param = ParameterLoader(MapParameter(PrimitiveParameter("", str)))
    Context.repo_tokens = _param
    Context.parameter_names += (_param._set_name("repo_tokens"),)

# anaconda_anon_usage.patch._new_user_agent
if not hasattr(aau_patch, "_old_aau_user_agent"):
    _debug("Replacing anaconda_anon_usage user agent in module")
    aau_patch._old_aau_user_agent = aau_patch._new_user_agent
    aau_patch._new_user_agent = _aid_user_agent
