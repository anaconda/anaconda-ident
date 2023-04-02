setlocal EnableDelayedExpansion
%PREFIX%\python.exe -m pip install --no-deps --ignore-installed -vv .
if not exist %PREFIX%\etc\conda\activate.d mkdir %PREFIX%\etc\conda\activate.d
if not exist %PREFIX%\python-scripts mkdir %PREFIX%\python-scripts
copy %RECIPE_DIR%\post-link.bat %PREFIX%\etc\conda\activate.d\%PKG_NAME%_activate.bat
copy %RECIPE_DIR%\post-link.sh %PREFIX%\etc\conda\activate.d\%PKG_NAME%_activate.sh
copy %RECIPE_DIR%\post-link.sh %PREFIX%\python-scripts\.%PKG_NAME%-post-link.sh
copy %RECIPE_DIR%\pre-unlink.sh %PREFIX%\etc\conda\activate.d\.%PKG_NAME%-pre-unlink.sh
