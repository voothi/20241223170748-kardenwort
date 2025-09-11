@echo off
setlocal

:: Script to parse a specified section from a config.ini file.
:: Usage: call _config_loader.cmd [section_name]
:: It reads key-value pairs and prints them in the format: CFG_key=value

if "%~1"=="" (
    echo ERROR: No section name provided to _config_loader.cmd. >&2
    exit /b 1
)
set "TARGET_SECTION=[%~1]"

set "CONFIG_FILE=%~dp0..\config.ini"

if not exist "%CONFIG_FILE%" (
    echo ERROR: Config file not found at "%CONFIG_FILE%" >&2
    exit /b 1
)

set "IN_TARGET_SECTION=0"

for /f "usebackq delims=" %%L in ("%CONFIG_FILE%") do (
    set "LINE=%%L"
    call :ProcessLine
)

exit /b 0

:ProcessLine
    setlocal enabledelayedexpansion
    :: Standardize the line for case-insensitive comparison
    set "COMPARE_LINE=!LINE!"

    if /i "!COMPARE_LINE!"=="%TARGET_SECTION%" (
        endlocal
        set IN_TARGET_SECTION=1
        goto :eof
    )
    endlocal

    if "%LINE:~0,1%"=="[" (
        set "IN_TARGET_SECTION=0"
        goto :eof
    )

    if %IN_TARGET_SECTION% neq 1 goto :eof

    for /f "tokens=1,* delims== " %%A in ("%LINE%") do (
        if not "%%A"=="" if not "%%A"==";" (
            echo CFG_%%A=%%B
        )
    )
goto :eof