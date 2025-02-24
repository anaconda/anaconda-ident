import json
import os
import re
import subprocess
import sys

from anaconda_anon_usage import __version__ as aau_version
from anaconda_anon_usage import tokens

from anaconda_ident import __version__ as aid_version

ALL_FIELDS = {"aau", "aid", "c", "s", "e", "u", "h", "n", "o", "m", "U", "H", "N"}


def get_test_envs():
    proc = subprocess.run(
        ["conda", "info", "--envs", "--json"],
        check=False,
        capture_output=True,
        text=True,
    )
    pfx_s = os.path.join(sys.prefix, "envs") + os.sep
    pdata = json.loads(proc.stdout)
    # Limit ourselves to two non-base environments to speed up local testing
    envs = [sys.prefix] + [e for e in pdata["envs"] if e.startswith(pfx_s)][:2]
    envs = {("base" if e == sys.prefix else os.path.basename(e)): e for e in envs}
    return envs


other_tokens = {"aau": aau_version, "aid": aid_version}
mtoken = tokens.machine_token()
if mtoken:
    other_tokens["m"] = mtoken
otoken = tokens.organization_token()
if otoken:
    other_tokens["o"] = otoken
all_session_tokens = set()
all_environments = set()


def verify_user_agent(output, expected, envname=None, marker=None):
    # Unfortunately conda has evolved how it logs request headers
    # So this regular expression attempts to match multiple forms
    # > User-Agent: conda/...
    # .... {'User-Agent': 'conda/...', ...}
    other_tokens["n"] = envname if envname else "base"

    match = re.search(r"^.*User-Agent: (.+)$", output, re.MULTILINE)
    user_agent = match.groups()[0] if match else ""
    new_values = [t.split("/", 1) for t in user_agent.split(" ") if "/" in t]
    new_values = {k: v for k, v in new_values if k in ALL_FIELDS}
    header = " ".join(f"{k}/{v}" for k, v in new_values.items())

    # Confirm that all of the expected tokens are present
    status = []
    missing = set(expected) - set(new_values)
    extras = set(new_values) - set(expected)
    if missing:
        status.append(f"{','.join(missing)} MISSING")
    if extras:
        status.append(f"{','.join(extras)} EXTRA")
    modified = []
    duplicated = []
    for k, v in new_values.items():
        if k == "o":
            v = "/".join(sorted(set(v.split("/"))))
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
    return ", ".join(status), header
