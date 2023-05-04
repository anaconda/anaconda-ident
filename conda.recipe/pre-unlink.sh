pfx=${CONDA_PREFIX:-${PREFIX:-}}
pbin=${pfx}/python.exe
[ -f ${pbin} ] || pbin=${pfx}/bin/python
${pbin} -m anaconda_ident.install --disable --quiet >>"${pfx}/.messages.txt" 2>&1
