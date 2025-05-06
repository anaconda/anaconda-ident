#!/bin/bash
# shellcheck disable=SC2001,SC2086

set -o errtrace -o nounset -o pipefail -o errexit

SCRIPTDIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
export CONDA_ALWAYS_YES=true
mode=${1:-}

# For local tests we need to avoid installing anaconda-ident
fdir="testbld"
if conda list | grep -q '^anaconda-ident.*<develop>'; then
    echo "cannot run with a development install"
    exit 1
fi

installed_pkgs=""
cached_pkgs=""
pkgs_dir=$(conda config --show pkgs_dirs | sed -nE '/^ *- */{s///;p;q;}')

do_cleanup() {
    rm -rf testbld 2>/dev/null || :
    if [ -n "$cached_pkgs" ]; then
        echo "Removing: $cached_pkgs"
        rm -rf $cached_pkgs
        conda index "$CONDA_PREFIX/conda-bld" || :
        cached_pkgs=""
    fi
    if [ -n "$installed_pkgs" ]; then
        echo "Uninstalling: $installed_pkgs"
        conda remove $installed_pkgs --force </dev/null 2>/dev/null || :
        installed_pkgs=""
    fi
}

cleanup() {
    local arg1=$?
    echo "--------"
    do_cleanup
    rm other_settings_test.yaml || :
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
info_orig=$(conda config --show | grep -E '^(register_envs|repodata_use_zst):' | sort)
info_new=$(echo "$info_orig" | sed 's@True@false@;s@False@true@' | sed 's@true@True@;s@false@False@')
echo "$info_new" >other_settings_test.yaml

grep '|' "$SCRIPTDIR"/config_tests.txt | while IFS="|" read -r cstr def cha rtk bstr; do
    echo "--------"
    echo "config string: $cstr"
    echo "default channels: $def"
    echo "channel alias: $cha"
    echo "repo token: $rtk"
    echo "build string: $bstr"
    echo "build number: $bnum"
    echo "--------"
    fbase="testpkg-$ver-${bstr}_$bnum"
    fname="$fbase.tar.bz2"
    fpath="$CONDA_PREFIX/conda-bld/noarch/$fname"

    if [ "$mode" != "--test-only" ]; then
        output=$(python -m anaconda_ident.keymgr --directory $fdir \
                 --name "testpkg" --version "$ver" --build-string "$bstr" --build-number "$bnum" \
                 --config-string "$cstr" --default-channel "$def" --channel-alias "$cha" \
                 --repo-token "$rtk" --other-settings other_settings_test.yaml --pepper)
        echo "$output"
        echo "--------"
        [ -f "$fdir/$fname" ] || exit 1
        mv "$fdir/$fname" "$fpath"
        cached_pkgs="$cached_pkgs $fpath"
        conda index "$CONDA_PREFIX/conda-bld"
    fi

    if [ "$mode" = "--build-only" ]; then
        continue
    fi

    cached_pkgs="$cached_pkgs $pkgs_dir/$fbase $pkgs_dir/pkgs/$fname"
    installed_pkgs="testpkg"
    conda search --override-channels -c local testpkg
    cmd=(conda install "local::testpkg=$ver=${bstr}_$bnum")
    echo "${cmd[*]}"
    CONDA_ALWAYS_YES=true "${cmd[@]}" </dev/null
    ftest=$CONDA_PREFIX/condarc.d/anaconda_ident.yml
    all_content=$(cat "$ftest" 2>/dev/null || :)
    all_config=$(conda config --show || :)
    echo "--------"

    echo "Verifying contents"
    if [ -z "$all_content" ]; then
        echo "ERROR: file not found: $ftest"
        exit 1
    fi
    echo "$all_content"
    cstr_cfg=$(echo "$all_config" | grep -E '^anaconda_ident:' || :)
    if [[ "$cstr_cfg" != "anaconda_ident: ${cstr}:"* ]]; then
        echo "EXPECTED: anaconda_ident: ${cstr}:..."
        echo "FOUND: ${cstr_cfg}"
        echo "ERROR: config string not set properly"
        exit 1
    fi
    cstr_cfg=$(echo "$all_config" | grep -E '^anaconda_heartbeat:' || :)
    if [ -z "$cha" ]; then eval="True"; else eval="${cha}/main/"; fi
    if [[ "$cstr_cfg" != "anaconda_heartbeat: $eval"* ]]; then
        echo "EXPECTED: anaconda_heartbeat: ${cha}/main/..."
        echo "FOUND: ${cstr_cfg}"
        echo "ERROR: heartbeat string not set correctly"
        exit 1
    fi
    info_test=$(echo "$all_config" | grep -E '^(register_envs|repodata_use_zst):' | sort)
    if [ "$info_test" != "$info_new" ]; then
        # shellcheck disable=SC2001
        echo "$info_new" | sed 's@^@EXPECTED: @'
        echo "$info_test" | sed 's@^@FOUND: @'
        echo "ERROR: additional settings were not included"
        exit 1
    fi
    echo "--------"

    if [ -n "$rtk" ]; then
        echo "Verifying repo tokens"
        repo_tok=$(echo "$all_config" | sed '1,/^repo_tokens/d;/^[^ ]/,$d;s/^ *//')
        echo "$repo_tok"
        if [ -z "$repo_tok" ]; then
            echo "ERROR: repo tokens not included"
            exit 1
        fi
        repo_chan=$(echo "$repo_tok" | sed -E 's@(.*):.*@\1@')
        repo_chan=${repo_chan%/}/main
        repo_val=$(echo "$repo_tok" | sed -E 's@.*: *(.*)@\1@')
        cmd=(proxyspy --return-code 404 -- conda search --override-channels -c "$repo_chan" testpackage)
        echo "${cmd[*]}"
        repo_logs=$("${cmd[@]}" 2>/dev/null || :)
        token_host=$(echo "$repo_logs" | sed -nE 's@.* CONNECT ([^:]*).*@\1@p' | head -1)
        token_val=$(echo "$repo_logs" | sed -nE 's@.* GET /t/([^/]*).*@\1@p' | head -1)
        if [[ "$repo_chan" != */$token_host/* || "$token_val" != "$repo_val" ]]; then
            echo "ERROR: '$token_host' / '$token_val'"
            exit 1
        fi
        echo "--------"
    fi

    # This corrupts the package cache as a way to test that the files were
    # copied, not hard linked, to the environment
    echo "Verifying copies, not links"
    fn="${pkgs_dir}/$fbase/condarc.d/anaconda_ident.yml"
    if [ ! -f "$fn" ]; then echo "package cache file not found: $fn"; exit 1; fi
    fpath="${CONDA_PREFIX}/condarc.d/anaconda_ident.yml"
    if [ ! -f "$fpath" ]; then echo "environment file not found: $fpath"; exit 1; fi
    echo "$fn -> $fpath"
    echo "corrupted: true" >> "$fn"
    if grep "^corrupted" "$fpath"; then echo "config file linked"; exit 1; fi
    echo "--------"

    conda list | grep -q ^testpkg || exit 1
    CONFIG_STRING="$cstr" DEFAULT_CHANNELS="$def" \
        CHANNEL_ALIAS="$cha" REPO_TOKEN="$rtk" \
        ANACONDA_IDENT_DEBUG=1 SKIP_INSTALL=1 python "$SCRIPTDIR"/test_config.py

    do_cleanup
done
