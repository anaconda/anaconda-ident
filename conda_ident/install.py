import sysconfig
import traceback
import argparse
import shutil
import sys
import os

from urllib.parse import quote_plus, unquote_plus
from os.path import basename, dirname, exists, isdir, join


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
        help="Specify a default channel for use with --set-condarc and/or --token. "
        "Multiple channels may be supplied as a comma-separated list or by supplying "
        "multiple --default-channel options.",
    )
    p.add_argument(
        "--channel-alias",
        default=None,
        help="Specify a channel_alias to use with --set-condarc and/or --token. "
        "This is recomended only if all channels are sourced from the same repository; "
        "e.g., an instance of Anaconda Server.",
    )
    p.add_argument(
        "--set-condarc",
        action="store_true",
        default=None,
        help="Append a default_channels configuration to $CONDA_PREFIX/.condarc. "
        "To use this, at least one --default-channel must be supplied.",
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
    if args.set_condarc and not args.default_channel:
        print("WARNING: --set-condarc is inoperative without --default-channel\n")
    if args.token and not args.default_channel:
        print("WARNING: --token is inoperative used without --default-channel\n")
    if (args.default_channel or args.channel_alias) and not (
        args.token or args.set_condarc
    ):
        print(
            "WARNING: ---default-channel/--channel-alias should be used with --set-condarc/--token"
        )
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


def manage_data_dir(args, dname):
    if bool(args.clean) == isdir(dname) and (args.clean or args.config or args.token):
        if args.verbose:
            print(("removing" if args.clean else "creating"), "directory...")
        try:
            if args.clean:
                shutil.rmtree(dname)
            else:
                os.makedirs(dname, exist_ok=True)
        except Exception:
            error("directory operation failed")
    return dname if isdir(dname) else None


def manage_config(args, dname):
    if not (args.config or args.verbose):
        return
    tfile = join(dname, "config")
    value = None
    if exists(tfile):
        try:
            with open(tfile, "r") as fp:
                value = fp.read().strip()
        except Exception:
            error("config read failed")
    if args.verbose:
        print("current config:", value if value else "<none>")
    if args.clean or not args.config:
        return
    if args.config == value:
        if args.verbose:
            print("no config change required")
        return
    if args.verbose:
        print("new config:", args.config)
    try:
        with open(tfile, "w") as fp:
            fp.write(args.config)
    except Exception:
        error("config writing failed")


def manage_condarc(args):
    if not (
        args.clean
        or args.set_condarc
        and (any(args.default_channel) or args.channel_alias)
        or args.verbose
    ):
        return

    tfile = join(sys.prefix, ".condarc")
    lstart = "# <<< conda_ident <<<"
    lfinish = "# >>> conda_ident >>>"

    result = extra = []
    if exists(tfile):
        try:
            with open(tfile, "r") as fp:
                result = fp.read().splitlines()
            if lstart in result and lfinish in result:
                n1 = result.index(lstart)
                n2 = result.index(lfinish)
                extra = result[n1 + 1 : n2]
                del result[n1 : n2 + 1]
        except Exception:
            error("reading condarc failed")
            return

    if args.verbose:
        if extra:
            print("current condarc content:")
            print("\n".join("| " + c for c in extra))
        else:
            print("current condarc content: <none>")

    if args.clean:
        newextra = []
    elif args.set_condarc and (any(args.default_channel) or args.channel_alias):
        newextra = ["add_anaconda_token: true"]
        if args.channel_alias:
            newextra.append("channel_alias: " + args.channel_alias)
        newextra.append("default_channels:")
        for c1 in args.default_channel:
            for c2 in c1.split(","):
                newextra.append("  - " + c2.strip().rstrip("/"))
    else:
        return

    if newextra == extra:
        if args.verbose:
            print("no condarc changes required")
        return
    elif args.verbose and newextra:
        print("new condarc content:")
        print("\n".join("| " + c for c in newextra))

    if newextra:
        result.append(lstart)
        result.extend(newextra)
        result.append(lfinish)
    if result:
        if args.verbose:
            what = "modified" if newextra else "cleaned"
            print("writing %s condarc..." % what)
        try:
            with open(tfile, "w") as fp:
                fp.write("\n".join(result) + "\n")
        except Exception:
            error("condarc writing failed")
    elif exists(tfile):
        if args.verbose:
            print("removing condarc...")
        try:
            os.unlink(tfile)
        except Exception:
            error("condarc removal failed")


def manage_token(args, dname):
    do_update = (
        bool(args.default_channel or args.channel_alias and args.token)
        and not args.clean
    )
    if not (do_update or args.verbose):
        return

    tokens = {}
    try:
        if isdir(dname):
            for entry in os.scandir(dname):
                if entry.name.endswith(".token"):
                    url = unquote_plus(entry.name[:-6])
                    with open(entry.path) as f:
                        tokens[url] = f.read().strip()
    except Exception:
        error("token directory read failure")

    if args.verbose:
        if tokens:
            print("current repo tokens:")
            for k, v in tokens.items():
                print(" - %s: %s..." % (k, v[:6]))
        else:
            print("current repo tokens: <none>")

    newtokens = {}
    if args.token and (args.channel_alias or args.default_channel):
        # Prefer full URLs in default_channel over channel_alias
        defchan = []
        for c1 in args.default_channel:
            for c2 in c1.split(","):
                if "/" in c2:
                    defchan.append(c2)
        defchan = defchan[0] if defchan else args.channel_alias
        defchan = "/".join(defchan.strip().split("/", 3)[:3]) + "/"
        newtokens[defchan] = args.token.strip()
    else:
        newtokens = tokens

    if newtokens == tokens:
        if do_update and args.verbose:
            print("no repo token changes required")
        return
    elif args.verbose and newtokens:
        print("new repo tokens:")
        for k, v in newtokens.items():
            print(" - %s: %s..." % (k, v[:6]))

    if args.verbose:
        try:
            print(("updating" if tokens else "creating"), "repo token...")
            for key in set(tokens) | set(newtokens):
                fpath = join(dname, quote_plus(key) + ".token")
                if key in newtokens:
                    with open(fpath, "w") as fp:
                        fp.write(newtokens[key])
                else:
                    os.unlink(fpath)
        except Exception:
            error("repo token writing failed")


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
        dname = join(sys.prefix, "etc", "conda_ident")
        print("config directory:", dname)
        manage_data_dir(args, dname)
        manage_config(args, dname)
        manage_condarc(args)
        manage_token(args, dname)
    if args.verbose:
        print(msg)
    return 0 if success else -1


if __name__ == "__main__":
    sys.exit(main())
