@echo off
setlocal EnableDelayedExpansion

REM Set paths
set PYTHON_PATH=U:\voothi\20250825231214-spacy-env\Scripts\python.exe
set WORKSPACE=U:\voothi\20241223170748-kardenwort-kern
set SCRIPT=krdnkrt-krn-runner.py

REM Verify Python exists
if not exist "%PYTHON_PATH%" (
    echo ERROR: Python executable not found at: %PYTHON_PATH%
    exit /b 1
)

REM Change to workspace directory
cd /d "%WORKSPACE%"
if errorlevel 1 (
    echo ERROR: Failed to change directory to %WORKSPACE%
    exit /b 1
)

REM Run script for a single English text file
echo Running extraction for a single English text...

echo.
echo Single word mode...
call "%PYTHON_PATH%" "%SCRIPT%" --language en --type word --mode single
if errorlevel 1 goto :error

REM The 'sentence' mode requires at least two files ('dual' or 'triple' mode) and cannot be run in 'single' mode.

echo.
echo All operations completed successfully.
exit /b 0

:error
echo ERROR: Script failed with error level %errorlevel%
exit /b 1