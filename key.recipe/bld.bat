setlocal EnableDelayedExpansion
echo "CREATING THE LICENSE KEY"
%PREFIX%\python.exe -m conda_ident.install --config "%CONFIG_STRING%" --default-channel "%DEFAULT_CHANNELS%" --channel-alias "%CHANNEL_ALIAS%" --repo-token "%REPO_TOKEN%" --ignore-missing
%PREFIX%\python.exe %SRC_DIR%\tests\test_config.py
