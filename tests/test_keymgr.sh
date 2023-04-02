#!/bin/bash

set -e

SCRIPTDIR=$(cd $(dirname $BASH_SOURCE[0]) && pwd)
source $CONDA_PREFIX/etc/profile.d/conda.sh

bnum=0
ver=$(date +%Y%m%d)
grep '|' $SCRIPTDIR/config_tests.txt | while IFS="|" read cstr def cha rtk bstr; do
    bnum=$((bnum + 1))
    echo "--------"
    echo "config string: $cstr"
    echo "default channels: $def"
    echo "channel alias: $cha"
    echo "repo token: $rtk"
    echo "build string: $bstr"
    echo "build number: $bnum"
    echo "--------"
    output=$(python -m conda_ident.keymgr \
             --name "testpkg" --version "$ver" --build-string "$bstr" --build-number "$bnum" \
             --config-string "$cstr" --default-channel "$def" --channel-alias "$cha" --repo-token "$rtk")
    echo "$output"
    echo "--------"
    fname=$(echo "$output" | tail -1)
    [ -f "$fname" ] || exit -1
    rm -rf $CONDA_PREFIX/pkgs/${fname%%.*}
    conda install -p $CONDA_PREFIX $fname --freeze-installed --offline --yes
    echo "--------"
    conda list testpkg | grep -q ^testpkg || exit -1
    CONFIG_STRING="$cstr" DEFAULT_CHANNELS="$def" \
        CHANNEL_ALIAS="$cha" REPO_TOKEN="$rtk" \
        CONDA_IDENT_DEBUG=1 SKIP_INSTALL=1 python $SCRIPTDIR/test_config.py
    conda remove -p $CONDA_PREFIX testpkg --force --offline --yes
    rm $fname
done
