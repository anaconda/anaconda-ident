#!/bin/bash

set -o errtrace -o nounset -o pipefail -o errexit

SCRIPTDIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
mode=${1:-}; shift

trap cleanup EXIT

cleanup() {
    arg1=$?
    if [ "$mode" != "--test-only" ]; then
        mkdir -p "$CONDA_PREFIX/conda-bld" || :
        rm -rf "$CONDA_PREFIX/conda-bld/noarch/testpkg-*" || :
        conda index "$CONDA_PREFIX/conda-bld" || :
    fi
    if [ "$mode" != "--build-only" ]; then
        rm -rf "$CONDA_PREFIX/pkgs/testpkg-"* || :
        conda remove -p "$CONDA_PREFIX" testpkg anaconda-ident \
            --force --offline --yes || :
    fi
    exit "$arg1"
}

# shellcheck disable=SC1091
source "$CONDA_PREFIX/etc/profile.d/conda.sh"
mkdir -p "$CONDA_PREFIX/conda-bld/noarch"

ver=$(date +%Y%m%d)
if [ "$mode" = "--test-only" ]; then
    # shellcheck disable=SC2012
    bnum=$(ls -1 "$CONDA_PREFIX/conda-bld/noarch" | sed -nE 's@^testpkg-.*_(.*).tar.bz2@\1@p' | tail -1)
    if [ -z "$bnum" ]; then
        echo "Couldn't find test packages"
        exit 1
    fi
else
    rm -f "$CONDA_PREFIX/conda-bld/noarch/testpkg-"*
    bnum=$RANDOM
fi
if [ "$mode" != "--build-only" ]; then
    rm -rf "${CONDA_PREFIX}/pkgs/testpkg-"* || :
fi

compatibility=--compatibility
grep '|' "$SCRIPTDIR"/config_tests.txt | while IFS="|" read -r cstr def cha rtk bstr; do
    echo "--------"
    echo "config string: $cstr"
    echo "default channels: $def"
    echo "channel alias: $cha"
    echo "repo token: $rtk"
    echo "build string: $bstr"
    echo "build number: $bnum"
    echo "--------"
    fname=testpkg-$ver-${bstr}_$bnum.tar.bz2
    pkg=testpkg=$ver=${bstr}_$bnum

    if [ "$mode" != "--test-only" ]; then
        output=$(python -m anaconda_ident.keymgr $compatibility \
                 --name "testpkg" --version "$ver" --build-string "$bstr" --build-number "$bnum" \
                 --config-string "$cstr" --default-channel "$def" --channel-alias "$cha" --repo-token "$rtk")
        echo "$output"
        echo "--------"
        [ -f "$fname" ] || exit 1
        mv "$fname" "$CONDA_PREFIX/conda-bld/noarch/"
        conda index "$CONDA_PREFIX/conda-bld"
    fi

    if [ "$mode" = "--build-only" ]; then
        continue
    fi

    conda install -p "$CONDA_PREFIX" "$pkg" \
        --override-channels -c local --freeze-installed --offline --yes
    echo "--------"

    # This corrupts the package cache as a way to test that the files were
    # copied, not hard linked, to the environment
    echo "Verifying copies, not links"
    for fn in "${CONDA_PREFIX}/pkgs/${fname%%.*}"/*/anaconda_ident.yml; do
        fpath="${CONDA_PREFIX}/$(basename "$(dirname "$fn")")/anaconda_ident.yml"
        echo "corrupted: true" >> "$fn"
        echo "$fn -> $fpath"
        if [ ! -f "$fpath" ]; then echo "config file not found"; exit 1; fi
        if grep "^corrupted" "$fpath"; then echo "config file linked"; exit 1; fi
    done
    echo "--------"

    if [ -n "$compatibility" ]; then
        if [ $compatibility = "--compatibility" ]; then
            what="Compatibility"
            compatibility="--legacy-only"
        else
            what="Legacy"
            compatibility=""
        fi
        if [ -f "$CONDA_PREFIX/etc/anaconda_ident.yml" ]; then
            echo "$what mode confirmed"
        else
            echo "ERROR: $what mode failed"
            exit 1
        fi
    fi
    echo "--------"

    conda list | grep -q ^testpkg || exit 1
    CONFIG_STRING="$cstr" DEFAULT_CHANNELS="$def" \
        CHANNEL_ALIAS="$cha" REPO_TOKEN="$rtk" \
        ANACONDA_IDENT_DEBUG=1 SKIP_INSTALL=1 python "$SCRIPTDIR"/test_config.py
done
