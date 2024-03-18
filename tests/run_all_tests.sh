#! /bin/bash
set -e
export ANACONDA_IDENT_DEBUG=1
export PYTHONUNBUFFERED=1
conda create -n testchild1 --yes
conda create -n testchild2 --yes
conda info
conda info --envs
anaconda-ident --expect
anaconda-keymgr --help
python tests/test_config.py
bash tests/test_keymgr.sh "$1"
