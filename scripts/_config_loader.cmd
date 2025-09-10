@echo off
setlocal enabledelayedexpansion

:: Path to the config file (assuming it's one level up from the script's directory)
set "CONFIG_FILE=%~dp0..\config.ini"
if not exist "%CONFIG_FILE%" exit /b 1

set "IN_WIN_SECTION=0"

for /f "usebackq delims=" %%L in ("%CONFIG_FILE%") do (
    set "LINE=%%L"

    if "!LINE!"=="[paths_win]" (
        set "IN_WIN_SECTION=1"
    ) else (
        if "!LINE:~0,1!"=="[" set "IN_WIN_SECTION=0"
    )

    if !IN_WIN_SECTION! equ 1 (
        for /f "tokens=1,* delims==" %%A in ("!LINE!") do (
            set "KEY=%%A"
            set "VALUE=%%B"
            
            for /f "tokens=* delims= " %%K in ("!KEY!") do set "TRIMMED_KEY=%%K"
            for /f "tokens=* delims= " %%V in ("!VALUE!") do set "TRIMMED_VALUE=%%V"
            
            :: If a valid key was found, simply print the command to be executed
            if defined TRIMMED_KEY (
                echo CFG_!TRIMMED_KEY!=!TRIMMED_VALUE!
            )
        )
    )
)

exit /b 0