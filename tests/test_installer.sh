#!/bin/bash

set -e

SCRIPTDIR=$(cd $(dirname $BASH_SOURCE[0]) && pwd)
CONDA_PREFIX=$(cd $CONDA_PREFIX && pwd)
source $CONDA_PREFIX/*/activate
# Needed to convert windows path to unix
CONDA_PREFIX=$(cd $CONDA_PREFIX && pwd)

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
  - anaconda-ident
  - anaconda-client
  - conda${vflag:-}
EOD
if [ ${vflag:2:2} -gt 22 ]; then
  # Install navigator only for conda 23.x
  echo "  - anaconda-navigator" >> construct.yaml
fi

cat >post_install.sh <<EOD
\${PREFIX}/bin/python -m anaconda_ident.install --enable --clear-old-token
EOD

cat >post_install.bat <<EOD
%PREFIX%\\python.exe -m anaconda_ident.install --enable --clear-old-token
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
