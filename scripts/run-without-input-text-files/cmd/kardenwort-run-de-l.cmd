@echo off
setlocal enabledelayedexpansion
chcp 65001 > nul

:: Load configuration from config.ini
call "%~dp0_config_loader.cmd"
if errorlevel 1 exit /b 1

:: Check if the required variables were loaded
if not defined CFG_python_path (
    echo ERROR: python_path not found in config.ini [paths_win] section. >&2
    exit /b 1
)
if not defined CFG_kardenwort_workspace (
    echo ERROR: kardenwort_workspace not found in config.ini [paths_win] section. >&2
    exit /b 1
)

set "KARDENWORT_INPUT_TEXT=%~1"

:: Use variables loaded from the config file to build all paths
"%CFG_python_path%" ^
"%CFG_kardenwort_workspace%/kardenwort.py" ^
--type "word" ^
--language "de" ^
--lemma-index-file "%CFG_kardenwort_workspace%/data/deu-mixed-typical-2011-1m-words.csv" ^
--lemma-override-file "%CFG_kardenwort_workspace%/data/lemma_override_de.tsv" ^
--de-dictionary-file "%CFG_kardenwort_workspace%/data/german.dic" ^
--sentence-context-size "0" ^
--stdout-format "html" ^
--de-fix-genitive ^
--de-gcs ^
--de-gcs-pos-tags "!VERB" ^
--de-gcs-split-mode "combined" ^
--de-gcs-preserve-compound-word ^
--de-gcs-skip-merge-fractions