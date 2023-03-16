pfx=${CONDA_PREFIX:-${PREFIX:-}}
"$pfx/bin/python" -m conda_ident.install --clean --quiet >>"${pfx}/.messages.txt" 2>&1
