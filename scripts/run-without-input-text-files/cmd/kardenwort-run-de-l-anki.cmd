@echo off
REM Setup the environment and set UTF-8 encoding.
setlocal
chcp 65001 > nul

REM Pass the input text to the Python script via an environment variable.
set "KARDENWORT_INPUT_TEXT=%~1"

rem Execute the Python script. It will read the environment variable internally.
"U:/voothi/20250825231214-spacy-env/Scripts/python.exe" ^
U:/voothi/20241223170748-kardenwort/kardenwort-runner.py ^
--type "word" ^
--language "de" ^
--text "%GDWORD%" ^
--de-gcs ^
--de-gcs-pos-tags "!VERB" ^
--mode "single"