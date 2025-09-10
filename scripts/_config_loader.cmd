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
        :: This is the final, robust parsing logic.
        :: It treats both space and equals sign as delimiters.
        for /f "tokens=1,* delims== " %%A in ("!LINE!") do (
            :: Check to ensure it's not a comment or empty line
            if not "%%A"=="" if not "%%A"==";" (
                echo CFG_%%A=%%B
            )
        )
    )
)

exit /b 0