import sysconfig
import argparse
import stat
import sys
import os

from os.path import basename, dirname, exists, join, relpath


def parse_argv():
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group()
    g.add_argument(
        "--enable",
        action="store_true",
        help="Enable anaconda_ident operation. "
        "Without further configuration, this enables randomized telemetry.",
    )
    g.add_argument(
        "--verify",
        action="store_true",
        help="Enable anaconda_ident operation if necessary and exit immediately, "
        "without reading or modifying the current configuration.",
    )
    g.add_argument(
        "--disable",
        action="store_true",
        help="Disable anaconda_ident operation. "
        "The configuration file is left in place, so that full operation can "
        "resume with a call to --enable. To remove the settings as well, use the "
        "--clean option instead.",
    )
    g.add_argument(
        "--status",
        action="store_true",
        help="Print the anaconda_ident patch and configuration status, and make no changes.",
    )
    g.add_argument(
        "--clean",
        action="store_true",
        help="Disable anaconda_ident operation and remove all configuration data. "
        "If you re-enable anaconda_ident, you will need to rebuild the configuration.",
    )
    p.add_argument(
        "--config",
        default=None,
        help="Set the telemetry configuration. "
        "Supply an empty string to revert to the default setting.",
    )
    p.add_argument(
        "--default-channel",
        action="append",
        help="Specify a default channel. "
        "Multiple channels may be supplied as a comma-separated list or by supplying "
        "multiple --default-channel options. Supply an empty string to clear the "
        "default channel list completely.",
    )
    p.add_argument(
        "--channel-alias",
        default=None,
        help="Specify a channel_alias. "
        "This is recomended only if all channels are sourced from the same repository; "
        "e.g., an instance of Anaconda Server. Supply an empty string to clear the "
        "channel alias setting.",
    )
    p.add_argument(
        "--repo-token",
        default=None,
        help="Store a token for conda authentication. To use this, a full channel "
        "URL is required. This will either be determined from the first full URL "
        "in the default_channels list; or if not present there, from channel_alias. "
        "Supply an empty string to clear the token.",
    )
    p.add_argument(
        "--write-token",
        default=None,
        action="store_true",
        help="Write the token to the standard location. This is needed for certain "
        "packages like Anaconda Navigator that do not use conda for authentication. "
        "Existing tokens for the same location are replaced. "
        "This is most useful in an installer post-install script.",
    )
    p.add_argument(
        "--clear-old-token",
        default=None,
        action="store_true",
        help="Clear any saved tokens written to the standard location that would "
        "conflict with the token in the installer. This helps ensure there the "
        "installed environment behaves as expected when replacing an older install. "
        "This is most useful in an installer post-install script.",
    )
    p.add_argument(
        "--quiet",
        dest="verbose",
        action="store_false",
        default=True,
        help="Silent mode; disables all non-error output.",
    )
    p.add_argument(
        "--ignore-missing", action="store_true", default=None, help=argparse.SUPPRESS
    )
    sys.argv[0] = "anaconda-ident"
    args = p.parse_args()
    if (args.clean or args.verify or args.status) and sum(
        v is not None for v in vars(args).values()
    ) != 6:
        what = "clean" if args.clean else ("status" if args.status else "verify")
        print("WARNING: --%s overrides other operations" % what)
    return args, p


success = True


def error(what, fatal=False, warn=False, traceback=True):
    global success
    print("ERROR:", what)
    if traceback:
        print("-----")
        traceback.print_exc()
        print("-----")
    if fatal:
        print("cannot proceed; exiting.")
        sys.exit(-1)
    if not warn:
        success = False


def tryop(op, *args, **kwargs):
    try:
        op(*args, **kwargs)
        return True
    except Exception:
        return False


OLD_PATCH_TEXT = b"""
try:
    import anaconda_ident.patch
except Exception as exc:
    pass
"""

PATCH_TEXT = b"""
# anaconda_ident p2
_old__init__ = context.__init__
def _new_init(*args, **kwargs):
    try:
        import anaconda_ident.patch
    except Exception as exc:
        import os, sys
        print("Error loading anaconda_ident:", exc, file=sys.stderr)
        if os.environ.get('ANACONDA_IDENT_DEBUG'):
            raise
    context.__init__ = _old__init__
    _old__init__(*args, **kwargs)
context.__init__ = _new_init
# anaconda_ident p2
"""

