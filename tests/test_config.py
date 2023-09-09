import os
import subprocess
import sys

from anaconda_anon_usage import __version__ as aau_version
from conda.base.context import context
from conda.models.channel import Channel

from anaconda_ident import __version__ as aid_version
from anaconda_ident import patch as patch

context.__init__()


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


os.environ["ANACONDA_IDENT_DEBUG"] = "1"
os.environ["ANACONDA_ANON_USAGE_DEBUG"] = "1"

print("Environment variables:")
print("-----")
print("CONFIG_STRING:", os.environ.get("CONFIG_STRING") or "")
print("DEFAULT_CHANNELS:", os.environ.get("DEFAULT_CHANNELS") or "")
print("CHANNEL_ALIAS:", os.environ.get("CHANNEL_ALIAS") or "")
print("REPO_TOKEN:", os.environ.get("REPO_TOKEN") or "")
print("SKIP_INSTALL:", os.environ.get("SKIP_INSTALL") or False)
print("ANACONDA_IDENT_DEBUG:", os.environ.get("ANACONDA_IDENT_DEBUG") or "")
print("-----")
p = subprocess.run(
    ["python", "-m", "anaconda_ident.install", "--status"], capture_output=True
)
print(p.stdout.decode("utf-8").strip())
print("-----")
p = subprocess.run(["python", "-m", "conda", "info"], capture_output=True)
print(p.stdout.decode("utf-8").strip())
print("-----")

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
    ("none", ""),
    ("default", ""),
    ("username", "u"),
    ("hostname", "h"),
    ("environment", "n"),
    ("userenv", "un"),
    ("userhost", "uh"),
    ("hostenv", "hn"),
    ("full", "uhn"),
    ("default:org1", "o"),
    ("full:org2", "uhno"),
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

nfailed = 0
saved_values = {"aau": aau_version, "aid": aid_version}
all_session_tokens = set()
max_anon = len("anon")
max_param = max(max(len(x) for x, _ in test_patterns), len("ident"))
max_field = max(max(len(x) for _, x in test_patterns), len("fields"))

id_last = False
need_header = True
for aau_state, id_state in states:
    os.environ["CONDA_ANACONDA_ANON_USAGE"] = "on" if aau_state else "off"
    if id_state != id_last:
        id_last = id_state
        flag = "--enable" if id_state else "--disable"
        print("")
        p = subprocess.run(
            ["python", "-m", "anaconda_ident.install", flag], capture_output=True
        )
        print(p.stdout.decode("utf-8"))
        need_header = True
    if need_header:
        need_header = False
        print("")
        print(
            "{:{w0}} {:{w1}} {:{w2}} ?? token values".format(
                "anon", "ident", "fields", w0=max_anon, w1=max_param, w2=max_field
            )
        )
        print(
            "{} {} {} -- ----------".format(
                "-" * max_anon, "-" * max_param, "-" * max_field
            )
        )
    anon_flag = "T" if aau_state else "F"
    for param, test_fields in test_patterns:
        saved_values["o"] = param.split(":", 1)[-1] if ":" in param else ""
        os.environ["CONDA_ANACONDA_IDENT"] = param
        if id_state:
            test_fields = "cse" + test_fields
        else:
            test_fields = "cse" if aau_state else ""
        expected = list(test_fields)
        expected.append("aau")
        if id_state:
            expected.append("aid")
        print(
            "{:{w0}} {:{w1}} {:{w2}} ".format(
                anon_flag, param, test_fields, w0=max_anon, w1=max_param, w2=max_field
            ),
            end="",
        )
        # Make sure to leave override-channels and the full channel URL in here.
        # This allows this command to run fully no matter what we do to channel_alias
        # and default_channels
        proc = subprocess.run(
            [
                "conda",
                "search",
                "-vvv",
                "--override-channels",
                "-c",
                "https://repo.anaconda.com/pkgs/fakechannel",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        user_agent = [v for v in proc.stderr.splitlines() if "User-Agent" in v]
        user_agent = user_agent[0].split(":", 1)[-1].strip() if user_agent else ""
        new_values = [token.split("/", 1) for token in user_agent.split(" ")]
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
        conflicts = []
        for k, v in new_values.items():
            if k == "s":
                if new_values["s"] in all_session_tokens:
                    status.append("SESSION")
                all_session_tokens.add(new_values["s"])
            elif saved_values.setdefault(k, v) != v:
                conflicts.append(k)
        if conflicts:
            status.append(f"{','.join(conflicts)} CONFLICT")
        status = ", ".join(status)
        print("XX" if status else "OK", header, status)
        if status:
            nfailed += 1
            if "--fast" in sys.argv:
                sys.exit(1)


print("FAILURES:", nfailed)
sys.exit(nfailed)
