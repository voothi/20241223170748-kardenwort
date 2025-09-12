@echo off
chcp 65001 > nul

:: ============================================================================
:: 1. Change to the Project Root Directory
:: This is the crucial fix. It ensures that all subsequent relative paths
:: (both in this script and in the Python script) are resolved correctly.
:: ============================================================================
set "PROJECT_ROOT=%~dp0..\..\.."
cd /d "%PROJECT_ROOT%"
if errorlevel 1 (
    echo ERROR: Failed to change directory to the project root: "%PROJECT_ROOT%" >&2
    exit /b 1
)


:: ============================================================================
:: 1. Load Configuration from multiple sections
:: ============================================================================
for /f "delims=" %%a in ('call "%~dp0..\..\_config_loader.cmd" environment') do (set "%%a")
for /f "delims=" %%a in ('call "%~dp0..\..\_config_loader.cmd" scripts') do (set "%%a")
for /f "delims=" %%a in ('call "%~dp0..\..\_config_loader.cmd" project_structure') do (set "%%a")


:: ============================================================================
:: 2. Validate Configuration and Define Paths
:: ============================================================================
if not defined CFG_python_executable (echo ERROR: python_executable not found in [environment] section. >&2 & exit /b 1)
if not defined CFG_kardenwort_workspace (echo ERROR: kardenwort_workspace not found in [environment] section. >&2 & exit /b 1)
if not defined CFG_kardenwort_runner_filename (echo ERROR: kardenwort_runner_filename not found in [scripts] section. >&2 & exit /b 1)
if not defined CFG_source_code_dir (echo ERROR: source_code_dir not found in [project_structure] section. >&2 & exit /b 1)

set "PYTHON_EXE=%CFG_python_executable%"
set "KARDENWORT_RUNNER_SCRIPT=%CFG_kardenwort_workspace%/%CFG_source_code_dir%/%CFG_kardenwort_runner_filename%"


:: ============================================================================
:: 3. Execute the Python Script
:: ============================================================================
echo Running extraction in different modes...

echo.
echo Triple word mode with GCS...
call "%PYTHON_EXE%" "%KARDENWORT_RUNNER_SCRIPT%" --language de --type word --mode triple --de-gcs --de-gcs-pos-tags "!VERB"
if errorlevel 1 goto :error

echo.
echo Triple sentence mode...
call "%PYTHON_EXE%" "%KARDENWORT_RUNNER_SCRIPT%" --language de --type sentence --mode triple
if errorlevel 1 goto :error

echo.
echo All operations completed successfully.
exit /b 0

:error
echo ERROR: Script failed with error level %errorlevel%
exit /b 1