AC_PATCH_TEXT = b"""
# anaconda_ident p3
try:
    import anaconda_ident.patch_ac
except Exception as exc:
    import os, sys
    print("Error loading anaconda_ident:", exc, file=sys.stderr)
    if os.environ.get('ANACONDA_IDENT_DEBUG'):
        raise
# anaconda_ident p3
"""

BS_PATCH_TEXT = b"""
# anaconda_ident p3
try:
    import anaconda_ident.patch_bc
except Exception as exc:
    import os, sys
    print("Error loading anaconda_ident:", exc, file=sys.stderr)
    if os.environ.get('ANACONDA_IDENT_DEBUG'):
        raise
# anaconda_ident p3
"""

__sp_dir = None


def _sp_dir():
    global __sp_dir
    if __sp_dir is None:
        __sp_dir = sysconfig.get_paths()["purelib"]
    return __sp_dir


def _eolmatch(text, ptext):
    wineol = b"\r\n" in text
    if wineol != (b"\r\n" in ptext):
        args = (b"\n", b"\r\n") if wineol else (b"\r\n", b"\n")
        ptext = ptext.replace(*args)
    return ptext


def _read(args, pfile, patch_text):
    if not exists(pfile):
        return None, "NOT PRESENT"
    with open(pfile, "rb") as fp:
        text = fp.read()
    patch_text = _eolmatch(text, patch_text)
    if text.endswith(patch_text):
        status = "ENABLED"
    elif b"anaconda_ident" in text:
        status = "NEEDS UPDATE"
    else:
        status = "DISABLED"
    return text, status


def _strip(text, patch_text, old_patch_text):
    found = False
    patch_text = _eolmatch(text, patch_text)
    if text.endswith(patch_text):
        text = text[: -len(patch_text)]
        found = True
    if old_patch_text:
        old_patch_text = _eolmatch(text, old_patch_text)
        if text.endswith(old_patch_text):
            text = text[: -len(old_patch_text)]
            found = True
    if not found and b"# anaconda_ident " in text:
        text = text[: text.find(b"# anaconda_ident p")]
    return text


def _patch(args, pfile, patch_text, old_patch_text, safety_len):
    verbose = args.verbose or args.status
    if verbose:
        print(f"patch target: ...{relpath(pfile, _sp_dir())}")
    text, status = _read(args, pfile, patch_text)
    if verbose:
        print(f"| status: {status}")
    if status == "NOT PRESENT":
        return
    enable = args.enable or args.verify
    disable = args.disable or args.clean
    if status == "NEEDS UPDATE":
        need_change = True
        status = "reverting" if disable else "updating"
    elif enable:
        need_change = status == "DISABLED"
        status = "applying"
    elif disable:
        need_change = status == "ENABLED"
        status = "reverting"
    else:
        need_change = False
    if not need_change:
        return
    if verbose:
        print(f"| {status} patch...", end="")
    renamed = False
    try:
        text = _strip(text, patch_text, old_patch_text)
        # safety valve
        if len(text) < safety_len:
            print("safety check failed")
            error("! unexpected error, no changes made", fatal=True)
        # We do not append to the original file because this is
        # likely a hard link into the package cache, so doing so
        # would lead to conda flagging package corruption.
        with open(pfile + ".new", "wb") as fp:
            fp.write(text)
            if status != "reverting":
                fp.write(patch_text)
        pfile_orig = pfile + ".orig"
        if exists(pfile_orig):
            os.unlink(pfile_orig)
        os.rename(pfile, pfile_orig)
        renamed = True
        os.rename(pfile + ".new", pfile)
        print("success")
    except Exception as exc:
        print(f"failed: {exc}")
        if renamed:
            os.rename(pfile_orig, pfile)
    text, status = _read(args, pfile, patch_text)
    if verbose:
        print(f"| new status: {status}")


def _patch_conda_context(args, verbose):
    global OLD_PATCH_TEXT
    global PATCH_TEXT
    pfile = join(_sp_dir(), "conda", "base", "context.py")
    _patch(args, pfile, PATCH_TEXT, OLD_PATCH_TEXT, 70000)


