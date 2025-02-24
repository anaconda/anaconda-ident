import os
import subprocess
import sys
from os.path import exists, join

from anaconda_anon_usage.utils import _random_token
from conda.base.context import context
from conda.models.channel import Channel
from test_utils import get_test_envs, other_tokens, verify_user_agent

from anaconda_ident import patch

patch.main()
context.__init__()

# Make sure we always try to fetch. Prior versions of this
# test code used a fake channel to accomplish this, but the
# fetch behavior of conda changed to frustrate that approach.
os.environ["CONDA_LOCAL_REPODATA_TTL"] = "0"


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
    check=False,
    stdin=subprocess.DEVNULL,
)
print(p.stdout.decode("utf-8").strip())
print(p.stderr.decode("utf-8").strip())
if p.returncode != 0:
    sys.exit(-1)

# Verify baked configurations, if any
success = True
config_env = os.environ.get("CONFIG_STRING") or ""
config_baked = context.anaconda_ident
if config_baked.count(":") == 2:
    config_baked = config_baked.rsplit(":", 1)[0]
config_baked = config_baked.rstrip(":")
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
# A capital O represents an on-disk organization token.
test_patterns = (
    ("full:org1", "uhno"),
    ("full:org1", "uhnoO"),
    ("full", "unhO"),
    ("none", ""),
    ("default", ""),
    ("username", "u"),
    ("hostname", "h"),
    ("environment", "n"),
    ("userenv", "un"),
    ("userhost", "uh"),
    ("hostenv", "hn"),
    ("full", "uhn"),
    ("fullhash", "UHN"),
    ("default:org2", "o"),
    (":org3", "o"),
    ("none:org4", "o"),
    ("none", "O"),
    ("u", "u"),
    ("h", "h"),
    ("n", "n"),
    ("U", "U"),
    ("H", "H"),
    ("N", "N"),
    ("o:org4", "o"),
    ("o", ""),
    ("", "O"),
)

test_org = None
if config_env:
    fmt = config_baked.split(":", 1)[0]
    fmt = patch._client_token_formats.get(fmt, fmt)
    if "o" not in fmt and ":" in config_baked:
        fmt += "o"
    test_patterns = [(config_baked, fmt)]
    print("test_patterns:", test_patterns)

envs = get_test_envs()
maxlen = max(len(e) for e in envs)
tp_0 = test_patterns[0]
test_patterns = [t + ("",) for t in test_patterns]
for env in envs:
    # Test each env twice to confirm that
    # we get the same token each time
    test_patterns.append(tp_0 + (env,))
    test_patterns.append(tp_0 + (env,))

nfailed = 0

local_org = other_tokens.pop("o", None)
base_fields = "csem" if "m" in other_tokens else "cse"
if local_org:
    base_fields += "o"
ofile = join(context.default_prefix, "org_token")
otoken = _random_token()

id_last = False
need_header = True
for aau_state in (True, False):
    os.environ["CONDA_ANACONDA_ANON_USAGE"] = "on" if aau_state else "off"
    anon_flag = "T" if aau_state else "F"
    for param, test_fields, envname in test_patterns:
        org = org2 = None
        if "O" in test_fields:
            org2 = otoken
            with open(ofile, "w") as fp:
                fp.write(otoken)
        elif exists(ofile):
            os.unlink(ofile)
        org = param.split(":", 1)[-1] if ":" in param else ""
        org = (
            ([org] if org else [])
            + ([org2] if org2 else [])
            + ([local_org] if local_org else [])
        )
        other_tokens["o"] = "/".join(sorted(set(org)))
        os.environ["CONDA_ANACONDA_IDENT"] = param
        test_fields = orig_fields = base_fields + test_fields
        test_fields = "".join(dict.fromkeys(test_fields.replace("O", "o")))
        expected = list(test_fields)
        expected.extend(("aau", "aid"))
        # We need the specific channel configuration here so we can
        # experiment with different channel aliases and channel lists
        # in the keymgr packages
        cmd = [
            "proxyspy",
            "--return-code",
            "404",
            "--",
            "conda",
            "install",
            "--override-channels",
            "-c",
            "defaults",
            "fakepackage",
        ]
        if envname:
            cmd.extend(["-n", envname])
        proc = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
        )
        if exists(ofile):
            os.unlink(ofile)
        status, header = verify_user_agent(proc.stdout, expected, envname)
        if need_header:
            need_header = False
            print("|", header)
            print(f"anon    ident     {'envname':{maxlen}}   fields    status")
            print(f"---- ------------ {'-' * maxlen} ---------- ------")
        print(
            f"{anon_flag:4} {param:12} {envname:{maxlen}} {orig_fields:10} {status or 'OK'}"
        )
        if status:
            print("|", header)
        if status:
            nfailed += 1
            if "--fast" in sys.argv:
                sys.exit(1)

if exists(ofile):
    os.unlink(ofile)

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
