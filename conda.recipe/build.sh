#!/bin/bash
"${PREFIX}/bin/python" -m pip install --no-deps --ignore-installed -vv .
mkdir -p "${PREFIX}/etc/conda/activate.d"
cp "scripts/activate.sh" "${PREFIX}/etc/conda/activate.d/${PKG_NAME}_activate.sh"
mkdir -p "${PREFIX}/python-scripts"
cp "scripts/post-link.sh" "${PREFIX}/python-scripts/.${PKG_NAME}-post-link.sh"
cp "scripts/pre-unlink.sh" "${PREFIX}/python-scripts/.${PKG_NAME}-pre-unlink.sh"
