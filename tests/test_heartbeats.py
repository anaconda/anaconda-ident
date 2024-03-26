import json
import os
import re
import subprocess
import sys
from os.path import basename, join

from conda.base.context import context
from conda.models.channel import Channel
from anaconda_ident import patch

from test_utils import get_test_envs, verify_user_agent, other_tokens

patch.main()
context.__init__()
fmt, org, _ = patch.client_token_type()
if org:
    other_tokens['o'] = org
    fmt += 'o'
expected = ('aau', 'aid') + tuple(fmt)

os.environ["ANACONDA_IDENT_DEBUG"] = "1"

envs = get_test_envs()
maxlen = max(len(e) for e in envs)
nfailed = 0

print("Testing heartbeat")
print("-----------------")
urls = [u for c in context.channels for u in Channel(c).urls()]
urls.extend(u.rstrip("/") for u in context.channel_alias.urls())
if any('.anaconda.cloud' in u for u in urls):
    hb_url = 'https://repo.anaconda.cloud/'
elif any('.anaconda.com' in u for u in urls):
    hb_url = 'https://repo.anaconda.com/'
elif any('.anaconda.org' in u for u in urls):
    hb_url = 'https://conda.anaconda.org/'
else:
    hb_url = None
print("Expected heartbeat url:", hb_url)
print("Expected user agent tokens:", ','.join(expected))
need_header = True
for hval in ("true", "false"):
    os.environ["CONDA_ANACONDA_HEARTBEAT"] = hval
    for envname in envs:
        # Do each one twice to make sure the user agent string
        # remains correct on repeated attempts
        for stype in ("posix", "posix", "cmd.exe", "cmd.exe", "powershell", "powershell"):
            cmd = ["conda", "shell." + stype, "activate", envname]
            proc = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True,
            )
            header = status = ""
            no_hb_url = "No valid heartbeat channel" in proc.stderr
            hb_urls = set(line.rsplit(' ', 1)[-1]
                          for line in proc.stderr.splitlines()
                          if 'Heartbeat url:' in line)
            status = ""
            if hval == "true":
                if not (no_hb_url or hb_urls):
                    status = "NOT ENABLED"
                elif hb_url and not hb_urls:
                    status = "NO HEARTBEAT URL"
                elif not hb_url and hb_urls:
                    status = "UNEXPECTED URLS: " + ','.join(hb_urls)
                elif hb_url and any(hb_url not in u for u in hb_urls):
                    status = "INCORRECT URLS: " + ','.join(hb_urls)
            elif hval == "false" and (no_hb_url or hb_urls):
                status = "NOT DISABLED"
            if hb_urls and not status:
                status, header = verify_user_agent(proc.stderr, expected, envname, "Full client token")
            if need_header:
                if header:
                    print("|", header)
                print(f"hval  shell      {'envname':{maxlen}} status")
                print(f"----- ---------- {'-' * maxlen} ----------")
                need_header = False
            print(f"{hval:5} {stype:10} {envname:{maxlen}} {status or 'OK'}")
            if status:
                print("|", " ".join(cmd))
                for line in proc.stderr.splitlines():
                    if line.strip():
                        print("!", line)
                if header:
                    print("|", header)
                nfailed += 1

print("FAILURES:", nfailed)
sys.exit(nfailed)
