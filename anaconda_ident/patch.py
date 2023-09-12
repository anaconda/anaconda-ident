import getpass
import platform
import sys
from os import environ
from os.path import basename, join

import conda.base.context as c_context
from anaconda_anon_usage import patch as aau_patch
from anaconda_anon_usage import tokens
from anaconda_anon_usage import utils as aau_utils
from anaconda_anon_usage.utils import _debug, cached
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

# Provide ANACONDA_IDENT_DEBUG and ANACONDA_IDENT_DEBUG_PREFIX
# as synonyms to their a-a-u equivalents. *_DEBUG enables debug
# logging of course; _PREFIX does so as well but prepends the
# given string to each debug log value.
DPREFIX = environ.get("ANACONDA_IDENT_DEBUG_PREFIX") or ""
DEBUG = environ.get("ANACONDA_IDENT_DEBUG") or DPREFIX
if DEBUG:
    aau_utils.DPREFIX = aau_utils.DPREFIX or DPREFIX
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
}


def get_environment_name():
    prefix = (
        getattr(context, "checked_prefix", None) or context.target_prefix or sys.prefix
    )
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


def client_token_type():
    token_type = context.anaconda_ident
    _debug("Token config from context: %s", token_type)
    if ":" in token_type:
        token_type, org = token_type.split(":", 1)
    else:
        org = ""
    fmt = _client_token_formats.get(token_type, token_type)
    _debug("Preliminary usage tokens: %s", fmt)
    if org and "o" not in fmt:
        _debug("Organization string provided; adding o to format")
        fmt += "o"
    elif not org and "o" in fmt:
        _debug("Expected an organization string; none provided.")
        fmt = fmt.replace("o", "")
    fmt = "cse" + "".join(dict.fromkeys(c for c in fmt if c in "uhon"))
    _debug("Final token config: %s %s", fmt, org)
    return fmt, org


@cached
def client_token_string():
    parts = ["aau/" + tokens.version_token(), "aid/" + __version__]
    fmt, org = client_token_type()
    for code in fmt:
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
            value = org
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
    result = ctx._old_user_agent
    tokens = client_token_string()
    if tokens:
        result = result + " " + tokens
    return result


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
