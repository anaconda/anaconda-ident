import os
import sys
import subprocess

from conda_ident import patch


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


# In a "baked" configuration, the client token config is
# hardcoded into the package itself
baked_tokens = patch.get_baked_binstar_tokens()
baked_defchan = patch.get_baked_default_channels()
repo_url_env = os.environ.get("REPO_URL") or ''
repo_token_env = os.environ.get("REPO_TOKEN") or ''
defchan = 'default_channels: ["%s/"]' % repo_url_env.rstrip("/")
token_dict = {repo_url_env: repo_token_env}

success = True
client_token_env = os.environ.get("CLIENT_TOKEN") or ''
baked_config = patch.get_baked_token_config()
if not client_token_env and baked_config is not None:
    print("Unexpected baked configuration:", baked_config)
    success = False
elif client_token_env and baked_config != client_token_env:
    print("Baked config mismatch:\n - expected: %s\n - found: %s" % (client_token_env, baked_config))
    success = False
elif client_token_env:
    print("Running with baked configuration:", baked_config)

if not repo_url_env and defchan:
    print("Unexpected baked default channels:", baked_defchan)
    success = False
elif repo_url_env and baked_defchan != defchan:
    print("Baked default channels mismatch:\n - expected: %s\n - found: %s" % (defchan, baked_defchan))
    success = False
elif repo_url_env:
    print("Default channel set:", baked_defchan)

if not (repo_url_env and repo_token_env) and baked_tokens:
    print("Unexpected baked token set:", baked_tokens)
    success = False
elif repo_url_env and repo_token_env and baked_tokens != token_dict:
    print("Baked token mismatch:\n - expected: %s\n - found: %s" % (token_dict, baked_tokens))
    success = False
elif repo_url_env and repo_token_env:
    print("Baked token set:", repo_token_env)

if not success:
    sys.exit(-1)

test_org = None
if client_token_env:
    fmt = baked_config.split(":", 1)[0]
    fmt = patch._client_token_formats.get(fmt, fmt)
    if 'o' not in fmt and ':' in baked_config:
        fmt += 'o'
    test_patterns = [(baked_config, fmt)]
    flags = ("--enable", "--disable", "--enable")
    print("test_patterns:", test_patterns)

nfailed = 0
saved_values = {}
all_session_tokens = set()
max_param = max(max(len(x) for x, _ in test_patterns), len("client_token"))
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
            "client_token", "fields", w1=max_param, w2=max_field
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
