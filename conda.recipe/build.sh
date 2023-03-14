"${PREFIX}/bin/python" -m pip install --no-deps --ignore-installed -vv .
"${PREFIX}/bin/python" -m conda_ident.install --client-token "${CLIENT_TOKEN}" --default-channel "${REPO_URL}" --repo-token "${REPO_TOKEN}" --set-condarc
mkdir -p "${PREFIX}/etc/conda/activate.d"
cp "${RECIPE_DIR}/post-link.sh" "${PREFIX}/etc/conda/activate.d/${PKG_NAME}_activate.sh"
