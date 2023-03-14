setlocal EnableDelayedExpansion
%PREFIX%\python.exe -m pip install --no-deps --ignore-installed -vv .
%PREFIX%\python.exe -m conda_ident.install --client-token "%CLIENT_TOKEN%" --default-channel "%REPO_URL%" --repo-token "%REPO_TOKEN%" --set-condarc --ignore-missing
if not exist %PREFIX%\etc\conda\activate.d mkdir %PREFIX%\etc\conda\activate.d
copy %RECIPE_DIR%\post-link.bat %PREFIX%\etc\conda\activate.d\%PKG_NAME%_activate.bat
