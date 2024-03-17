import json
import os
import re
import subprocess
import sys
from os.path import basename, join

from anaconda_anon_usage import __version__ as aau_version
from conda.base.context import context
from conda.models.channel import Channel

from anaconda_ident import __version__ as aid_version
from anaconda_ident import patch as patch

context.__init__()

# Make sure we always try to fetch. Prior versions of this
# test code used a fake channel to accomplish this, but the
# fetch behavior of conda changed to frustrate that approach.
os.environ["CONDA_LOCAL_REPODATA_TTL"] = "0"

def get_config_value(key, subkey=None):
    """
    Why not just do getattr(context, key)? Well, we actually want
    to know *where* the config value is set
    """
    result = getattr(context, key)
    if subkey is not None:
        result = getattr(result, subkey)
    for loc, rdict in context.raw_data.items():
        if key in rdict:
            break
    else:
        loc = None
    return result, loc


print("Environment variables:")
print("-----")
print("CONFIG_STRING:", os.environ.get("CONFIG_STRING") or "")
print("DEFAULT_CHANNELS:", os.environ.get("DEFAULT_CHANNELS") or "")
print("CHANNEL_ALIAS:", os.environ.get("CHANNEL_ALIAS") or "")
print("REPO_TOKEN:", os.environ.get("REPO_TOKEN") or "")
print("ANACONDA_IDENT_DEBUG:", os.environ.get("ANACONDA_IDENT_DEBUG") or "")
print("ANACONDA_ANON_USAGE_DEBUG:", os.environ.get("ANACONDA_ANON_USAGE_DEBUG") or "")
print("-----")
p = subprocess.run(
    ["python", "-m", "conda", "info"],
    capture_output=True,
    check=True,
    stdin=subprocess.DEVNULL,
)
print(p.stdout.decode("utf-8").strip())

# Verify baked configurations, if any
success = True
config_env = os.environ.get("CONFIG_STRING") or ""
config_baked = context.anaconda_ident
if config_env:
    if config_baked != config_env:
        print(
            "Baked configuration mismatch:\n - expected: %s\n - found: %s"
            % (config_env, config_baked)
        )
        success = False
    else:
        print("Baked configuration:", config_env)

calias_env = (os.environ.get("CHANNEL_ALIAS") or "").rstrip("/")
calias_baked = context.channel_alias.base_url
if calias_env:
    if calias_env != calias_baked:
        print(
            "Baked channel alias mismatch:\n - expected: %s\n - found: %s"
            % (calias_env, calias_baked)
        )
        success = False
    else:
        print("Baked channel alias:", calias_env)

defchan_env = os.environ.get("DEFAULT_CHANNELS") or ""
defchan_env = [c for c in defchan_env.split(",")] if defchan_env else []
defchan_baked = [c.base_url for c in context.default_channels]
if defchan_env:
    if [Channel(c).base_url for c in defchan_env] != defchan_baked:
        print(
            "Baked default channels mismatch:\n - expected: %s\n - found: %s"
            % (defchan_env, defchan_baked)
        )
        success = False
    else:
        print("Baked default channels:", defchan_env)

# In a "baked" configuration, the client token config is
# hardcoded into the package itself
token_baked = dict(context.repo_tokens)
token_env = os.environ.get("REPO_TOKEN") or ""
if token_env:
    token_chan = [c for c in defchan_env + [calias_env] if c and "/" in c]
    token_chan = "/".join(token_chan[0].split("/", 3)[:3]) + "/" if token_chan else ""
    token_env = {token_chan: token_env}
else:
    token_env = None

if not token_env and token_baked:
    print("Unexpected baked token set:", token_baked)
    success = False
elif token_env and token_env != token_baked:
    print(
        "Baked token mismatch:\n - expected: %s\n - found: %s"
        % (token_env, token_baked)
    )
    success = False
elif token_env:
    print("Baked token set:", token_env)

if not success:
    sys.exit(-1)

# In theory, test_fields = _client_token_formats[param]
# I'm hardcoding them here so the test doesn't depend on that
# part of the code, with the exception of "baked" test below.
test_patterns = (
    ("full:org1", "uhno"),
    ("none", ""),
    ("default", ""),
    ("username", "u"),
    ("hostname", "h"),
    ("environment", "n"),
    ("userenv", "un"),
    ("userhost", "uh"),
    ("hostenv", "hn"),
    ("full", "uhn"),
    ("default:org2", "o"),
    (":org3", "o"),
    ("none:org4", "o"),
    ("u", "u"),
    ("h", "h"),
    ("n", "n"),
    ("o:org4", "o"),
    ("o", ""),
)
all_fields = {"aau", "aid", "c", "s", "e", "u", "h", "n", "o"}
states = (
    (True, True),
    (False, True),
    (True, True),
    (True, False),
    (False, False),
    (True, False),
    (True, True),
)

test_org = None
if config_env:
    fmt = config_baked.split(":", 1)[0]
    fmt = patch._client_token_formats.get(fmt, fmt)
    if "o" not in fmt and ":" in config_baked:
        fmt += "o"
    test_patterns = [(config_baked, fmt)]
    print("test_patterns:", test_patterns)

