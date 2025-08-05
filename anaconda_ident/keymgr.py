import argparse
import base64
import hashlib
import io
import json
import os
import sys
from datetime import datetime
from os.path import basename, commonpath, dirname, exists, isdir, realpath
from tarfile import TarInfo
from tarfile import open as tf_open

try:
    from ruamel.yaml import YAML
except Exception:
    from ruamel_yaml import YAML

from . import __version__

LINE = "-" * 16
HEARTBEAT_PKG = "main/noarch/activate-0.0.1-0.conda"


def _org_token(args):
    org_token = args.org_token
    cparts = args.config_string.split(":") + [""]
    if org_token and cparts[1] and cparts[1] != org_token:
        raise argparse.ArgumentError("Conflicting org strings supplied")
    return org_token or cparts[1]


def _pepper(args):
    pepper = args.pepper
    cparts = args.config_string.split(":") + ["", ""]
    if cparts and cparts[2] and cparts[2] != cparts:
        raise argparse.ArgumentError("Conflicting pepper values supplied")
    if cparts[2]:
        return cparts[2]
    if args.pepper:
        pepper = os.urandom(16)
        pepper = base64.b64encode(pepper).rstrip(b"=")
        return pepper.decode("ascii")
    return ""


def parse_argv():
    p = argparse.ArgumentParser()
    p.add_argument(
        "--config-string",
        default="default",
        help="Set the telemetry configuration. Defaults to 'default'.",
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
        "This is recommended only if all channels are sourced from the same repository; "
        "e.g., an instance of Anaconda Server.",
    )
    p.add_argument(
        "--repo-token",
        default=None,
        help="Store a token for conda authentication. To use this, a full channel "
        "URL is required. This will either be determined from the first full URL "
        "in the default_channels list; or if not present there, from channel_alias.",
    )
    p.add_argument(
        "--org-token",
        default=None,
        help="Store an organization token. It is still possible to include the org "
        "token in the --config-string argument, but this provides an alternative "
        "that may be easier to use with the default ident configuration.",
    )
    p.add_argument(
        "--name",
        default="anaconda-ident-config",
        help="The conda name for the package. Defaults to anaconda-ident-config.",
    )
    p.add_argument(
        "--version",
        default=None,
        help="The conda version for the package. Defaults to an eight digit "
        "string formed from the date and the month.",
    )
    p.add_argument(
        "--build-number",
        default=0,
        type=int,
        help="The conda build number for the package. Defaults to 0.",
    )
    p.add_argument(
        "--build-string",
        default="default",
        help="The conda build number for the package. Defaults to the "
        "organization component of the config string if supplied, or "
        "'default if none is supplied.",
    )
    p.add_argument(
        "--directory",
        default=None,
        help="The directory in which to create the package. The default "
        "is the current directory.",
    )
    p.add_argument(
        "--verbose",
        action="store_true",
        help="Print a verbose explanation of the progress.",
    )
    p.add_argument(
        "--heartbeat",
        default=True,
        action=argparse.BooleanOptionalAction,
        help="By default, anaconda-ident will enable activation heartbeats. "
        "This takes the form of a single HEAD request attempt to the tokenized repository "
        "with silent failure and a short timeout for negligible disruption.",
    )
    p.add_argument(
        "--compatibility",
        default=False,
        action=argparse.BooleanOptionalAction,
        help="Stores the config file in a second location in the environment. "
        "Older versions of anaconda-ident stored it in a non-standard location; "
        "this has been corrected in newer versions of the tool. For existing "
        "deployments, it may be necessary to use this option to ensure "
        "uninterrupted service.",
    )
    p.add_argument(
        "--pepper",
        action="store_true",
        help="If supplied, a random 16-byte pepper value is computed, base64 "
        "encoded, and appended to the config-string. If a pepper value was "
        "already included in the config string, an error will be raised.",
    )
    p.add_argument(
        "--other-settings",
        default=None,
        help="If supplied, it is assumed to be a filename of additional conda "
        "settings to add to the configuration file. It must be a valid YAML "
        "parseable file, but no attempt is made to confirm that it contains "
        "valid conda settings, or that those settings do not conflict with "
        "those generated by this function.",
    )
    p.add_argument("--legacy-only", action="store_true", help=argparse.SUPPRESS)
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode. "
        "Print the content of the package but do not create it. Also sets verbose=True.",
    )
    if len(sys.argv) <= 1:
        p.print_help()
        print(LINE)
        print("No arguments supplied... exiting.")
        sys.exit(-1)
    args = p.parse_args()
    if args.directory:
        p1 = realpath(args.directory)
        if exists(p1):
            if not isdir(p1):
                raise argparse.ArgumentError("Not a directory: %s" % p1)
        else:
            p2 = commonpath([realpath(os.getcwd())])
            try:
                is_sub = commonpath([p1, p2]) == p2
            except Exception:
                is_sub = False
            if not is_sub:
                raise argparse.ArgumentError("Directory does not exist: %s" % p1)
    _org_token(args)
    _pepper(args)
    return args, p


