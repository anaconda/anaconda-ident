import argparse
import sys
from threading import Thread

from anaconda_anon_usage import utils
from conda.base.context import context
from conda.gateways import anaconda_client
from conda.gateways.connection.session import CondaSession
from conda.models.channel import Channel

VERBOSE = True
STANDALONE = True
PRO_REPO = "https://repo.anaconda.cloud"
DEF_REPO = "https://conda.anaconda.org"


def _print(msg, *args, standalone=False, error=False):
    global VERBOSE
    global STANDALONE
    if not (VERBOSE or utils.DEBUG or error):
        return
    if standalone and not STANDALONE:
        return
    # It is very important that these messages are printed to stderr
    # when called from within the activate script. Otherwise they
    # will insert themselves into the activation command set
    ofile = sys.stdout if STANDALONE and not error else sys.stderr
    print(msg % args, file=ofile)


def _ping(session, url, wait):
    try:
        response = session.head(url, proxies=session.proxies)
        _print("status code (expect 404): %s", response.status_code)
    except Exception as exc:
        if type(exc).__name__ != "ConnectionError":
            _print("Heartbeat error: %s", exc, error=True)


def _attempt_heartbeat(channel=None, name=None, wait=False):
    line = "------------------------"
    _print(line, standalone=True)
    _print("anaconda-ident heartbeat", standalone=True)
    _print(line, standalone=True)

    if not getattr(context, "_aau_initialized", False):
        if not hasattr(context, "_aau_initialized"):
            from anaconda_anon_usage import patch

            patch.main()
        context.__init__()

    base = None
    repo_tokens = context.repo_tokens
    if not repo_tokens:
        repo_tokens = anaconda_client.read_binstar_tokens()
    repo_tokens = {k.rstrip("/") for k in repo_tokens}
    if PRO_REPO in repo_tokens:
        base = PRO_REPO
    elif DEF_REPO in repo_tokens:
        base = DEF_REPO
    elif repo_tokens:
        base = next(iter(repo_tokens)).rstrip("/")
    else:
        channels = [u for c in context.channels for u in Channel(c).urls()]
        if not channels:
            _print("no valid heartbeat channel")
            _print(line, standalone=True)
            return
        base = sorted(channels, key=lambda x: x.count("/"))[0].rsplit("/", 2)[0]
    url = f"{base}/{channel or 'main'}/noarch/{name or 'activate'}"

    _print("heartbeat url: %s", url)
    session = CondaSession()
    t = Thread(target=_ping, args=(session, url, wait), daemon=True)
    t.start()
    _print("%swaiting for response", "" if wait else "not ")
    t.join(timeout=None if wait else 0.1)

    _print(line, standalone=True)


def attempt_heartbeat(
    channel=None, name=None, verbose=True, standalone=True, wait=False
):
    global VERBOSE
    global STANDALONE
    try:
        VERBOSE = verbose
        STANDALONE = standalone
        _attempt_heartbeat(channel, name, wait)
    except Exception as exc:
        _print("unexpected error in heartbeat: %s", exc, error=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--wait", action="store_true")
    p.add_argument("--channel", default=None)
    p.add_argument("--name", default=None)
    args = p.parse_args()
    attempt_heartbeat(args.channel, args.name, args.verbose, args.verbose, args.wait)


if __name__ == "__main__":
    main()
