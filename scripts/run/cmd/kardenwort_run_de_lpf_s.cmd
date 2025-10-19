@echo off
rem Set console code page to UTF-8 to handle special characters correctly.
chcp 65001 > nul

rem --- Configuration Section ---
set "PYTHON_EXE=U:/voothi/20250825231214-spacy-env/Scripts/python.exe"
set "KARDENWORT_SCRIPT=U:/voothi/20241223170748-kardenwort/src/kardenwort/core/kardenwort.py"
set "INPUT_FILE=U:/voothi/20241223170748-kardenwort/source_texts/text1.txt"
for %%F in ("%INPUT_FILE%") do set "OUTPUT_FILE=%%~dpnF.lemmas.txt"
set "LEMMA_INDEX_FILE=U:/voothi/20241223170748-kardenwort/data/de/deu-mixed-typical-2011-1m-words.csv"
set "LEMMA_OVERRIDE_FILE=U:/voothi/20241223170748-kardenwort/data/de/lemma_override_de.tsv"
set "DE_DICT_FILE=U:/voothi/20241223170748-kardenwort/data/de/german.dic"


rem --- Execution Section ---
echo ============================================================================
echo Starting Kardenwort script...
echo Input file:  %INPUT_FILE%
echo Output file: %OUTPUT_FILE%
echo ============================================================================

rem --- SINGLE-LINE COMMAND TO PREVENT ERRORS ---
"%PYTHON_EXE%" "%KARDENWORT_SCRIPT%" --lemmas-per-line --language "de" --text1-file "%INPUT_FILE%" --output-file "%OUTPUT_FILE%" --lemma-index-file "%LEMMA_INDEX_FILE%" --lemma-override-file "%LEMMA_OVERRIDE_FILE%" --de-dictionary-file "%DE_DICT_FILE%" --de-fix-genitive

if errorlevel 1 (
    echo.
    echo ERROR: The script failed with an error.
    pause
    exit /b 1
)

echo.
echo ============================================================================
echo Script finished successfully.
echo Output has been saved to: %OUTPUT_FILE%
echo ============================================================================
echo.