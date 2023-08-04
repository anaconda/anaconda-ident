#!/bin/bash
echo -n "installed python ... "
T_PREFIX=$(cd $1 && pwd); shift
TEST_REPO_TOKEN=$1; shift
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
  success=no
else
  echo $T_PYTHON
  success=yes
fi
status=$($T_PYTHON -m anaconda_ident.install --status)
echo "$status"
cinfo=$($T_PYTHON -m conda info)
echo "$cinfo" | grep -vE '^ *$'
echo "------"
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
if echo "$status" | grep -xq "current status: ENABLED"; then
  echo "yes"
else
  echo "NO"
  success=no
fi
echo -n "repo token ... "
if echo "$status" | grep -q "[:] ${TEST_REPO_TOKEN:0:6}"; then
  echo "yes"
else
  echo "NO"
  success=no
fi
echo -n "binstar token ... "
binstar_token=$($T_PYTHON -c 'from binstar_client.utils.config import load_token;print(load_token("https://repo.anaconda.cloud/"))')
if [ "$binstar_token" = "$TEST_REPO_TOKEN" ]; then
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
