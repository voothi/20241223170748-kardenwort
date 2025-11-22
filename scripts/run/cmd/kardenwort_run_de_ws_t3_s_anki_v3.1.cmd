@echo off
chcp 65001 > nul

:: ============================================================================
:: 1. Change to the Project Root Directory
:: ============================================================================
set "PROJECT_ROOT=%~dp0..\..\.."
cd /d "%PROJECT_ROOT%"
if errorlevel 1 (
    echo ERROR: Failed to change directory to the project root: "%PROJECT_ROOT%" >&2
    exit /b 1
)

:: ============================================================================
:: 2. Load Configuration and Define Paths
:: ============================================================================
for /f "delims=" %%a in ('call "%~dp0..\..\_config_loader.cmd" environment') do (set "%%a")
for /f "delims=" %%a in ('call "%~dp0..\..\_config_loader.cmd" scripts') do (set "%%a")
for /f "delims=" %%a in ('call "%~dp0..\..\_config_loader.cmd" project_structure') do (set "%%a")

if not defined CFG_python_executable (echo ERROR: python_executable not found in [environment] section. >&2 & exit /b 1)
if not defined CFG_kardenwort_workspace (echo ERROR: kardenwort_workspace not found in [environment] section. >&2 & exit /b 1)
if not defined CFG_kardenwort_runner_filename (echo ERROR: kardenwort_runner_filename not found in [scripts] section. >&2 & exit /b 1)
if not defined CFG_source_code_dir (echo ERROR: source_code_dir not found in [project_structure] section. >&2 & exit /b 1)

set "PYTHON_EXE=%CFG_python_executable%"
set "KARDENWORT_RUNNER_SCRIPT=%CFG_kardenwort_workspace%/%CFG_source_code_dir%/%CFG_kardenwort_runner_filename%"

:: ============================================================================
:: 3. Execute the Python Script in Mixed Mode
:: ============================================================================
echo Running extraction in mixed-triple mode (sentence + word)...

:: This single command now handles both sentence and word processing,
:: creating a shared parent deck automatically thanks to the --mode mixed-triple.
call "%PYTHON_EXE%" "%KARDENWORT_RUNNER_SCRIPT%" ^
    --language de ^
    --mode mixed-triple ^
    --tts-destination-lang ru ^
    --deduplication-scope sentence ^
    --anki-create-subdecks ^
    --anki-markdown-decks ^
    --anki-sentence-subdecks ^
    --anki-deck-content parent-source parent-translations subdeck-source subdeck-translations ^
    --suspend-cards ^
    --show-success-message ^
    --play-sound-on-completion

if errorlevel 1 goto :error

echo.
echo All operations completed successfully.
exit /b 0

:error
echo ERROR: Script failed with error level %errorlevel%
exit /b 1