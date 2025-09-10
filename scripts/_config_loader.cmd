@echo off
setlocal enabledelayedexpansion

:: Path to the config file (assuming it's one level up from the script's directory)
set "CONFIG_FILE=%~dp0..\config.ini"
if not exist "%CONFIG_FILE%" exit /b 1

set "IN_WIN_SECTION=0"
for /f "usebackq delims=" %%L in ("%CONFIG_FILE%") do (
    set "LINE=%%L"

    if "!LINE!"=="[paths_win]" ( set "IN_WIN_SECTION=1" )
    if "!LINE!"=="[paths_nix]" ( set "IN_WIN_SECTION=0" )

    if !IN_WIN_SECTION! equ 1 (
        :: Check if the line is a valid key=value pair (not a comment or section header)
        if not "!LINE!"=="" if not "!LINE:~0,1!"=="[" if not "!LINE:~0,1!"==";" (
            
            :: The most robust way to parse "key = value"
            for /f "tokens=1,* delims==" %%A in ("!LINE!") do (
                set "KEY=%%A"
                set "VALUE=%%B"

                :: Brutally remove all spaces from the key
                set "KEY=!KEY: =!"

                :: Remove the first character from the value (which is a space)
                set "VALUE=!VALUE:~1!"
                
                :: Using parentheses guarantees a newline character after each line is printed.
                (echo CFG_!KEY!=!VALUE!)
            )
        )
    )
)

exit /b 0