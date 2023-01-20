"${PREFIX}/bin/python" -m pip install --no-deps --ignore-installed -vv .
[ -z "${CLIENT_TOKEN}" ] || echo "${CLIENT_TOKEN}" > ${SP_DIR}/conda_ident/client_token
mkdir -p "${PREFIX}/etc/conda/activate.d"
cp "${RECIPE_DIR}/post-link.sh" "${PREFIX}/etc/conda/activate.d/${PKG_NAME}_activate.sh"
