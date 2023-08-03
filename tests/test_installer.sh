#!/bin/bash

set -e

SCRIPTDIR=$(cd $(dirname $BASH_SOURCE[0]) && pwd)
vflag=$1; shift
source $CONDA_PREFIX/*/activate

SITE=https://repo.anaconda.cloud
ALIAS=$SITE/repo
anaconda-keymgr --version 999 --repo-token $TEST_REPO_TOKEN \
    --default-channel $ALIAS/main --default-channel $ALIAS/msys2 \
    --config-string full:installertest
mkdir -p $CONDA_PREFIX/conda-bld/noarch
mv anaconda-ident-config-999-default_0.tar.bz2 $CONDA_PREFIX/conda-bld/noarch
python -m conda_index $CONDA_PREFIX/conda-bld

TMPDIR=$(mktemp -d)
trap 'rm -rf -- "$TMPDIR"' EXIT
echo $TMPDIR
cd $TMPDIR

[ -z "$vflag" ] || vflag="==$vflag"

cat >construct.yaml <<EOD
name: AIDTest
version: 1.0
installer_type: all
channels:
  - local
  - defaults
post_install: post_install.bat # [win]
post_install: post_install.sh # [not win]
specs:
  - anaconda-ident-config
  - anaconda-client
  - conda${vflag:-}
EOD

cat >post_install.sh <<EOD
\${PREFIX}/bin/python -m anaconda_ident.install --enable --write-token --quiet
EOD

cat >post_install.bat <<EOD
%PREFIX%\\python.exe -m anaconda_ident.install --enable --write-token --quiet
EOD

echo "-----"
cat construct.yaml
echo "-----"
cat post_install.bat
echo "-----"
cat post_install.sh
echo "-----"

constructor .

T_PREFIX=$TMPDIR/aidtest
[ -f AIDTest*.sh ] || exit 0
bash AIDTest*.sh -b -p $T_PREFIX -k
. $SCRIPTDIR/test_environment.sh "$T_PREFIX" "$TEST_REPO_TOKEN"
