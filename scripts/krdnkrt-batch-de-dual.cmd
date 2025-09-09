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

REM Run script with different modes
echo Running extraction in different modes...

echo.
echo Dual word mode with GCS (excluding verbs)...
call "%PYTHON_PATH%" "%SCRIPT%" --language de --type word --mode dual --de-gcs --de-gcs-pos-tags "!VERB"
if errorlevel 1 goto :error

echo.
echo Dual sentence mode...
REM --de-gcs flags are ignored in 'sentence' mode by the main script, so they are not included here.
call "%PYTHON_PATH%" "%SCRIPT%" --language de --type sentence --mode dual
if errorlevel 1 goto :error

echo.
echo All operations completed successfully.
exit /b 0

:error
echo ERROR: Script failed with error level %errorlevel%
exit /b 1