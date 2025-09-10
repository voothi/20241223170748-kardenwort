@echo off
REM Setup the environment and set UTF-8 encoding.
setlocal
chcp 65001 > nul

REM Pass the input text to the Python script via an environment variable.
set "KARDENWORT_INPUT_TEXT=%~1"

REM Execute the Python script directly. It will read the environment variable internally.
"U:/voothi/20250825231214-spacy-env/Scripts/python.exe" ^
U:/voothi/20241223170748-kardenwort/kardenwort.py ^
--type "word" ^
--language "de" ^
--lemma-index-file "U:/voothi/20241223170748-kardenwort/data/deu-mixed-typical-2011-1m-words.csv" ^
--lemma-override-file "U:/voothi/20241223170748-kardenwort/data/lemma_override_de.tsv" ^
--de-dictionary-file "U:/voothi/20241223170748-kardenwort/data/german.dic" ^
--sentence-context-size "0" ^
--stdout-format "html" ^
--de-fix-genitive ^
--de-gcs ^
--de-gcs-pos-tags "!VERB" ^
--de-gcs-split-mode "combined" ^
--de-gcs-preserve-compound-word ^
--de-gcs-skip-merge-fractions