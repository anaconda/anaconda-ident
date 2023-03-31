"${PREFIX}/bin/python" -m pip install --no-deps --ignore-installed -vv .
mkdir -p "${PREFIX}/etc/conda/activate.d"
cp "${RECIPE_DIR}/post-link.sh" "${PREFIX}/etc/conda/activate.d/${PKG_NAME}_activate.sh"
