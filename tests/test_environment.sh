#!/bin/bash

set -o errtrace -o nounset -o pipefail -o errexit

success=yes
function finish() {
  if [ "$success" = yes ]; then
    echo "success!"
    exit 0
  else
    echo "one or more errors detected"
    exit 1
  fi
}

echo "Environment tester"
echo "------------------------"
T_PREFIX=$(cd "$1" && pwd); shift
echo "prefix ... $T_PREFIX"

echo -n "python ... "
T_PYTHON_WIN=$T_PREFIX/python.exe
T_PYTHON_UNX=$T_PREFIX/bin/python
if [ -x "$T_PYTHON_WIN" ]; then
  T_PYTHON=$T_PYTHON_WIN
elif [ -x "$T_PYTHON_UNX" ]; then
  T_PYTHON=$T_PYTHON_UNX
fi
if [ -z "$T_PYTHON" ]; then
  echo "MISSING"
  exit 1
fi
echo "$T_PYTHON"

echo -n "sp_dir ... "
T_SPDIR=$($T_PYTHON -c "import sysconfig;print(sysconfig.get_paths()['purelib'])")
echo "$T_SPDIR"

echo -n "token ... "
repo_token=${1:-}
if [ -z "$repo_token" ]; then
  echo "NOT SUPPLIED"
else
  echo "${repo_token:0:6}..."
fi
echo "------------------------"
cnd_v=$($T_PYTHON -c "from conda import __version__;print(__version__)")
echo "conda: $cnd_v"
aau_v=$($T_PYTHON -c "from anaconda_anon_usage import __version__;print(__version__)")
echo "anaconda_anon_usage: $aau_v"
aid_v=$($T_PYTHON -c "from anaconda_ident import __version__;print(__version__)")
echo "anaconda_ident: $aid_v"
pver1=$(sed -nE 's@^# anaconda_ident @@p' "$T_SPDIR/conda/base/context.py")
pver2=$(sed -nE 's@^# anaconda_ident @@p' "$T_SPDIR/anaconda_anon_usage/patch.py")
pver3=$(sed -nE 's@^# anaconda_ident @@p' "$T_SPDIR/conda/gateways/anaconda_client.py")
pver4=$(sed -nE 's@^# anaconda_ident @@p' "$T_SPDIR/binstar_client/utils/config.py")
echo "| conda.base.context: $pver1"
echo "| anaconda_anon_usage: $pver2"
echo "| conda.gateways.anaconda_client: $pver3"
echo "| binstar_client.utils.config: $pver4"
echo "------------------------"
success=yes

echo
cmd="$T_PYTHON -m anaconda_ident.install --status"
echo "\$ $cmd"
status=$($cmd)
echo "$status"

echo
cmd="$T_PYTHON -m conda info"
echo "\$ $cmd"
echo "------------------------"
cinfo=$($cmd 2>&1)
echo "$cinfo" | grep -vE '^ *$'
echo "------------------------"

echo
cmd="$T_PYTHON -m conda list"
echo "\$ $cmd"
echo "------------------------"
pkgs=$($cmd 2>&1)
echo "$pkgs" | grep -vE '^ *$'
echo "------------------------"

echo
echo -n "correct prefix ... "
test_prefix=$(echo "$status" | sed -nE 's@ *conda prefix: @@p' | tail -1)
# For windows this converts the prefix to posix
test_prefix=$(cd "$test_prefix" && pwd)
if [ "$test_prefix" = "$T_PREFIX" ]; then
  echo "yes"
else
  echo "NO"
  success=no
fi

echo -n "enabled ... "
cnt=$(echo "$status" | grep -c "^. status: ENABLED")
if [ "$cnt" -ge 3 ]; then
  echo "yes"
else
  echo "NO"
  success=no
fi

echo -n "user agent ... "
user_agent=$(echo "$cinfo" | sed -nE 's@.*user-agent : (.*)@\1@p')
if echo "$user_agent" | grep -q o/installertest; then
  echo "yes"
else
  echo "NO: $user_agent"
  success=no
fi

if [ -z "$repo_token" ]; then
  finish
fi

echo -n "token in status ... "
if echo "$status" | grep -q "[:] ${repo_token:0:6}"; then
  echo "yes"
else
  echo "NO"
  success=no
fi

echo -n "token in conda ..."
url=https://repo.anaconda.cloud/repo/main/linux-64/repodata.json
conda_token=$($T_PYTHON -c 'import conda.base.context;from conda.gateways.connection.session import CondaHttpAuth;print(CondaHttpAuth.add_binstar_token("'$url'"))')
if echo "$conda_token" | grep -q "/t/$repo_token/"; then
  echo "yes"
else
  echo "NO: $conda_token"
  success=no
fi

if echo "$pkgs" | grep -q ^anaconda-client; then
  echo -n "token in binstar ... "
  url=https://repo.anaconda.cloud/repo/
  binstar_token=$($T_PYTHON -c 'from binstar_client.utils.config import load_token;print(load_token("'$url'"))')
  if [ "$binstar_token" = "$repo_token" ]; then
    echo "yes"
  else
    echo "NO: $binstar_token"
    success=no
  fi
fi

if echo "$pkgs" | grep -q ^anaconda-navigator; then
  echo -n "token in navigator ... "
  nav_token=$($T_PYTHON -c 'from anaconda_navigator.widgets.main_window.account_components import token_list;print(token_list().get("'$url'"))')
  if [ "$nav_token" = "$repo_token" ]; then
    echo "yes"
  else
    echo "NO: $nav_token"
    success=no
  fi
fi

finish
