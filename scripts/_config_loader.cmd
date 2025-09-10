@echo off
setlocal

:: Path to the config file (assuming it's one level up from the script's directory)
set "CONFIG_FILE=%~dp0..\config.ini"
if not exist "%CONFIG_FILE%" exit /b 1

set "IN_WIN_SECTION=0"
for /f "usebackq delims=" %%L in ("%CONFIG_FILE%") do (
    set "LINE=%%L"
    call :ProcessLine
)
exit /b 0

:ProcessLine
if "%LINE%"=="[paths_win]" set "IN_WIN_SECTION=1" & goto :eof
if "%LINE%"=="[paths_nix]" set "IN_WIN_SECTION=0" & goto :eof

if %IN_WIN_SECTION% neq 1 goto :eof

:: The most robust way to parse "key = value"
for /f "tokens=1,* delims== " %%A in ("%LINE%") do (
    :: Check to ensure it's not a comment or empty line
    if not "%%A"=="" if not "%%A"==";" (
        echo CFG_%%A=%%B
    )
)
goto :eof