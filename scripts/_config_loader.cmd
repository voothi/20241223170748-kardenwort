@echo off
setlocal

:: Script to parse the [paths] section from a config.ini file.
:: It reads key-value pairs and prints them in the format: CFG_key=value

:: Path to the config file (assuming it's one level up from the script's directory)
set "CONFIG_FILE=%~dp0..\config.ini"

:: Check if the config file exists
if not exist "%CONFIG_FILE%" (
    echo ERROR: Config file not found at "%CONFIG_FILE%" >&2
    exit /b 1
)

:: This variable will act as a flag. 0 = not in section, 1 = in section.
set "IN_PATHS_SECTION=0"

:: Read the config file line by line
for /f "usebackq delims=" %%L in ("%CONFIG_FILE%") do (
    set "LINE=%%L"
    call :ProcessLine
)

exit /b 0


:ProcessLine
:: Check if the current line is the start of our target section '[paths]'
:: The /i switch makes the comparison case-insensitive.
if /i "%LINE%"=="[paths]" (
    set "IN_PATHS_SECTION=1"
    goto :eof
)

:: Check if the line is the start of ANY OTHER section.
:: If it is, we are no longer in the [paths] section.
:: This must be checked *after* the "[paths]" check.
if "%LINE:~0,1%"=="[" (
    set "IN_PATHS_SECTION=0"
    goto :eof
)

:: If we are not currently inside the [paths] section, skip the rest.
if %IN_PATHS_SECTION% neq 1 goto :eof

:: Parse the "key = value" line and print it.
:: This handles spaces around the '='.
for /f "tokens=1,* delims== " %%A in ("%LINE%") do (
    :: Ensure the line is not a comment (starting with ';') or empty.
    if not "%%A"=="" if not "%%A"==";" (
        echo CFG_%%A=%%B
    )
)
goto :eof