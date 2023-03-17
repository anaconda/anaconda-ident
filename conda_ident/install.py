import sysconfig
import traceback
import argparse
import sys
import os

from os.path import basename, dirname, exists, join


def parse_argv():
    p = argparse.ArgumentParser(description="conda-ident installer")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--enable", action="store_true", help="Enable conda_ident operation")
    g.add_argument(
        "--disable", action="store_true", help="Disable conda_ident operation"
    )
    g.add_argument(
        "--clean",
        action="store_true",
        help="Disable conda_ident operation and remove configuration data.",
    )
    p.add_argument(
        "--quiet",
        dest="verbose",
        action="store_false",
        default=True,
        help="Silent mode.",
    )
    p.add_argument(
        "--config", default=None, help="Install a hardcoded configuration value."
    )
    p.add_argument(
        "--default-channel",
        action="append",
        help="Specify a default channel. "
        "Multiple channels may be supplied as a comma-separated list or by supplying "
        "multiple --default-channel options.",
    )
    p.add_argument(
        "--channel-alias",
        default=None,
        help="Specify a channel_alias. "
        "This is recomended only if all channels are sourced from the same repository; "
        "e.g., an instance of Anaconda Server.",
    )
    p.add_argument(
        "--token",
        default=None,
        help="Store a token for conda authentication. To use this, a full channel "
        "URL is required. This will either be determined from the first full URL "
        "in the default_channels list; or if not present there, from channel_alias.",
    )
    g.add_argument("--verify", action="store_true", help=argparse.SUPPRESS)
    p.add_argument(
        "--ignore-missing", action="store_true", default=None, help=argparse.SUPPRESS
    )
    args = p.parse_args()
    if (args.clean or args.verify) and sum(
        v is not None for v in vars(args).values()
    ) != 5:
        what = "clean" if args.clean else "verify"
        print("WARNING: --%s overrides other operations" % what)
    return args


success = True


def error(what, fatal=False):
    global success
    print("ERROR:", what)
    print("-----")
    traceback.print_exc()
    print("-----")
    if fatal:
        print("cannot proceed; exiting.")
        sys.exit(-1)
    success = False


PATCH_TEXT = """
try:
    import conda_ident.patch
except Exception as exc:
    pass
"""


def manage_patch(args):
    global PATCH_TEXT

    sp_dir = sysconfig.get_paths()["purelib"]
    pfile = join(sp_dir, "conda", "base", "context.py")
    pline = PATCH_TEXT.encode("ascii")
    nline = len(pline)

    def _read(pfile):
        try:
            with open(pfile, "rb") as fp:
                text = fp.read()
        except Exception:
            if args and not args.ignore_missing:
                error("conda_ident installation failed", fatal=True)
            text = b""
        return text, b"conda_ident" in text[-nline:]

    text, is_present = _read(pfile)
    if args.verbose:
        print("patch target:", pfile)
        print("current status:", "ENABLED" if is_present else "DISABLED")

    enable = args.enable or args.verify
    disable = args.disable or args.clean

    need_change = enable and not is_present or disable and is_present
    if not need_change:
        if args.verbose and (enable or disable):
            print("no patchwork needed")
        return
    elif text is None:
        if args.verbose:
            print("nothing to patch")
        return

    if args.verbose:
        print(("reverting" if is_present else "applying"), "patch...")
    try:
        wineol = b"\r\n" in text
        if wineol != (b"\r\n" in pline):
            args = (b"\n", b"\r\n") if wineol else (b"\r\n", b"\n")
            pline = pline.replace(*args)
        if is_present:
            text = text.replace(pline, b"")
        # We do not append to the original file because this is
        # likely a hard link into the package cache, so doing so
        # would lead to conda flagging package corruption.
        with open(pfile + ".new", "wb") as fp:
            fp.write(text)
            if not is_present:
                fp.write(pline)
        pfile_orig = pfile + ".orig"
        if exists(pfile_orig):
            os.unlink(pfile_orig)
        os.rename(pfile, pfile_orig)
        os.rename(pfile + ".new", pfile)
        is_present = not is_present
    except Exception:
        error("%s failed" % ("deactivation" if is_present else "activation"))

    text, is_present = _read(pfile)
    if args.verbose:
        print("new status:", "ENABLED" if is_present else "DISABLED")


__yaml = None


