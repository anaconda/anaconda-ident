@echo off
:: Set PATH explicitly as it may not be set correctly by some versions of conda
if "%CONDA_PREFIX%"=="" (set "pfx=%PREFIX%") else (set "pfx=%CONDA_PREFIX%")
set "PATH=%PATH%;%pfx%\Library\bin"
"%pfx%\python.exe" -m conda_ident.install --disable --quiet >>"%pfx%\.messages.txt" 2>&1 && if errorlevel 1 exit 1
