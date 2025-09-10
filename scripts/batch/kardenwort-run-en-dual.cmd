@echo off
setlocal EnableDelayedExpansion

REM --- Universal startup block ---
set "WORKSPACE=%~dp0..\"
set "RUNNER_SCRIPT=kardenwort-runner.py"

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: 'python' command not found. Please ensure it is installed and in your PATH.
    exit /b 1
)

for /f "usebackq delims=" %%i in (`python "%WORKSPACE%%RUNNER_SCRIPT%" --get-python-path`) do set "PYTHON_PATH=%%i"

if "!PYTHON_PATH!"=="" (
    echo ERROR: Failed to get Python path from config.ini. See script output above for details.
    exit /b 1
)
if not exist "%PYTHON_PATH%" (
    echo ERROR: Python executable from config.ini not found: !PYTHON_PATH!
    exit /b 1
)

cd /d "%WORKSPACE%"
if errorlevel 1 (
    echo ERROR: Failed to change directory to %WORKSPACE%
    exit /b 1
)
REM --- End of universal block ---


echo Running extraction for English in dual mode...

echo.
echo Dual word mode...
call "%PYTHON_PATH%" "%RUNNER_SCRIPT%" --language en --type word --mode dual
if errorlevel 1 goto :error

echo.
echo Dual sentence mode...
call "%PYTHON_PATH%" "%RUNNER_SCRIPT%" --language en --type sentence --mode dual
if errorlevel 1 goto :error

echo.
echo All operations completed successfully.
exit /b 0

:error
echo ERROR: Script failed with error level %errorlevel%
exit /b 1