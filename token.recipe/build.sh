#! /bin/bash
"${PREFIX}/bin/python" -m conda_ident.install --config "${CONFIG_STRING}" --default-channel "${DEFAULT_CHANNELS}" --channel-alias "${CHANNEL_ALIAS}" --repo-token "${REPO_TOKEN}"
"${PREFIX}/bin/python" ${SRC_DIR}/conda.recipe/run_test.py
