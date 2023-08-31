#!/bin/bash

"${PREFIX}/bin/python" -m pip install --no-deps --ignore-installed -vv .
mkdir -p "${PREFIX}/etc/conda/activate.d"
mkdir -p "${PREFIX}/python-scripts"
cp "${RECIPE_DIR}/post-link.sh" "${PREFIX}/etc/conda/activate.d/${PKG_NAME}_activate.sh"
cp "${RECIPE_DIR}/post-link.bat" "${PREFIX}/etc/conda/activate.d/${PKG_NAME}_activate.bat"
cp "${RECIPE_DIR}/post-link.bat" "${PREFIX}/python-scripts/.${PKG_NAME}-post-link.bat"
cp "${RECIPE_DIR}/pre-unlink.bat" "${PREFIX}/python-scripts/.${PKG_NAME}-pre-unlink.bat"
