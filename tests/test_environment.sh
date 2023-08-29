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
  success=yes
else
  echo "NO"
  success=no
fi

echo -n "enabled ... "
if echo "$status" | grep -q "status: ENABLED"; then
  echo "yes"
else
  echo "NO"
  success=no
fi

echo -n "user agent ... "
user_agent=$(echo "$cinfo" | sed -nE 's@.*user-agent : (.*)@\1@p')
if echo "$user_agent" | grep -q "ident/.* c/.* s/.* e/"; then
  echo "yes"
else
  echo "NO: $user_agent"
  success=no
fi

if [ "$success" = yes ]; then
  echo "success!"
  exit 0
else
  echo "one or more errors detected"
  exit -1
fi
