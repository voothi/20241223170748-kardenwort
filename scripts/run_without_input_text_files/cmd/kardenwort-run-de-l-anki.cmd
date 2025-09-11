@echo off
chcp 65001 > nul

:: ============================================================================
:: 1. Load Configuration
:: ============================================================================
for /f "delims=" %%a in ('call "%~dp0..\..\_config_loader.cmd"') do (
    set "%%a"
)

:: Check if the required variables were loaded from config.ini
if not defined CFG_python_executable (
    echo ERROR: python_executable not found in config.ini [environment] section. >&2
    exit /b 1
)
if not defined CFG_kardenwort_workspace (
    echo ERROR: kardenwort_workspace not found in config.ini [environment] section. >&2
    exit /b 1
)

:: ============================================================================
:: 2. Define Full Paths and Input
:: This makes the command block below clean and avoids parser bugs.
:: ============================================================================
set "PYTHON_EXE=%CFG_python_executable%"
set "KARDENWORT_SCRIPT=%CFG_kardenwort_workspace%/src/kardenwort/core/kardenwort_runner.py"

:: Pass the input text to the Python script via an environment variable.
set "KARDENWORT_INPUT_TEXT=%~1"

:: ============================================================================
:: 3. Execute the Python Script
:: It will read the KARDENWORT_INPUT_TEXT environment variable internally.
:: ============================================================================
"%PYTHON_EXE%" "%KARDENWORT_SCRIPT%" ^
--type "word" ^
--language "de" ^
--de-gcs ^
--de-gcs-pos-tags "!VERB" ^
--mode "single"