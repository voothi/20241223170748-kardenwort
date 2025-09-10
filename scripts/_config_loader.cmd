@echo off
setlocal enabledelayedexpansion

:: Path to the config file (assuming it's one level up from the script's directory)
set "CONFIG_FILE=%~dp0..\config.ini"

if not exist "%CONFIG_FILE%" (
    echo ERROR: Config file not found at "%CONFIG_FILE%" >&2
    exit /b 1
)

:: Flag to check if we are inside the correct [paths_win] section
set "IN_WIN_SECTION=0"

:: Read the config file line by line
for /f "usebackq delims=" %%L in ("%CONFIG_FILE%") do (
    set "LINE=%%L"

    :: Check if we are entering the [paths_win] section
    if "!LINE!"=="[paths_win]" (
        set "IN_WIN_SECTION=1"
    ) else (
        :: Check if we are entering another section, which means [paths_win] ended
        if "!LINE:~0,1!"=="[" (
            set "IN_WIN_SECTION=0"
        )
    )

    :: If we are in the correct section, parse the key=value pairs
    if !IN_WIN_SECTION! equ 1 (
        for /f "tokens=1,* delims==" %%A in ("!LINE!") do (
            set "KEY=%%A"
            set "VALUE=%%B"
            
            :: Trim leading/trailing whitespace from KEY
            for /f "tokens=* delims= " %%K in ("!KEY!") do set "TRIMMED_KEY=%%K"
            
            :: Trim leading whitespace from VALUE
            for /f "tokens=* delims= " %%V in ("!VALUE!") do set "TRIMMED_VALUE=%%V"
            
            :: Set environment variables with a prefix, e.g., CFG_python_path
            endlocal & set "CFG_!TRIMMED_KEY!=!TRIMMED_VALUE!"
        )
    )
)

goto :eof