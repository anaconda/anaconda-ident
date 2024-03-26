#!/bin/bash

set -o errtrace -o nounset -o pipefail -o errexit

SCRIPTDIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
mode=${1:-}

# For local tests we need to avoid installing anaconda-ident
if conda list anaconda-ident 2>/dev/null | grep -q ^anaconda-ident; then
    echo "Local tests detected; force install enabled"
    remove_pkgs="testpkg"
    use_blob=yes
else
    remove_pkgs="testpkg anaconda-ident"
    use_blob=no
fi

cleanup() {
    local arg1=$?
    echo "--------"
    rm other_settings_test.yaml 2>/dev/null || :
    if [ "$mode" != "--test-only" ]; then
        rm -rf "$CONDA_PREFIX/conda-bld/noarch/testpkg-*" 2>/dev/null || :
        conda index "$CONDA_PREFIX/conda-bld" || :
    fi
    if [ "$mode" != "--build-only" ]; then
        rm -rf "$CONDA_PREFIX/pkgs/testpkg-"* 2>/dev/null || :
        conda remove -p "$CONDA_PREFIX" "$remove_pkgs" --offline --yes 2>/dev/null || :
    fi
    exit "$arg1"
}

trap cleanup EXIT

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

# Include flipped values of these two settings in an additional
# settings file to test that functionality
info_orig=$(conda config --show | grep -E '^(auto_update_conda|notify_outdated_conda):')
info_new=$(echo "$info_orig" | sed 's@True@false@;s@False@true@' | sed 's@true@True@;s@false@False@')
echo "$info_new" >other_settings_test.yaml

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
    fpath="$CONDA_PREFIX/conda-bld/noarch/$fname"
    pkg=testpkg=$ver=${bstr}_$bnum

    if [ "$mode" != "--test-only" ]; then
        output=$(python -m anaconda_ident.keymgr $compatibility \
                 --name "testpkg" --version "$ver" --build-string "$bstr" --build-number "$bnum" \
                 --config-string "$cstr" --default-channel "$def" --channel-alias "$cha" \
                 --repo-token "$rtk" --other-settings other_settings_test.yaml --pepper)
        echo "$output"
        echo "--------"
        [ -f "$fname" ] || exit 1
        mv "$fname" "$fpath"
        conda index "$CONDA_PREFIX/conda-bld"
    fi

    if [ "$mode" = "--build-only" ]; then
        continue
    fi

    if [ "$use_blob" = yes ]; then ipkg=$fpath; else ipkg=$pkg; fi
    conda install -p "$CONDA_PREFIX" "$ipkg" \
        --override-channels -c local --freeze-installed --offline --yes
    echo "--------"

    echo "Verifying contents"
    if [ "$compatibility" = "--legacy-only" ]; then
        ftest=$CONDA_PREFIX/etc/anaconda_ident.yml
    else
        ftest=$CONDA_PREFIX/condarc.d/anaconda_ident.yml
    fi
    if [ ! -f "$ftest" ]; then
        echo "ERROR: file not found: $ftest"
        exit 1
    fi
    cat "$ftest"
    echo "--------"

    all_config=$(conda config --show)
    echo "Verifying config string"
    cstr_cfg=$(echo "$all_config" | grep -E '^anaconda_ident:')
    echo "$cstr_cfg"
    if [[ "$cstr_cfg" != "anaconda_ident: ${cstr}:"* ]]; then
        echo "EXPECTED: anaconda_ident: ${cstr}:..."
        echo "ERROR: config string not set properly"
        exit 1
    fi
    echo "--------"

    echo "Verifying additional settings"
    info_test=$(echo "$all_config" | grep -E '^(auto_update_conda|notify_outdated_conda):')
    echo "$info_test"
    if [ "$info_test" != "$info_new" ]; then
        # shellcheck disable=SC2001
        echo "$info_new" | sed 's@^@EXPECTED: @'
        echo "ERROR: additional settings were not included"
        exit 1
    fi
    echo "--------"

    if [ -n "$rtk" ]; then
        echo "Verifying repo tokens"
        repo_tok=$(echo "$all_config" | sed -nE '/^repo_tokens:/{:loop n;/^[A-za-z]/q;s/^ *//p;b loop;};')
        echo "$repo_tok"
        if [ -z "$repo_tok" ]; then
            echo "ERROR: repo tokens not included"
            exit 1
        fi
        repo_chan="$(echo "$repo_tok" | sed -E 's@/?: .*@@')/main"
        conda search -vvv --override-channels -c "$repo_chan" testpackage
        echo "--------"
    fi

    exit 0

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
    python "$SCRIPTDIR"/test_heartbeats.py
done
