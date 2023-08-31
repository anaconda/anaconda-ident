#!/bin/bash

set -e

vflag="==$1"; shift
repo_token=$1; shift

SCRIPTDIR=$(cd $(dirname $BASH_SOURCE[0]) && pwd)
CONDA_PREFIX=$(cd $CONDA_PREFIX && pwd)
source $CONDA_PREFIX/*/activate
# Needed to convert windows path to unix
CONDA_PREFIX=$(cd $CONDA_PREFIX && pwd)

if [ -z "$repo_token" ]; then
  EDITION=base
  CLEAR_FLAG=
else
  EDITION=pro
  CLEAR_FLAG="--clear-old-token"
  SITE=https://repo.anaconda.cloud
  ALIAS=$SITE/repo
  python -m anaconda_ident.keymgr --version 999 \
      --repo-token $repo_token --config-string full:installertest \
      --default-channel $ALIAS/main --default-channel $ALIAS/msys2
  mkdir -p $CONDA_PREFIX/conda-bld/noarch
  mv anaconda-ident-config-999-default_0.tar.bz2 $CONDA_PREFIX/conda-bld/noarch
  python -m conda_index $CONDA_PREFIX/conda-bld
fi

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
  - anaconda-client
  - conda${vflag:-}
  - anaconda-ident=*=${EDITION}_*
EOD
if [ $EDITION = pro ]; then
  echo "  - anaconda-ident-config" >> construct.yaml
fi
if [ ${vflag:2:2} -gt 22 ]; then
  # Install navigator only for conda 23.x
  echo "  - anaconda-navigator" >> construct.yaml
fi

cat >post_install.sh <<EOD
\${PREFIX}/bin/python -m anaconda_ident.install --enable ${CLEAR_FLAG}
EOD

cat >post_install.bat <<EOD
%PREFIX%\\python.exe -m anaconda_ident.install --enable ${CLEAR_FLAG}
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
  echo ".sh installer created"
elif [ -f AIDTest*.exe ]; then
  echo ".exe installer created"
else
  echo "No testable installer created"
  exit -1
fi
