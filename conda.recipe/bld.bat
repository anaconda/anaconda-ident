setlocal EnableDelayedExpansion
%PREFIX%\python.exe -m pip install --no-deps --ignore-installed -vv .
%PREFIX%\python.exe -m conda_ident.install --config "%CONFIG_STRING%" --default-channel "%DEFAULT_CHANNELS%" --channel-alias "%CHANNEL_ALIAS%" --token "%REPO_TOKEN%" --set-condarc --ignore-missing
if not exist %PREFIX%\etc\conda\activate.d mkdir %PREFIX%\etc\conda\activate.d
copy %RECIPE_DIR%\post-link.bat %PREFIX%\etc\conda\activate.d\%PKG_NAME%_activate.bat
