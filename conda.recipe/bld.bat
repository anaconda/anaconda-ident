setlocal EnableDelayedExpansion
%PREFIX%\python.exe -m pip install --no-deps --ignore-installed -vv .
if not exist %PREFIX%\etc\conda\activate.d mkdir %PREFIX%\etc\conda\activate.d
copy scripts\activate.bat %PREFIX%\etc\conda\activate.d\%PKG_NAME%_activate.bat
copy scripts\activate.sh %PREFIX%\etc\conda\activate.d\%PKG_NAME%_activate.sh
if not exist %PREFIX%\Scripts mkdir %PREFIX%\Scripts
copy scripts\post-link.bat %PREFIX%\Scripts\.%PKG_NAME%-post-link.bat
copy scripts\pre-unlink.bat %PREFIX%\Scripts\.%PKG_NAME%-pre-unlink.bat
if not exist %PREFIX%\bin mkdir %PREFIX%\bin
copy scripts\post-link.sh %PREFIX%\bin\.%PKG_NAME%-post-link.sh
copy scripts\pre-unlink.sh %PREFIX%\bin\.%PKG_NAME%-pre-unlink.sh
