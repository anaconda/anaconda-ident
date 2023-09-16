setlocal EnableDelayedExpansion
%PREFIX%\python.exe -m pip install --no-deps --ignore-installed -vv .
if not exist %PREFIX%\etc\conda\activate.d mkdir %PREFIX%\etc\conda\activate.d
if not exist %PREFIX%\python-scripts mkdir %PREFIX%\python-scripts
copy scripts\activae.bat %PREFIX%\etc\conda\activate.d\%PKG_NAME%_activate.bat
copy scripts\activate.sh %PREFIX%\etc\conda\activate.d\%PKG_NAME%_activate.sh
copy scripts\post-link.sh %PREFIX%\python-scripts\.%PKG_NAME%-post-link.sh
copy scripts\pre-unlink.sh %PREFIX%\etc\conda\activate.d\.%PKG_NAME%-pre-unlink.sh
