setlocal EnableDelayedExpansion
%PREFIX%/bin/python -m pip install --no-deps --ignore-installed -vv .
if not exist %PREFIX%\etc\conda\activate.d mkdir %PREFIX%\etc\conda\activate.d
copy %RECIPE_DIR%\post-link.bat %PREFIX%\etc\conda\activate.d\%PKG_NAME%_activate.bat
