#!/bin/bash

set -e

echo "Environment tester"
echo "------------------------"
T_PREFIX=$(cd $1 && pwd); shift
echo "prefix ... $T_PREFIX"

echo -n "python ... "
T_PYTHON_WIN=$T_PREFIX/python.exe
T_PYTHON_UNX=$T_PREFIX/bin/python
if [ -x $T_PYTHON_WIN ]; then
  T_PYTHON=$T_PYTHON_WIN
elif [ -x $T_PYTHON_UNX ]; then
  T_PYTHON=$T_PYTHON_UNX
fi
if [ -z "$T_PYTHON" ]; then
  echo "MISSING"
  exit -1
fi
echo $T_PYTHON

if [ -z "$1" ]; then
  expected="community"
else
  expected="commercial"
  repo_token=$1; shift
  echo "token: ${repo_token:0:6}..."
  echo "------------------------"
fi
success=yes

echo
cmd="$T_PYTHON -m anaconda_ident.install --status"
echo "\$ $cmd"
status=$($cmd)
echo "$status"
edition=$(echo "$status" | sed -nE 's@.*: ([^ ]+) edition$@\1@p')

echo
cmd="$T_PYTHON -m conda info"
echo "\$ $cmd"
echo "------------------------"
cinfo=$($cmd)
echo "$cinfo" | grep -vE '^ *$'
echo "------------------------"

echo
cmd="$T_PYTHON -m conda list"
echo "\$ $cmd"
echo "------------------------"
pkgs=$($cmd)
echo "$pkgs" | grep -vE '^ *$'
echo "------------------------"

echo
echo -n "correct prefix ... "
test_prefix=$(echo "$status" | sed -nE 's@ *conda prefix: @@p')
# For windows this converts the prefix to posix
test_prefix=$(cd $test_prefix && pwd)
if [ "$test_prefix" = "$T_PREFIX" ]; then
  echo "yes"
else
  echo "NO"
  success=no
fi

echo -n "correct edition ... "
if [ "$edition" = $expected ]; then
  echo "yes"
else
  echo "NO: $edition != $expected"
  success=no
fi

if [ "$edition" = community ]; then
  echo -n "confirming anonymity ... "
  if $T_PYTHON -c "from anaconda_ident import pro" 2>/dev/null; then
    echo "NO: pro code found"
    success=no
  else
    echo "yes: pro code absent"
  fi
fi

echo -n "enabled ... "
cntE=$(echo "$status" | grep "^. status: ENABLED" | wc -l | sed 's@ @@g')
cntD=$(echo "$status" | grep "^. status: DISABLED" | wc -l | sed 's@ @@g')
if [ "$expected" = commercial ]; then
  expE=3; expD=0
else
  expE=1; expD=2
fi
if [[ $cntE == $expE && $cntD == $expD ]]; then
  echo "yes ($cntE enabled, $cntD disabled)"
else
  echo "NO ($cntE enabled, $cntD disabled)"
  success=no
fi

echo -n "user agent ... "
user_agent=$(echo "$cinfo" | sed -nE 's@.*user-agent : (.*)@\1@p')
if [ "$expected" = commercial ]; then
    expU='ident/pro.*o/installertest'
else
    expU=ident/
fi
if echo "$user_agent" | grep -q "$expU"; then
  echo "yes"
else
  echo "NO: $user_agent"
  success=no
fi

if [ $expected = commercial ]; then
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
fi

if [ "$success" = yes ]; then
  echo "success!"
  exit 0
else
  echo "one or more errors detected"
  exit -1
fi
