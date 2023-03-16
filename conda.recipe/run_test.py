import os
import sys
import subprocess

from conda_ident import patch
from ruamel.yaml import safe_load


print("Environment variables:")
print("-----")
print("CONFIG_STRING:", os.environ.get("CONFIG_STRING") or "")
print("DEFAULT_CHANNELS:", os.environ.get("DEFAULT_CHANNELS") or "")
print("CHANNEL_ALIAS:", os.environ.get("CHANNEL_ALIAS") or "")
print("REPO_TOKEN:", os.environ.get("REPO_TOKEN") or "")
print("-----")
subprocess.run(["python", "-m", "conda_ident.install"])
print("-----")

# Verify baked configurations, if any
success = True
config_env = os.environ.get("CONFIG_STRING") or ""
config_baked = patch.get_baked_token_config()
if not config_env and config_baked is not None:
    print("Unexpected baked configuration:", config_baked)
    success = False
elif config_env and config_baked != config_env:
    print(
        "Baked config mismatch:\n - expected: %s\n - found: %s"
        % (config_env, config_baked)
    )
    success = False
elif config_env:
    print("Running with baked configuration:", config_env)

condarc = os.path.join(sys.prefix, ".condarc")
if os.path.exists(condarc):
    with open(condarc, "rb") as fp:
        condarc = safe_load(fp)
else:
    condarc = {}

defchan_baked = condarc.get("default_channels") or []
defchan_env_s = os.environ.get("DEFAULT_CHANNELS") or ""
defchan_env = [c.rstrip("/") for c in defchan_env_s.split(",")] if defchan_env_s else []
if not defchan_env_s and defchan_baked:
    print("Unexpected baked default channels:", defchan_baked)
    success = False
elif defchan_env_s and defchan_env != defchan_baked:
    print(
        "Baked default channels mismatch:\n - expected: %s\n - found: %s"
        % (defchan_env, defchan_baked)
    )
    success = False
elif defchan_env:
    print("Baked default channels:", defchan_env)

calias_baked = condarc.get("channel_alias")
calias_env = os.environ.get("CHANNEL_ALIAS") or ""
if not calias_env and calias_baked is not None:
    print("Unexpected baked channel alias:", calias_baked)
    success = False
elif calias_env and calias_env != calias_baked:
    print(
        "Baked channel alias mismatch:\n - expected: %s\n - found: %s"
        % (calias_env, calias_baked)
    )
    success = False
elif calias_env:
    print("Baked channel alias:", calias_env)

# In a "baked" configuration, the client token config is
# hardcoded into the package itself
token_baked = patch.get_baked_binstar_tokens()
token_env = os.environ.get("REPO_TOKEN") or ""
if token_env:
    token_chan = calias_env or defchan_env[0]
    token_chan = "/".join(token_chan.split("/", 3)[:3]) + "/"
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
    ("none", ""),
    ("default", "cse"),
    ("username", "cseu"),
    ("hostname", "cseh"),
    ("environment", "csen"),
    ("userenv", "cseun"),
    ("userhost", "cseuh"),
    ("hostenv", "csehn"),
    ("full", "cseuhn"),
    ("default:org1", "cseo"),
    ("full:org2", "cseuhno"),
    (":org3", "cseo"),
    ("none:org4", "o"),
    ("c", "c"),
    ("s", "s"),
    ("u", "u"),
    ("h", "h"),
    ("e", "e"),
    ("n", "n"),
    ("o:org4", "o"),
    ("o", ""),
)
flags = ("", "--disable", "--enable")

test_org = None
if config_env:
    fmt = config_baked.split(":", 1)[0]
    fmt = patch._client_token_formats.get(fmt, fmt)
    if "o" not in fmt and ":" in config_baked:
        fmt += "o"
    test_patterns = [(config_baked, fmt)]
    flags = ("--enable", "--disable", "--enable")
    print("test_patterns:", test_patterns)

nfailed = 0
saved_values = {}
all_session_tokens = set()
max_param = max(max(len(x) for x, _ in test_patterns), len("config"))
max_field = max(max(len(x) for _, x in test_patterns), len("fields"))
for flag in flags:
    if flag:
        print("")
        print("----")
        subprocess.run(["python", "-m", "conda_ident.install", flag])
        print("----")
        print("")
    is_enabled = flag != "--disable"
    print(
        "{:{w1}} {:{w2}} ?? token values".format(
            "config", "fields", w1=max_param, w2=max_field
        )
    )
    print("{} {} -- ----------".format("-" * max_param, "-" * max_field))
    for param, test_fields in test_patterns:
        print(
            "{:{w1}} {:{w2}} ".format(param, test_fields, w1=max_param, w2=max_field),
            end="",
        )
        os.environ["CONDA_CLIENT_TOKEN"] = param
        proc = subprocess.run(
            ["conda", "search", "-vvv", "--override-channels", "-c", "fakechannel"],
            check=False,
            capture_output=True,
            text=True,
        )
        user_agent = [v for v in proc.stderr.splitlines() if "User-Agent" in v]
        header = [v for v in proc.stderr.splitlines() if "X-Conda-Ident" in v]
        user_agent = user_agent[0].split(":", 1)[-1].strip() if user_agent else ""
        header = header[0].split(": ", 1)[-1].strip() if header else ""
        assert user_agent.endswith(header), (user_agent, header)
        if is_enabled:
            new_values = {token[0]: token for token in header.split(" ") if token}
            # Confirm that all of the expected tokens are present
            failed = set(new_values) != set(test_fields)
            # Confirm that if the org token, if present, matches the provided value
            if not failed and "o" in new_values:
                failed = new_values["o"][2:] != param.rsplit(":", 1)[-1]
            # Confirm that the session token, if present, is unique
            if "s" in new_values:
                failed = failed or new_values["s"] in all_session_tokens
                all_session_tokens.add(new_values["s"])
            # Confirm that any values besides session and org do not change from run to run
            if not failed:
                failed = any(
                    v != saved_values.setdefault(k, v)
                    for k, v in new_values.items()
                    if k not in "so"
                )
        else:
            failed = len(header) > 0
        print("XX" if failed else "OK", header)
        nfailed += failed


print("FAILURES:", nfailed)
sys.exit(nfailed)
