@echo off
chcp 65001 > nul

:: ============================================================================
:: 1. Load Configuration
:: ============================================================================
for /f "delims=" %%a in ('call "%~dp0..\..\_config_loader.cmd"') do (
    set "%%a"
)

:: Check if the required variables were loaded from config.ini
if not defined CFG_python_path (
    echo ERROR: python_path not found in config.ini [paths_win] section. >&2
    exit /b 1
)
if not defined CFG_kardenwort_workspace (
    echo ERROR: kardenwort_workspace not found in config.ini [paths_win] section. >&2
    exit /b 1
)

:: ============================================================================
:: 2. Define Full Paths and Input
:: This makes the command block below clean and avoids parser bugs.
:: ============================================================================
set "PYTHON_EXE=%CFG_python_path%"
set "KARDENWORT_SCRIPT=%CFG_kardenwort_workspace%/kardenwort.py"
set "LEMMA_INDEX_FILE=%CFG_kardenwort_workspace%/data/deu-mixed-typical-2011-1m-words.csv"
set "LEMMA_OVERRIDE_FILE=%CFG_kardenwort_workspace%/data/lemma_override_de.tsv"
set "DE_DICT_FILE=%CFG_kardenwort_workspace%/data/german.dic"

:: Pass the input text to the Python script via an environment variable.
set "KARDENWORT_INPUT_TEXT=%~1"

:: ============================================================================
:: 3. Execute the Python Script
:: It will read the KARDENWORT_INPUT_TEXT environment variable internally.
:: ============================================================================
"%PYTHON_EXE%" "%KARDENWORT_SCRIPT%" ^
--type "word" ^
--language "de" ^
--lemma-index-file "%LEMMA_INDEX_FILE%" ^
--lemma-override-file "%LEMMA_OVERRIDE_FILE%" ^
--de-dictionary-file "%DE_DICT_FILE%" ^
--sentence-context-size "0" ^
--stdout-format "html" ^
--de-fix-genitive ^
--de-gcs ^
--de-gcs-pos-tags "NOUN PRON ADV ADJ" ^
--de-gcs-split-mode "combined" ^
--de-gcs-preserve-compound-word ^
--de-gcs-skip-merge-fractions