ABOUT_JSON = {"summary": "Anaconda-Ident Configuration Package"}
FNAME = "condarc.d/anaconda_ident.yml"
FNAME2 = "etc/anaconda_ident.yml"
FNAME3 = "org_token"
INDEX_JSON = {
    "arch": None,
    "build": "custom_0",
    "build_number": 0,
    "depends": ["anaconda-ident"],
    "license": "NONE",
    "name": "anaconda-ident-config",
    "noarch": "generic",
    "platform": None,
    "subdir": "noarch",
    "timestamp": 0,
    "version": "19000101",
}
LINK_JSON = {"noarch": {"type": "generic"}, "package_metadata_version": 1}
PATHS_JSON_REC = {
    "_path": "",
    "no_link": True,
    "path_type": "hardlink",
    "sha256": "",
    "size_in_bytes": 0,
}
PATHS_JSON = {
    "paths": [],
    "paths_version": 1,
}
NO_LINK = []


def _bytes(data, yaml=False):
    if isinstance(data, bytes):
        pass
    elif isinstance(data, dict):
        if yaml:
            buf = io.BytesIO()
            YAML(typ="safe", pure=True).dump(data, buf)
            data = buf.getvalue()
        else:
            data = json.dumps(data, separators=(",", ":"), sort_keys=True).encode(
                "ascii"
            )
    elif isinstance(data, str):
        data = data.encode("utf-8")
    else:
        raise NotImplementedError
    h = hashlib.new("sha256")
    h.update(data)
    return data, len(data), h.hexdigest()


def _add(tf, fname, data, verbose, add_to_paths=False):
    data, size, hvalue = _bytes(data)
    if verbose:
        print("%s:" % fname)
        for line in data.decode("utf-8").splitlines():
            if line:
                print("|", line)
    if tf is not None:
        info = TarInfo(fname)
        info.size = size
        tf.addfile(info, io.BytesIO(data))
    if add_to_paths:
        prec = PATHS_JSON_REC.copy()
        prec["_path"] = fname
        prec["size_in_bytes"] = size
        prec["sha256"] = hvalue
        PATHS_JSON["paths"].append(prec)
        NO_LINK.append(fname)


