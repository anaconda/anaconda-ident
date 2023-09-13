#!/bin/bash

set -o errtrace -o nounset -o pipefail -o errexit

SCRIPTDIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck disable=SC1091
source "$CONDA_PREFIX/etc/profile.d/conda.sh"

ver=$(date +%Y%m%d)
compatibility=--compatibility
grep '|' "$SCRIPTDIR"/config_tests.txt | while IFS="|" read -r cstr def cha rtk bstr; do
    bnum=$RANDOM
    echo "--------"
    echo "config string: $cstr"
    echo "default channels: $def"
    echo "channel alias: $cha"
    echo "repo token: $rtk"
    echo "build string: $bstr"
    echo "build number: $bnum"
    echo "--------"
    output=$(python -m anaconda_ident.keymgr $compatibility \
             --name "testpkg" --version "$ver" --build-string "$bstr" --build-number "$bnum" \
             --config-string "$cstr" --default-channel "$def" --channel-alias "$cha" --repo-token "$rtk")
    echo "$output"
    echo "--------"
    fname=$(echo "$output" | tail -1)
    [ -f "$fname" ] || exit 1
    rm -rf "${CONDA_PREFIX}/pkgs/${fname%%.*}"*
    conda install -p "$CONDA_PREFIX" "$fname" --freeze-installed --offline --yes
    # This corrupts the package cache as a way to test that the files were
    # copied, not hard linked, to the environment
    echo "--------"
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
    conda list testpkg | grep -q ^testpkg || exit 1
    CONFIG_STRING="$cstr" DEFAULT_CHANNELS="$def" \
        CHANNEL_ALIAS="$cha" REPO_TOKEN="$rtk" \
        ANACONDA_IDENT_DEBUG=1 SKIP_INSTALL=1 python "$SCRIPTDIR"/test_config.py
    conda remove -p "$CONDA_PREFIX" testpkg --force --offline --yes
    rm -rf "$fname" "${CONDA_PREFIX}/pkgs/${fname%%.*}"*
done
