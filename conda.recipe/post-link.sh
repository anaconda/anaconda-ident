pfx=${CONDA_PREFIX:-${PREFIX:-}}
"$pfx/bin/python" -m conda_ident.install --verify --quiet >>"${pfx}/.messages.txt" 2>&1
