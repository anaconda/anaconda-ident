import os
import sys
import subprocess

from anaconda_ident import __version__
from conda.base.context import context

context.__init__()

os.environ["ANACONDA_IDENT_DEBUG"] = "1"

print("Environment variables:")
print("-----")
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

# In theory, test_fields = _client_token_formats[param]
# I'm hardcoding them here so the test doesn't depend on that
# part of the code, with the exception of "baked" test below.
test_patterns = (("default", "cse"),)
flags = ("", "--disable", "--enable")

nfailed = 0
saved_values = {}
all_session_tokens = set()
max_param = max(max(len(x) for x, _ in test_patterns), len("config"))
max_field = max(max(len(x) for _, x in test_patterns), len("fields"))
for flag in flags:
    if flag:
        print("")
        print("----")
        p = subprocess.run(
            ["python", "-m", "anaconda_ident.install", flag], capture_output=True
        )
        print(p.stdout.decode("utf-8"))
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
        test_fields = "i" + test_fields
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
        if "ident/" in user_agent:
            header = user_agent[user_agent.find("ident/") :]
        else:
            header = ""
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
            if "i" in new_values:
                failed = failed or new_values["i"] != f"ident/{__version__}"
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
        if failed and "--fast" in sys.argv:
            sys.exit(1)


print("FAILURES:", nfailed)
sys.exit(nfailed)
