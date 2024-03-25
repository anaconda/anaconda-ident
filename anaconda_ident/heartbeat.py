import argparse
import sys
from threading import Thread

from anaconda_anon_usage import utils
from conda.base.context import context
from conda.gateways.connection.session import CondaSession
from conda.models.channel import Channel

VERBOSE = True
STANDALONE = True
CLD_REPO = "https://repo.anaconda.cloud/"
ORG_REPO = "https://conda.anaconda.org/"
COM_REPO = "https://repo.anaconda.com/pkgs/"


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
        _print("Status code (expect 404): %s", response.status_code)
    except Exception as exc:
        if type(exc).__name__ != "ConnectionError":
            _print("Heartbeat error: %s", exc, error=True)


def _attempt_heartbeat(channel=None, name=None, wait=False):
    line = "------------------------"
    _print(line, standalone=True)
    _print("anaconda-ident heartbeat", standalone=True)
    _print(line, standalone=True)

    if not hasattr(context, "_aid_initialized"):
        from anaconda_ident import patch

        patch.main()

    if channel and "/" in channel:
        url = channel.rstrip() + "/noarch/activate"
    else:
        urls = [u for c in context.channels for u in Channel(c).urls()]
        urls.extend(u.rstrip("/") for u in context.channel_alias.urls())
        if any(u.startswith(CLD_REPO) for u in urls):
            base = CLD_REPO
        elif any(u.startswith(COM_REPO) for u in urls):
            base = COM_REPO
        elif any(u.startswith(ORG_REPO) for u in urls):
            base = ORG_REPO
        else:
            _print("no valid heartbeat channel")
            _print(line, standalone=True)
            return
        channel = channel or "main"
        url = f"{base}{channel}/noarch/activate"

    _print("Heartbeat url: %s", url)
    _print("User agent: %s", context.user_agent)
    session = CondaSession()
    t = Thread(target=_ping, args=(session, url, wait), daemon=True)
    t.start()
    _print("%saiting for response", "W" if wait else "Not w")
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
        _print("Unexpected error in heartbeat: %s", exc, error=True)


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
