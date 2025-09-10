@echo off
rem Setup the environment and set UTF-8 encoding.
setlocal
chcp 65001 > nul

rem Pass the input text to the Python script via an environment variable.
set "KARDENWORT_INPUT_TEXT=%~1"

rem Execute the Python script. It will read the environment variable internally.
"U:/voothi/20250825231214-spacy-env/Scripts/python.exe" ^
U:/voothi/20241223170748-kardenwort/kardenwort.py ^
--type "word" ^
--language "en" ^
--lemma-index-file "U:/voothi/20241223170748-kardenwort/data/en-news-2023-1m-words.csv" ^
--lemma-override-file "U:/voothi/20241223170748-kardenwort/data/lemma_override_en.tsv" ^
--sentence-context-size "0" ^
--stdout-format "html"