def _patch_anaconda_client(args, verbose):
    global AC_PATCH_TEXT
    afile = join(_sp_dir(), "conda", "gateways", "anaconda_client.py")
    _patch(args, afile, AC_PATCH_TEXT, None, 2000)


def _patch_binstar_client(args, verbose):
    global BS_PATCH_TEXT
    bfile = join(_sp_dir(), "binstar_client", "utils", "config.py")
    _patch(args, bfile, BS_PATCH_TEXT, None, 9000)


def manage_patch(args):
    verbose = args.verbose or args.status
    if verbose:
        print("conda prefix:", sys.prefix)
    _patch_conda_context(args, verbose)
    _patch_anaconda_client(args, verbose)
    _patch_binstar_client(args, verbose)


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


def _print_config(what, args, config):
    if args.verbose or args.status:
        value = config.get("anaconda_ident")
        print("%s user agent: %s" % (what, value or "<default>"))


def _print_default_channels(what, args, config):
    if args.verbose or args.status:
        value = config.get("default_channels")
        if value is None:
            value = "<none>"
        elif not value:
            value = "[]"
        else:
            value = "\n - " + "\n - ".join(value)
        print("%s default_channels: %s" % (what, value))


def _print_channel_alias(what, args, config):
    if args.verbose or args.status:
        value = config.get("channel_alias")
        print("%s channel_alias: %s" % (what, value or "<none>"))


def _print_tokens(what, args, config):
    if args.verbose or args.status:
        tokens = config.get("repo_tokens")
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


def read_condarc(args, fname):
    verbose = args.verbose or args.status
    fexists = exists(fname)
    if verbose:
        spath = relpath(fname, sys.prefix)
        print("config file: %s%s" % (spath, "" if fexists else " (not present)"))
    if not fexists:
        return {}
    try:
        with open(fname, "r") as fp:
            condarc = _yaml().safe_load(fp)
    except Exception:
        error("config load failed")
    if verbose:
        _print_config("|", args, condarc)
        _print_default_channels("|", args, condarc)
        _print_channel_alias("|", args, condarc)
        _print_tokens("|", args, condarc)
    return condarc


def manage_condarc(args, condarc):
    if args.clean:
        return {}
    condarc = condarc.copy()
    # config string
    if args.config is not None:
        new_token = "" if args.config == "default" else args.config
        _set_or_delete(condarc, "anaconda_ident", new_token)
        _print_config("new", args, condarc)
    # default_channels
    if args.default_channel:
        nchan = []
        for c1 in args.default_channel:
            for c2 in c1.split(","):
                if c2.strip():
                    nchan.append(c2.strip().rstrip("/"))
        _set_or_delete(condarc, "default_channels", nchan)
        _print_default_channels("new", args, condarc)
    # channel alias
    if args.channel_alias is not None:
        _set_or_delete(condarc, "channel_alias", args.channel_alias)
        _print_channel_alias("new", args, condarc)
    # tokens
    if args.repo_token is not None:
        tokens = {}
        if args.repo_token.strip():
            defchan = condarc.get("default_channels", []) + [
                condarc.get("channel_alias", "")
            ]
            defchan = [c for c in defchan if "/" in c]
            if not defchan:
                if args.verbose:
                    print("------------------------")
                error(
                    "A repo_token value may only be supplied if accompanied\n"
                    "by a channel_alias or default_channels value.",
                    fatal=True,
                    traceback=False,
                )
            defchan = "/".join(defchan[0].strip().split("/", 3)[:3]) + "/"
            tokens[defchan] = args.repo_token.strip()
        _set_or_delete(condarc, "repo_tokens", tokens)
        _print_tokens("new", args, condarc)
    _set_or_delete(condarc, "add_anaconda_token", bool(condarc.get("repo_tokens")))
    return condarc


