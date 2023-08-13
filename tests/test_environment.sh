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

echo -n "token ... "
repo_token=$1; shift
if [ -z "$repo_token" ]; then
  echo "MISSING"
  exit -1
fi
echo "${repo_token:0:6}..."
success=yes
echo "------------------------"

echo
cmd="$T_PYTHON -m anaconda_ident.install --status"
echo "\$ $cmd"
status=$($cmd)
echo "$status"

echo
cmd="$T_PYTHON -m conda info"
echo "\$ $cmd"
echo "------------------------"
cinfo=$($cmd)
echo "$cinfo" | grep -vE '^ *$'
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

echo -n "enabled ... "
if echo "$status" | grep -xq "current conda status: ENABLED"; then
  echo "yes"
else
  echo "NO"
  success=no
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
conda_token=$($T_PYTHON -c 'from conda.gateways.connection.session import CondaHttpAuth;print(CondaHttpAuth.add_binstar_token("'$url'"))')
if echo "$conda_token" | grep -q "/t/$repo_token/"; then
  echo "yes"
else
  echo "NO: $conda_token"
  success=no
fi

echo -n "token in binstar ... "
url=https://repo.anaconda.cloud/repo/
binstar_token=$($T_PYTHON -c 'from binstar_client.utils.config import load_token;print(load_token("'$url'"))')
if [ "$binstar_token" = "$repo_token" ]; then
  echo "yes"
else
  echo "NO: $binstar_token"
  success=no
fi

echo -n "user agent ... "
user_agent=$($T_PYTHON -m conda info | sed -nE 's@.*user-agent : (.*)@\1@p')
if echo "$user_agent" | grep -q o/installertest; then
  echo "yes"
else
  echo "NO: $user_agent"
fi

if [ "$success" = yes ]; then
  echo "success!"
  exit 0
else
  echo "one or more errors detected"
  exit -1
fi
