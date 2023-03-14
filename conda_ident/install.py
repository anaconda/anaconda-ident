import sysconfig
import traceback
import argparse
import sys
import os

from urllib.parse import quote_plus, unquote_plus
from os.path import basename, dirname, exists, isdir, join


p = argparse.ArgumentParser(description="conda-ident installer")
p.add_argument("--status", action="store_true", default=None)
p.add_argument("--enable", action="store_true", default=None)
p.add_argument("--disable", action="store_true", default=None)
p.add_argument("--client-token", default=None)
p.add_argument("--default-channel", default=None)
p.add_argument("--set-condarc", action="store_true", default=None)
p.add_argument("--repo-token", default=None)
p.add_argument("--quiet", action="store_true", default=None)
p.add_argument("--ignore-missing", action="store_true", default=None)
args = p.parse_args()
if args.enable and args.disable:
    p.error("Cannot supply both --enable and --disable\n")
if args.set_condarc and args.default_channel is None:
    p.error("--set-condarc cannot be used without --default-channel\n")
if args.repo_token and args.default_channel is None:
    p.error("--repo-token cannot be used without --default-channel\n")
if args.status and args.quiet:
    p.error("Cannot supply both --status and --quiet\n")
enable = args.enable or not any(v is not None for v in vars(args).values())


local_dir = dirname(__file__)
pkg_name = basename(local_dir)
if not args.quiet:
    msg = pkg_name + " installer"
    print(msg)
    msg = "-" * len(msg)
    print(msg)


success = True


def error(what, fatal=False):
    global success
    print("ERROR:", what)
    print("-----")
    traceback.print_exc()
    print("-----")
    if fatal:
        print("Cannot proceed; exiting.")
        print(msg)
        sys.exit(-1)
    success = False


pline = """
try:
    import conda_ident.patch
except Exception:
    pass
""".encode(
    "ascii"
)


sp_dir = sysconfig.get_paths()["purelib"]
pkg_dir = join(sp_dir, pkg_name)
if not isdir(pkg_dir):
    pkg_dir = local_dir
if not args.quiet:
    print("Location:", pkg_dir)


pfile = join(sp_dir, "conda", "base", "context.py")
try:
    with open(pfile, "rb") as fp:
        text = fp.read()
    is_present = b"conda_ident" in text[-len(pline) :]
    need_change = args.enable and not is_present or args.disable and is_present
except Exception:
    if not args.ignore_missing:
        error("conda_ident installation failed", fatal=True)
    is_present = need_change = False


if need_change:
    if not args.quiet:
        print(("Disabling" if is_present else "Enabling"), "conda_ident...")
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
        error("activation failed")
elif not args.quiet:
    print("Status:", "enabled" if is_present else "disabled")


tfile = join(pkg_dir, "client_token")
tvalue = None
if args.client_token:
    try:
        with open(tfile, "w") as fp:
            fp.write(args.client_token)
        tvalue = args.client_token
    except Exception:
        error("client_token setting failed")
elif exists(tfile):
    try:
        with open(tfile, "r") as fp:
            tvalue = fp.read().strip()
    except Exception:
        error("client_token reading failed")
if not args.quiet:
    print("Client token:", tvalue or "<none>")

defchan = (args.default_channel or "").rstrip("/")
if args.set_condarc and defchan:
    try:
        tfile = join(sys.prefix, ".condarc")
        print("Creating:", tfile)
        with open(tfile, "w") as fp:
            fp.write('default_channels: ["%s"]\n' % defchan)
        if not args.quiet:
            print("default_channels set:", defchan)
    except Exception:
        error("condarc setting failed")

dname = join(pkg_dir, "tokens")
if args.repo_token and defchan:
    fname = quote_plus(defchan + "/") + ".token"
    fpath = join(dname, fname)
    try:
        os.makedirs(dname, exist_ok=True)
        with open(fpath, "w") as fp:
            fp.write(args.repo_token)
        if not args.quiet:
            print("repo_token set for:", defchan)
    except Exception:
        error("repo_token setting failed")
elif isdir(dname):
    if not args.quiet:
        print("Repo token directory: found")
        for entry in os.scandir(dname):
            if entry.name.endswith(".token"):
                print(" -", unquote_plus(entry.name[:-6]))
elif not args.quiet:
    print("Repo token directory: NOT found")

if not args.quiet:
    print(msg)
