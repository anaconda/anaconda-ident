pfx=${CONDA_PREFIX:-${PREFIX:-}}
"$pfx/bin/python" -m conda_ident.install --disable >>"${pfx}/.messages.txt" 2>&1