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

REM Run script
echo Running word extraction for a single German text...

echo.
echo Single word mode with GCS (excluding verbs)...
call "%PYTHON_PATH%" "%SCRIPT%" --language de --type word --mode single --de-gcs --de-gcs-pos-tags "!VERB"
if errorlevel 1 goto :error

echo.
echo All operations completed successfully.
exit /b 0

:error
echo ERROR: Script failed with error level %errorlevel%
exit /b 1