#!/bin/bash
"${PREFIX}/bin/python" -m pip install --no-deps --ignore-installed -vv .
mkdir -p "${PREFIX}/etc/conda/activate.d"
cp "scripts/activate.sh" "${PREFIX}/etc/conda/activate.d/${PKG_NAME}_activate.sh"
if [ "$SUBDIR" = "noarch" ]; then sdir=python-scripts; else sdir=bin; fi
mkdir -p "${PREFIX}/${sdir}"
cp "scripts/post-link.sh" "${PREFIX}/${sdir}/.${PKG_NAME}-post-link.sh"
cp "scripts/pre-unlink.sh" "${PREFIX}/${sdir}/.${PKG_NAME}-pre-unlink.sh"
if [ "$SUBDIR" = "noarch" ]; then
    cp "scripts/activate.bat" "${PREFIX}/etc/conda/activate.d/${PKG_NAME}_activate.bat"
    cp "scripts/post-link.bat" "${PREFIX}/${sdir}/.${PKG_NAME}-post-link.bat"
    cp "scripts/pre-unlink.bat" "${PREFIX}/${sdir}/.${PKG_NAME}-pre-unlink.bat"
fi
