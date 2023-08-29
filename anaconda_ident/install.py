import sysconfig
import argparse
import sys
import os

from os.path import basename, dirname, exists, join, relpath
from traceback import format_exc

# Used by the subcommand plugin that doesn't have access to the used argparse parser
_subcommand_parser = None


def configure_parser(p):
    """Configure the given argparse parser instance"""
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
    p.add_argument(
        "--quiet",
        dest="verbose",
        action="store_false",
        default=True,
        help="Silent mode; disables all non-error output.",
    )


def parse_argv(args=None):
    p = argparse.ArgumentParser(description="The anaconda-ident installer.")

    # We're separating parser configuration here as it enables us to re-use
    # the code to configure the subcommand parser in conda>=23.7.0 style subcommands
    configure_parser(p)

    # args is None when it's being called as anaconda-ident, and it's populated
    # when called from the conda subcommand, we don't need to update sys.argv then
    if args is None:
        sys.argv[0] = "anaconda-ident"

    args = p.parse_args(args)

    if (args.clean or args.verify or args.status) and sum(
        v is not None for v in vars(args).values()
    ) != 6:
        what = "clean" if args.clean else ("status" if args.status else "verify")
        print("WARNING: --%s overrides other operations" % what)
    return args, p


success = True


def error(what, fatal=False, warn=False):
    global success
    print("ERROR:", what)
    tb = format_exc()
    if not tb.startswith("NoneType"):
        print("-----")
        print(tb.rstrip())
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
        if verbose:
            print("success")
    except Exception as exc:
        if verbose:
            what = "failed"
        else:
            what = f"failed to patch {relpath(pfile, _sp_dir())}"
        print(f"{what}: {exc}")
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


def manage_patch(args):
    verbose = args.verbose or args.status
    if verbose:
        print("conda prefix:", sys.prefix)
    _patch_conda_context(args, verbose)


def execute(args):
    """
    This is just the CLI execution after parsing and before returning of
    the result to integration into the conda subcommand plugin API
    """
    global success

    # if a conda>=23.7.0 subcommand plugin is configuring the subcommand parser,
    # we're storing the instance in a module variable, so we can print the help
    # if there are no command line options passed
    if _subcommand_parser is not None and len(sys.argv) <= 2:
        _subcommand_parser.print_help()
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
    if verbose:
        print(msg)
    return 0 if success else -1


def main(args=None):
    global success

    # if conda passes us pre-parsed args, we have to reuse them for
    # the conda subcommand integration
    args, p = parse_argv(args)

    # we're checking for conda or conda.exe for old-style conda subcommands
    if len(sys.argv) <= 1 or (
        basename(sys.argv[0]).lower() in ("conda", "conda.exe") and len(sys.argv) <= 2
    ):
        p.print_help()
        return 0

    # we separate execution here to be able to hook into the conda subcommand plugin API
    execute(args)

    return 0 if success else -1


if __name__ == "__main__":
    sys.exit(main())
