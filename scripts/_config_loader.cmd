@echo off
setlocal enabledelayedexpansion

:: Path to the config file (assuming it's one level up from the script's directory)
set "CONFIG_FILE=%~dp0..\config.ini"

if not exist "%CONFIG_FILE%" (
    echo ERROR: Config file not found at "%CONFIG_FILE%" >&2
    exit /b 1
)

:: This variable will accumulate all the set commands
set "SET_COMMANDS="

:: Flag to check if we are inside the correct [paths_win] section
set "IN_WIN_SECTION=0"

:: Read the config file line by line
for /f "usebackq delims=" %%L in ("%CONFIG_FILE%") do (
    set "LINE=%%L"

    if "!LINE!"=="[paths_win]" (
        set "IN_WIN_SECTION=1"
    ) else (
        if "!LINE:~0,1!"=="[" (
            set "IN_WIN_SECTION=0"
        )
    )

    if !IN_WIN_SECTION! equ 1 (
        for /f "tokens=1,* delims==" %%A in ("!LINE!") do (
            set "KEY=%%A"
            set "VALUE=%%B"
            
            for /f "tokens=* delims= " %%K in ("!KEY!") do set "TRIMMED_KEY=%%K"
            for /f "tokens=* delims= " %%V in ("!VALUE!") do set "TRIMMED_VALUE=%%V"
            
            :: Append the set command to our command string instead of executing it
            if defined TRIMMED_KEY (
                set "SET_COMMANDS=!SET_COMMANDS! & set "CFG_!TRIMMED_KEY!=!TRIMMED_VALUE!""
            )
        )
    )
)

:: Now, execute endlocal and the accumulated commands all at once
endlocal%SET_COMMANDS%

goto :eof