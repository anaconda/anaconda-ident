setlocal EnableDelayedExpansion
%PREFIX%\python.exe -m pip install --no-deps --ignore-installed -vv .
if "%CLIENT_TOKEN%" NEQ "" echo %CLIENT_TOKEN% > %SP_DIR%\conda_indent\client_token
if not exist %PREFIX%\etc\conda\activate.d mkdir %PREFIX%\etc\conda\activate.d
copy %RECIPE_DIR%\post-link.bat %PREFIX%\etc\conda\activate.d\%PKG_NAME%_activate.bat
