#!/bin/bash

"${PREFIX}/bin/python" -m pip install --no-deps --ignore-installed -vv .
mkdir -p "${PREFIX}/etc/conda/activate.d"
mkdir -p "${PREFIX}/python-scripts"
cp "scripts/activate.sh" "${PREFIX}/etc/conda/activate.d/${PKG_NAME}_activate.sh"
cp "scripts/activate.bat" "${PREFIX}/etc/conda/activate.d/${PKG_NAME}_activate.bat"
cp "scripts/post-link.bat" "${PREFIX}/python-scripts/.${PKG_NAME}-post-link.bat"
cp "scripts/pre-unlink.bat" "${PREFIX}/python-scripts/.${PKG_NAME}-pre-unlink.bat"
