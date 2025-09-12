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
for /f "delims=" %%a in ('call "%~dp0..\..\_config_loader.cmd" language_resources') do (set "%%a")


:: ============================================================================
:: 2. Validate Configuration and Define Paths
:: ============================================================================
if not defined CFG_python_executable (echo ERROR: python_executable not found in [environment] section. >&2 & exit /b 1)
if not defined CFG_kardenwort_workspace (echo ERROR: kardenwort_workspace not found in [environment] section. >&2 & exit /b 1)
if not defined CFG_kardenwort_script_filename (echo ERROR: kardenwort_script_filename not found in [scripts] section. >&2 & exit /b 1)
if not defined CFG_source_code_dir (echo ERROR: source_code_dir not found in [project_structure] section. >&2 & exit /b 1)
if not defined CFG_data_dir (echo ERROR: data_dir not found in [project_structure] section. >&2 & exit /b 1)
if not defined CFG_lemma_file_en (echo ERROR: lemma_file_en not found in [language_resources] section. >&2 & exit /b 1)
if not defined CFG_override_file_en (echo ERROR: override_file_en not found in [language_resources] section. >&2 & exit /b 1)

set "PYTHON_EXE=%CFG_python_executable%"
set "KARDENWORT_SCRIPT=%CFG_kardenwort_workspace%/%CFG_source_code_dir%/%CFG_kardenwort_script_filename%"
set "LEMMA_INDEX_FILE=%CFG_kardenwort_workspace%/%CFG_data_dir%/%CFG_lemma_file_en%"
set "LEMMA_OVERRIDE_FILE=%CFG_kardenwort_workspace%/%CFG_data_dir%/%CFG_override_file_en%"

:: Pass the input text to the Python script via an environment variable.
set "KARDENWORT_INPUT_TEXT=%~1"


:: ============================================================================
:: 3. Execute the Python Script
:: It will read the KARDENWORT_INPUT_TEXT environment variable internally.
:: ============================================================================
"%PYTHON_EXE%" "%KARDENWORT_SCRIPT%" ^
--type "word" ^
--language "en" ^
--lemma-index-file "%LEMMA_INDEX_FILE%" ^
--lemma-override-file "%LEMMA_OVERRIDE_FILE%" ^
--sentence-context-size "0" ^
--stdout-format "html"