import argparse
import hashlib
import io
import json
import os
import sys
from datetime import datetime
from os.path import basename, dirname
from tarfile import TarInfo
from tarfile import open as tf_open

try:
    import ruamel.yaml as ruamel_yaml
except Exception:
    import ruamel_yaml

from . import __version__

LINE = "-" * 16


def parse_argv():
    p = argparse.ArgumentParser()
    p.add_argument(
        "--config-string",
        default=None,
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
        default=".",
        help="The directory in which to create the package. The default "
        "is the current directory.",
    )
    p.add_argument(
        "--verbose",
        action="store_true",
        help="Print a verbose explanation of the progress.",
    )
    p.add_argument(
        "--compatibility",
        action="store_true",
        help="Stores the config file in a second location in the environment. "
        "Older versions of anaconda-ident stored it in a non-standard location; "
        "this has been corrected in newer versions of the tool. For existing "
        "deployments, it may be necessary to use this option to ensure "
        "uninterrupted service.",
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
    return args, p


ABOUT_JSON = {"summary": "Anaconda-Ident Configuration Package"}
FNAME = "condarc.d/anaconda_ident.yml"
FNAME2 = "etc/anaconda_ident.yml"
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
PATHS_JSON = {
    "paths": [
        {
            "_path": "",
            "no_link": True,
            "path_type": "hardlink",
            "sha256": "",
            "size_in_bytes": 0,
        }
    ],
    "paths_version": 1,
}


def _bytes(data, yaml=False):
    if isinstance(data, bytes):
        pass
    elif isinstance(data, dict):
        if yaml:
            data = ruamel_yaml.safe_dump(data, default_flow_style=False).encode("ascii")
        else:
            data = json.dumps(data, separators=(",", ":"), sort_keys=True).encode(
                "ascii"
            )
    elif isinstance(data, str):
        data = data.encode("utf-8")
    else:
        raise NotImplementedError
    return data, len(data)


def _add(tf, fname, data, verbose):
    data, size = _bytes(data)
    if verbose:
        print("%s:" % fname)
        for line in data.decode("utf-8").splitlines():
            if line:
                print("|", line)
    if tf is not None:
        info = TarInfo(fname)
        info.size = size
        tf.addfile(info, io.BytesIO(data))


def build_tarfile(dname, args, config_dict):
    name = args.name
    dt_now = datetime.now()
    version = args.version or dt_now.strftime("%Y%m%d")
    timestamp = int(dt_now.timestamp() * 1000 + 0.5)
    build_number = args.build_number or 0
    build_string = (args.build_string + "_" if args.build_string else "") + str(
        build_number
    )
    config_data, config_size = _bytes(config_dict, yaml=True)
    h = hashlib.new("sha256")
    h.update(config_data)
    config_hash = h.hexdigest()
    fname = f"{name}-{version}-{build_string}.tar.bz2"
    fpath = os.path.join(dname or ".", fname)
    verbose = args.verbose or args.dry_run
    if verbose:
        msg = "Building {}{}".format(fname, " (dry_run)" if args.dry_run else "")
        print(msg)
        print(LINE)

    def add_all(tf):
        v = args.verbose or args.dry_run
        new_file = not args.legacy_only
        old_file = args.legacy_only or args.compatibility
        NO_LINK = []
        if new_file:
            _add(tf, FNAME, config_data, v)
            NO_LINK.append(FNAME)
        if old_file:
            _add(tf, FNAME2, config_data, v)
            NO_LINK.append(FNAME2)
        _add(tf, "info/about.json", ABOUT_JSON, v)
        _add(tf, "info/files", FNAME, v)
        _add(tf, "info/no_link", "\n".join(NO_LINK), v)
        INDEX_JSON["name"] = name
        INDEX_JSON["version"] = version
        INDEX_JSON["build_number"] = build_number
        INDEX_JSON["build"] = build_string
        INDEX_JSON["timestamp"] = timestamp
        if not old_file:
            INDEX_JSON["depends"][0] += f" >={__version__}"
        _add(tf, "info/index.json", INDEX_JSON, v)
        _add(tf, "info/link.json", LINK_JSON, v)
        PATHS_JSON["paths"][0]["_path"] = FNAME
        PATHS_JSON["paths"][0]["size_in_bytes"] = config_size
        PATHS_JSON["paths"][0]["sha256"] = config_hash
        if old_file and new_file:
            PATHS_JSON["paths"].append(PATHS_JSON["paths"][0].copy())
        if old_file:
            PATHS_JSON["paths"][-1]["_path"] = FNAME2
        _add(tf, "info/paths.json", PATHS_JSON, v)

    if args.dry_run:
        add_all(None)
    else:
        with tf_open(fpath, "w:bz2") as tf:
            add_all(tf)
    return fname


def build_config_dict(args):
    verbose = args.verbose or args.dry_run
    if verbose:
        print("Building config dictionary")
        print(LINE)
    result = {}
    result["anaconda_ident"] = args.config_string or "default"
    if verbose:
        print("anaconda_ident:", result["anaconda_ident"])
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
