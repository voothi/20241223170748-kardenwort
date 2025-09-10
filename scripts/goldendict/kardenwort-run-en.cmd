@echo off
REM We set the UTF-8 encoding for correct work with Python.
chcp 65001 > nul

REM We run the python script, passing it the first argument (%1) from GoldenDict.
U:/voothi/20250825231214-spacy-env/Scripts/python.exe ^
U:/voothi/20241223170748-kardenwort/kardenwort.py ^
--type "word" ^
--language "en" ^
--text "%1" ^
--lemma-index-file "U:/voothi/20241223170748-kardenwort/data/en-news-2023-1m-words.csv" ^
--lemma-override-file "U:/voothi/20241223170748-kardenwort/data/lemma_override_en.tsv" ^
--sentence-context-size "0" ^
--stdout-format "html"