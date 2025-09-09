@echo off
setlocal EnableDelayedExpansion

REM Set paths
set PYTHON_PATH=C:\Users\voothi\AppData\Roaming\Anki2\addons21\spacyenv\Scripts\python.exe
set WORKSPACE=U:\voothi\20241223170748-token-extraction
set SCRIPT=t_starter.py

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

REM Run script with different modes
echo Running word extraction in different modes...

@REM echo 1. Simple word mode...
@REM call "%PYTHON_PATH%" "%SCRIPT%" --type word --mode simple
@REM if errorlevel 1 goto :error

echo.
echo 2. Dual word mode...
call "%PYTHON_PATH%" "%SCRIPT%" --language de --type word --mode dual
if errorlevel 1 goto :error

echo.
echo 3. Dual sentence mode...
call "%PYTHON_PATH%" "%SCRIPT%" --language de --type sentence --mode dual
if errorlevel 1 goto :error

echo.
echo All operations completed successfully.
exit /b 0

:error
echo ERROR: Script failed with error level %errorlevel%
exit /b 1