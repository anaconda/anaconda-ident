"${PREFIX}/bin/python" -m pip install --no-deps --ignore-installed -vv .
"${PREFIX}/bin/python" -m conda_ident.install --config "${CONFIG_STRING}" --default-channel "${DEFAULT_CHANNELS}" --channel-alias "${CHANNEL_ALIAS}" --token "${REPO_TOKEN}" --set-condarc --ignore-missing
mkdir -p "${PREFIX}/etc/conda/activate.d"
cp "${RECIPE_DIR}/post-link.sh" "${PREFIX}/etc/conda/activate.d/${PKG_NAME}_activate.sh"