def write_condarc(args, fname, condarc):
    if not condarc:
        if exists(fname):
            if args.verbose:
                print("removing anaconda_ident condarc...")
            if not tryop(os.unlink, fname):
                error("condarc removal failed")
        return
    if args.verbose:
        what = "updating" if exists(fname) else "creating"
        print("%s anaconda_ident condarc..." % what)
    renamed = False
    try:
        os.makedirs(dirname(fname), exist_ok=True)
        if exists(fname):
            renamed = tryop(os.rename, fname, fname + ".orig")
        with open(fname, "w") as fp:
            _yaml().dump(condarc, fp)
        if renamed:
            tryop(os.unlink, fname + ".orig")
    except Exception:
        error("condarc update failed")
        if renamed:
            tryop(os.rename, fname + ".orig", fname)


def modify_binstar(args, condarc, save=True):
    global success
    new_tokens = condarc.get("repo_tokens")
    if not new_tokens:
        if args.verbose:
            print("no tokens to write or clear")
        return

    from conda.gateways import anaconda_client as a_client

    token_dir = a_client._get_binstar_token_directory()
    try:
        old_tokens = os.listdir(token_dir)
    except Exception:
        old_tokens = []

    first_token = True
    for url, token in new_tokens.items():
        # Make sure all tokens have a trailing slash
        url = url.rstrip("/") + "/"
        for fname in list(old_tokens):
            # Remove old tokens that can potentially conflict
            # with this one. It is not enough to exactly match
            # the filename, a prefix match of the URL is needed
            if not fname.endswith(".token"):
                continue
            old_url = a_client.unquote_plus(fname[:-6])
            if not old_url.startswith(url):
                continue
            if args.verbose:
                print("removing existing token:", old_url)
            old_tokens.remove(fname)
            fpath = join(token_dir, fname)
            try:
                if first_token:
                    os.chmod(token_dir, os.stat(token_dir).st_mode | stat.S_IWRITE)
                    first_token = False
                os.chmod(fpath, os.stat(fpath).st_mode | stat.S_IWRITE)
                os.unlink(fpath)
            except Exception:
                error("error removing old token", warn=True)
        if not save:
            continue
        # For the special case repo.anaconda.cloud, save the
        # token with the "repo/" URL path. This reduces conflicts
        # with navigator and conda-token
        if url == "https://repo.anaconda.cloud/":
            url += "repo/"
        if args.verbose:
            print("installing token:", url)
        fname = a_client.quote_plus(url) + ".token"
        fpath = join(token_dir, fname)
        t_success = False
        try:
            if first_token:
                first_token = False
                os.makedirs(token_dir, exist_ok=True)
                os.chmod(token_dir, os.stat(token_dir).st_mode | stat.S_IWRITE)
            if exists(fpath):
                os.chmod(fpath, os.stat(fpath).st_mode | stat.S_IWRITE)
            with open(fpath, "w") as fp:
                fp.write(token)
            t_success = True
            os.chmod(fpath, os.stat(fpath).st_mode & ~stat.S_IWRITE)
        except Exception:
            if not t_success:
                error("token installation failed", warn=True)


def main():
    global success

    args, p = parse_argv()
    if len(sys.argv) <= 1:
        p.print_help()
        return 0

    verbose = args.verbose or args.status or len(sys.argv) <= 1
    if verbose:
        pkg_name = basename(dirname(__file__))
        msg = pkg_name + " installer"
        print(msg)
        msg = "-" * len(msg)
        print(msg)
        if len(sys.argv) <= 1:
            sys.argv[0] = "anaconda-ident"
            print(msg)
            return 0
    manage_patch(args)
    if args.verify:
        if verbose:
            print(msg)
        return 0
    fname = join(sys.prefix, "etc", "anaconda_ident.yml")
    condarc = read_condarc(args, fname)
    if not success:
        if verbose:
            print(msg)
        return -1
    if args.status or len(sys.argv) <= 1 + ("--quiet" in sys.argv):
        if verbose:
            print(msg)
        return 0 if success else -1
    newcondarc = manage_condarc(args, condarc)
    if condarc != newcondarc:
        write_condarc(args, fname, newcondarc)
    elif verbose:
        print("no changes to save")
    if args.write_token or args.clear_old_token:
        modify_binstar(args, newcondarc, save=args.write_token)
    if verbose:
        print(msg)
    return 0 if success else -1


if __name__ == "__main__":
    sys.exit(main())