proc = subprocess.run(
    ["conda", "info", "--envs", "--json"],
    check=False,
    capture_output=True,
    text=True,
)
pfx_s = join(sys.prefix, "envs") + os.sep
pdata = json.loads(proc.stdout)
envs = [e for e in pdata["envs"] if e == sys.prefix or e.startswith(pfx_s)]
envs = {("base" if e == sys.prefix else basename(e)): e for e in envs}
tp_0 = test_patterns[0]
test_patterns = [t + ("",) for t in test_patterns]
for env in envs:
    # Test each env twice to confirm that
    # we get the same token each time
    test_patterns.append(tp_0 + (env,))
    test_patterns.append(tp_0 + (env,))
maxlen = max(len(e) for e in envs)

nfailed = 0
other_tokens = {"aau": aau_version, "aid": aid_version}
all_session_tokens = set()
all_environments = set()

id_last = False
need_header = True
for aau_state, id_state in states:
    os.environ["CONDA_ANACONDA_ANON_USAGE"] = "on" if aau_state else "off"
    if id_state != id_last:
        id_last = id_state
        flag = "--enable" if id_state else "--disable"
        p = subprocess.run(
            ["python", "-m", "anaconda_ident.install", flag], capture_output=True
        )
        print(p.stdout.decode("utf-8").strip())
        need_header = True
    anon_flag = "T" if aau_state else "F"
    for param, test_fields, envname in test_patterns:
        other_tokens["o"] = param.split(":", 1)[-1] if ":" in param else ""
        other_tokens["n"] = envname if envname else "base"
        os.environ["CONDA_ANACONDA_IDENT"] = param
        if id_state:
            test_fields = "cse" + test_fields
        else:
            test_fields = "cse" if aau_state else ""
        test_fields = "".join(dict.fromkeys(test_fields))
        expected = list(test_fields)
        expected.append("aau")
        if id_state:
            expected.append("aid")
        # Make sure to leave override-channels and the full channel URL in here.
        # This allows this command to run fully no matter what we do to channel_alias
        # and default_channels
        cmd = ["conda", "install", "-vvv", "fakepackage"]
        if envname:
            cmd.extend(["-n", envname])
        proc = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
        )
        user_agent = ""
        for v in proc.stderr.splitlines():
            # Unfortunately conda has evolved how it logs request headers
            # So this regular expression attempts to match multiple forms
            # > User-Agent: conda/...
            # .... {'User-Agent': 'conda/...', ...}
            match = re.match(r'.*User-Agent(["\']?): *(["\']?)(.+)', v)
            if match:
                _, delim, user_agent = match.groups()
                if delim and delim in user_agent:
                    user_agent = user_agent.split(delim, 1)[0]
                break
        new_values = [t.split("/", 1) for t in user_agent.split(" ") if "/" in t]
        new_values = {k: v for k, v in new_values if k in all_fields}
        header = " ".join(f"{k}/{v}" for k, v in new_values.items())
        # Confirm that all of the expected tokens are present

        missing = set(expected) - set(new_values)
        extras = set(new_values) - set(expected)
        status = []
        if missing:
            status.append(f"{','.join(missing)} MISSING")
        if extras:
            status.append(f"{','.join(extras)} EXTRA")
        modified = []
        duplicated = []
        for k, v in new_values.items():
            if k == "s":
                if new_values["s"] in all_session_tokens:
                    status.append("SESSION")
                all_session_tokens.add(new_values["s"])
                continue
            if k == "e":
                k = "e/" + (envname or "base")
                if k not in other_tokens and v in all_environments:
                    duplicated.append("e")
                all_environments.add(v)
            if other_tokens.setdefault(k, v) != v:
                modified.append(k)
        if duplicated:
            status.append(f"DUPLICATED: {','.join(duplicated)}")
        if modified:
            status.append(f"MODIFIED: {','.join(modified)}")
        status = ", ".join(status)
        if need_header:
            need_header = False
            print("|", header)
            print(f"anon    ident     {'envname':{maxlen}} fields  status")
            print(f"---- ------------ {'-' * maxlen} ------- ------")
        print(
            f"{anon_flag:4} {param:12} {envname:{maxlen}} {test_fields:7} {status or 'OK'}"
        )
        if status:
            print("|", header)
        if status:
            nfailed += 1
            if "--fast" in sys.argv:
                sys.exit(1)

print("")
print("Checking environment tokens")
print("---------------------------")
for k, v in other_tokens.items():
    if k.startswith("e/"):
        pfx = envs[k[2:]]
        tpath = join(pfx, "etc", "aau_token")
        try:
            with open(tpath) as fp:
                token = fp.read().strip()
        except Exception:
            token = ""
        status = "OK" if token == v else "XX"
        print(f"{k[2:]:{maxlen}} | {v} {token} | {status}")
        if token != v:
            nfailed += 1
print("---------------------------")

print("FAILURES:", nfailed)
sys.exit(nfailed)
