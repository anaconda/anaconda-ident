pfx=${CONDA_PREFIX:-${PREFIX:-}}
"$pfx/bin/python" -m conda_ident.install --enable >>"${pfx}/.messages.txt" 2>&1