def build_tarfile(dname, args, config_dict):
    name = args.name
    dt_now = datetime.now()
    version = args.version or dt_now.strftime("%Y%m%d")
    timestamp = int(dt_now.timestamp() * 1000 + 0.5)
    build_number = args.build_number or 0
    build_string = (args.build_string + "_" if args.build_string else "") + str(
        build_number
    )
    org_token = _org_token(args)
    fname = f"{name}-{version}-{build_string}.tar.bz2"
    if dname:
        fname = os.path.join(dname, fname)
    verbose = args.verbose or args.dry_run
    if verbose:
        msg = "Building {}{}".format(fname, " (dry_run)" if args.dry_run else "")
        print(msg)
        print(LINE)

    def add_all(tf):
        v = args.verbose or args.dry_run
        new_file = not args.legacy_only
        old_file = args.legacy_only or args.compatibility
        if new_file:
            _add(tf, FNAME, config_dict, v, True)
        if old_file:
            _add(tf, FNAME2, config_dict, v, True)
        if org_token:
            _add(tf, FNAME3, org_token, v, True)
        _add(tf, "info/about.json", ABOUT_JSON, v)
        _add(tf, "info/files", FNAME, v)
        _add(tf, "info/no_link", "\n".join(NO_LINK), v)
        INDEX_JSON["name"] = name
        INDEX_JSON["version"] = version
        INDEX_JSON["build_number"] = build_number
        INDEX_JSON["build"] = build_string
        INDEX_JSON["timestamp"] = timestamp
        if not old_file:
            INDEX_JSON["depends"][0] += " >=" + __version__
        _add(tf, "info/index.json", INDEX_JSON, v)
        _add(tf, "info/link.json", LINK_JSON, v)
        _add(tf, "info/paths.json", PATHS_JSON, v)

    if args.dry_run:
        add_all(None)
    else:
        if dname:
            os.makedirs(dname, exist_ok=True)
        with tf_open(fname, "w:bz2") as tf:
            add_all(tf)
    return fname


def build_config_dict(args):
    verbose = args.verbose or args.dry_run
    if verbose:
        print("Building config dictionary")
        print(LINE)
    result = {}
    cstr = args.config_string.split(":", 1)[0] or "default"
    org_token = _org_token(args)
    pepper = _pepper(args)
    cparts = [cstr]
    if org_token or pepper:
        cparts.append(org_token)
    if pepper:
        cparts.append(pepper)
    result["anaconda_ident"] = ":".join(cparts)
    result["anaconda_anon_usage"] = True
    result["aggressive_update_packages"] = ["anaconda_anon_usage", "anaconda_ident"]
    if verbose:
        for k, v in result.items():
            print(f"{k}: {v}")
    if args.default_channel:
        nchan = []
        for c1 in args.default_channel:
            for c2 in c1.split(","):
                if c2.strip():
                    c2 = c2.strip().rstrip("/")
                    if c2 not in nchan:
                        nchan.append(c2)
        if nchan:
            result["default_channels"] = nchan
    if verbose and "default_channels" in result:
        print("default_channels:")
        for c in result["default_channels"]:
            print("- ", c)
    if args.channel_alias:
        c = args.channel_alias.strip().rstrip("/")
        if c:
            result["channel_alias"] = c
    if verbose and "channel_alias" in result:
        print("channel_alias:", result["channel_alias"])
    if not args.heartbeat:
        hb = False
    elif "channel_alias" in result:
        hb = result["channel_alias"] + "/" + HEARTBEAT_PKG
    else:
        hb = True
    result["anaconda_heartbeat"] = hb
    if verbose:
        print("anaconda_heartbeat:", hb)
    if args.repo_token is not None:
        token = args.repo_token.strip()
        defchan = list(result.get("default_channels", []))
        defchan.append(result.get("channel_alias", ""))
        defchan = [c for c in defchan if "/" in c]
        if token and defchan:
            defchan = "/".join(defchan[0].strip().split("/", 3)[:3]) + "/"
            result["repo_tokens"] = {defchan: token}
    if "repo_tokens" in result:
        result["add_anaconda_token"] = True
        if verbose:
            print("repo_tokens:")
            for k, v in result["repo_tokens"].items():
                print(f"  {k}: {v}")
    if args.other_settings is not None:
        with open(args.other_settings) as fp:
            data = YAML(typ="safe", pure=True).load(fp)
        result.update(data)
        if verbose:
            for k, v in data.items():
                print(f"{k}: {v}")
    return result


def main():
    global success
    args, p = parse_argv()
    verbose = args.verbose or args.dry_run
    if verbose:
        pkg_name = basename(dirname(__file__))
        msg = pkg_name + " config builder"
        print(msg)
        print(LINE)
        if len(sys.argv) == 1:
            p.print_help()
            print(LINE)
    config_dict = build_config_dict(args)
    if verbose:
        print(LINE)
    fname = build_tarfile(args.directory, args, config_dict)
    if verbose:
        print(LINE)
    print(fname)
    return 0


if __name__ == "__main__":
    sys.exit(main())
