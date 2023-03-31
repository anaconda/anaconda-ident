#!/bin/bash
SCRIPTDIR=$(cd $(dirname $BASH_SOURCE[0]) && pwd)
MYTMPDIR="$(mktemp -d)"
trap 'rm -rf -- "$MYTMPDIR"' EXIT
source "$CONDA_PREFIX/etc/profile.d/conda.sh"
channels=$(conda config --show channels | grep -v ^channels | sed 's@ *- *@@' | paste -s -d ',' -)
export CONDA_CHANNELS="local,$channels"
export KEY_VERSION=$(date +%Y%m%d)
conda build -m "$SCRIPTDIR/config_tests.yaml" --croot $MYTMPDIR "$SCRIPTDIR/../key.recipe"
