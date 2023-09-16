#!/bin/bash

set -o errtrace -o nounset -o pipefail -o errexit

repo_token=$1; shift
version=$1; shift

CONDA_PREFIX=$(cd "$CONDA_PREFIX" && pwd)
# shellcheck disable=SC1090
source "$CONDA_PREFIX"/*/activate
# Needed to convert windows path to unix
CONDA_PREFIX=$(cd "$CONDA_PREFIX" && pwd)

SITE=https://repo.anaconda.cloud
ALIAS=$SITE/repo
python -m anaconda_ident.keymgr --version 999 \
    --repo-token "$repo_token" --config-string full:installertest \
    --default-channel $ALIAS/main --default-channel $ALIAS/msys2
mkdir -p "$CONDA_PREFIX"/conda-bld/noarch
mv anaconda-ident-config-999-default_0.tar.bz2 "$CONDA_PREFIX"/conda-bld/noarch
python -m conda_index "$CONDA_PREFIX"/conda-bld

cat >construct.yaml <<EOD
name: AIDTest
version: 1.0
installer_type: all
channels:
  - local
  - ctools
  - defaults
post_install: post_install.bat # [win]
post_install: post_install.sh # [not win]
specs:
  - anaconda-ident-config
  - anaconda-client
  - conda==${version}
EOD

if [ "$(echo "$version" | cut -d '.' -f 1)" -ge 23 ]; then
  # Install navigator only for conda 23.x
  echo "  - anaconda-navigator" >>construct.yaml
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

if compgen -G "AIDTest*.sh" >/dev/null; then
  echo ".sh installer created"
elif compgen -G "AIDTest*.exe" >/dev/null; then
  echo ".exe installer created"
else
  echo "No testable installer created"
  exit 1
fi
