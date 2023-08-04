#!/bin/bash

set -e

if [ -z "TEST_REPO_TOKEN" ]; then
  echo "TEST_REPO_TOKEN must be set"
  exit -1
fi
SCRIPTDIR=$(cd $(dirname $BASH_SOURCE[0]) && pwd)
CONDA_PREFIX=$(cd $CONDA_PREFIX && pwd)
if [ ! -z $1 ]; then vflag="==$1"; shift; fi
source $CONDA_PREFIX/*/activate
# Needed to convert windows path to unix
CONDA_PREFIX=$(cd $CONDA_PREFIX && pwd)

SITE=https://repo.anaconda.cloud
ALIAS=$SITE/repo
python -m anaconda_ident.keymgr --version 999 \
    --repo-token $TEST_REPO_TOKEN --config-string full:installertest \
    --default-channel $ALIAS/main --default-channel $ALIAS/msys2
mkdir -p $CONDA_PREFIX/conda-bld/noarch
mv anaconda-ident-config-999-default_0.tar.bz2 $CONDA_PREFIX/conda-bld/noarch
python -m conda_index $CONDA_PREFIX/conda-bld

if [ -z "$TMPDIR" ]; then
  TMPDIR=$(mktemp -d)
  trap 'rm -rf -- "$TMPDIR"' EXIT
else
  TMPDIR=$(cd $TMPDIR && pwd)
fi
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

if [ -f AIDTest*.sh ]; then
  T_PREFIX=$TMPDIR/aidtest
  echo "Running the .sh installer..."
  bash AIDTest*.sh -b -p $T_PREFIX -k
elif [ -f AIDTest*.exe ]; then
  echo "Running the .exe installer..."
  cmd.exe /c "$(ls -1 AIDTest*.exe) /S"
  echo "Installer has been run"
  W_PREFIX="$USERPROFILE\\aidtest"
  T_PREFIX=$(cd "$W_PREFIX" && pwd)
else
  echo "No installer created"
  exit -1
fi
. $SCRIPTDIR/test_environment.sh "$T_PREFIX" "$TEST_REPO_TOKEN"
if [ ! -z "$W_PREFIX" ]; then
  echo "Running the .exe uninstaller"
  cmd.exe /c "$W_PREFIX\\Uninstall-AIDTest.exe /S"
fi
echo "success .. $success"
if [ "$success" = yes ]; then
  exit 0
else
  exit -1
fi
