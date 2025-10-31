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
:: 3. Execute the Python Scripts with Shared Parent Deck Logic
:: ============================================================================
echo Running extraction in different modes...

echo.
echo Triple sentence mode...
:: Run the first script, now with the --suspend-cards and --anki-markdown-subdecks flags
for /f "delims=" %%F in ('call "%PYTHON_EXE%" "%KARDENWORT_RUNNER_SCRIPT%" --language de --type sentence --mode triple --anki-create-subdecks --anki-markdown-subdecks --suspend-cards') do (
    set "SENTENCE_FILENAME=%%F"
)

if not defined SENTENCE_FILENAME (
    echo ERROR: Failed to get filename from the sentence script run. >&2
    goto :error
)

:: Derive the parent deck name from the first script's output filename.
set "TEMP_DECK_NAME=%SENTENCE_FILENAME:.tsv=%"
set "PARENT_DECK_NAME=%TEMP_DECK_NAME:.sentence=%"


echo Parent Deck Name for this session is: %PARENT_DECK_NAME%

echo.
echo Triple word mode...
:: Run the second script, passing the parent deck name and the --suspend-cards and --anki-markdown-subdecks flags
call "%PYTHON_EXE%" "%KARDENWORT_RUNNER_SCRIPT%" --language de --type word --mode triple --anki-create-subdecks --anki-markdown-subdecks --anki-parent-deck "%PARENT_DECK_NAME%" --suspend-cards
if errorlevel 1 goto :error

echo.
echo All operations completed successfully.
exit /b 0

:error
echo ERROR: Script failed with error level %errorlevel%
exit /b 1