def _yaml():
    global __yaml
    if __yaml is None:
        try:
            import ruamel.yaml as yaml
        except Exception:
            try:
                import ruamel_yaml as yaml
            except Exception:
                try:
                    import yaml
                except Exception:
                    error("failed to load yaml library")
                    return None
        __yaml = yaml
    return __yaml


def read_condarc(args, fname):
    if not exists(fname) or args.clean:
        if args.verbose and not args.clean:
            print("no conda_ident condarc to read")
        return {}
    try:
        if args.verbose:
            print("reading conda_ident condarc...")
        with open(fname, "r") as fp:
            return _yaml().safe_load(fp)
    except Exception:
        error("config load failed")


def _print_config(what, args, config):
    if args.verbose:
        value = config.get("client_token")
        print("%s config: %s" % (what, value or "<default>"))


def _print_default_channels(what, args, config):
    if args.verbose:
        value = config.get("default_channels")
        if value is None:
            value = "<none>"
        elif not value:
            value = "[]"
        else:
            value = "\n - " + "\n - ".join(value)
        print("%s default_channels: %s" % (what, value))


def _print_channel_alias(what, args, config):
    if args.verbose:
        value = config.get("channel_alias")
        print("%s channel_alias: %s" % (what, value or "<none>"))


def _print_tokens(what, args, config):
    if args.verbose:
        tokens = config.get("binstar_tokens")
        if tokens:
            print("%s repo tokens:" % what)
            for k, v in tokens.items():
                print(" - %s: %s..." % (k, v[:6]))
        else:
            print("%s repo tokens: <none>" % what)


def _set_or_delete(d, k, v):
    if v:
        d[k] = v
    elif k in d:
        del d[k]


def manage_condarc(args, condarc):
    if args.clean:
        return {}
    condarc = condarc.copy()
    # config string
    _print_config("current", args, condarc)
    if args.config is not None:
        _set_or_delete(condarc, "client_token", args.config)
        _print_config("new", args, condarc)
    # default_channels
    _print_default_channels("current", args, condarc)
    if args.default_channel:
        nchan = []
        for c1 in args.default_channel:
            for c2 in c1.split(","):
                if c2.strip():
                    nchan.append(c2.strip().rstrip("/"))
        _set_or_delete(condarc, "default_channels", nchan)
        _print_default_channels("new", args, condarc)
    # channel alias
    _print_channel_alias("current", args, condarc)
    if args.channel_alias is not None:
        _set_or_delete(condarc, "channel_alias", args.channel_alias)
        _print_channel_alias("new", args, condarc)
    # tokens
    _print_tokens("current", args, condarc)
    if args.token is not None:
        tokens = {}
        if args.token.strip():
            defchan = condarc.get("default_channels", []) + [
                condarc.get("channel_alias", "")
            ]
            defchan = [c for c in defchan if "/" in c]
            if defchan:
                defchan = "/".join(defchan[0].strip().split("/", 3)[:3]) + "/"
                tokens[defchan] = args.token.strip()
        _set_or_delete(condarc, "binstar_tokens", tokens)
        _print_tokens("new", args, condarc)
    _set_or_delete(condarc, "add_anaconda_token", bool(condarc.get("binstar_tokens")))
    return condarc


def write_condarc(args, fname, condarc):
    if not condarc:
        if exists(fname):
            if args.verbose:
                print("removing conda_ident condarc...")
            try:
                os.unlink(fname)
            except Exception:
                error("condarc removal failed")
        return
    if args.verbose:
        what = "updating" if exists(fname) else "creating"
        print("%s conda_ident condarc..." % what)
    try:
        os.makedirs(dirname(fname), exist_ok=True)
        with open(fname, "w") as fp:
            _yaml().dump(condarc, fp)
    except Exception:
        error("condarc update failed")


def main():
    global success
    args = parse_argv()
    if args.verbose:
        pkg_name = basename(dirname(__file__))
        msg = pkg_name + " installer"
        print(msg)
        msg = "-" * len(msg)
        print(msg)
    manage_patch(args)
    if not args.verify:
        fname = join(sys.prefix, "etc", "conda_ident.yml")
        print("config file:", fname)
        condarc = read_condarc(args, fname)
        if condarc is not None:
            newcondarc = manage_condarc(args, condarc)
            if condarc != newcondarc:
                write_condarc(args, fname, newcondarc)
    if args.verbose:
        print(msg)
    return 0 if success else -1


if __name__ == "__main__":
    sys.exit(main())
