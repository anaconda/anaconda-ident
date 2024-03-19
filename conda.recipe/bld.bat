setlocal EnableDelayedExpansion
%PREFIX%\python.exe -m pip install --no-deps --ignore-installed -vv . --no-build-isolation
if not exist %PREFIX%\etc\conda\activate.d mkdir %PREFIX%\etc\conda\activate.d
if not exist %PREFIX%\Scripts mkdir %PREFIX%\Scripts
copy scripts\activate.sh %PREFIX%\etc\conda\activate.d\%PKG_NAME%_activate.sh
copy scripts\post-link.sh %PREFIX%\Scripts\.%PKG_NAME%-post-link.sh
copy scripts\pre-unlink.sh %PREFIX%\Scripts\.%PKG_NAME%-pre-unlink.sh
copy scripts\activate.bat %PREFIX%\etc\conda\activate.d\%PKG_NAME%_activate.bat
copy scripts\pre-unlink.bat %PREFIX%\Scripts\.%PKG_NAME%-pre-unlink.bat
copy scripts\post-link.bat %PREFIX%\Scripts\.%PKG_NAME%-post-link.bat
