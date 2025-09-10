@echo off
REM We set the UTF-8 encoding for correct work with Python.
chcp 65001 > nul

REM We run the python script, passing it the first argument (%1) from GoldenDict.
U:/voothi/20250825231214-spacy-env/Scripts/python.exe ^
U:/voothi/20241223170748-kardenwort/kardenwort.py ^
--type "word" ^
--language "de" ^
--text "%1" ^
--lemma-index-file "U:/voothi/20241223170748-kardenwort/data/deu-mixed-typical-2011-1m-words.csv" ^
--lemma-override-file "U:/voothi/20241223170748-kardenwort/data/lemma_override_de.tsv" ^
--de-dictionary-file "U:/voothi/20241223170748-kardenwort/data/german.dic" ^
--sentence-context-size "0" ^
--stdout-format "html" ^
--de-fix-genitive ^
--de-gcs ^
--de-gcs-pos-tags "NOUN PRON ADV ADJ" ^
--de-gcs-split-mode "combined" ^
--de-gcs-preserve-compound-word ^
--de-gcs-skip-merge-fractions