import subprocess
import json
import os

python_exe = r'u:\voothi\20250825231214-spacy-env\Scripts\python.exe'
kardenwort_script = r'u:\voothi\20241223170748-kardenwort\src\kardenwort\core\kardenwort.py'
text1_file = 'test_trennbar2.txt'
with open(text1_file, 'w', encoding='utf-8') as f:
    f.write('Testen deutscher trennbarer Verben und anderer')

cmd = [
    python_exe,
    kardenwort_script,
    '--type', 'word',
    '--language', 'de',
    '--deduplication-scope', 'sentence',
    '--sentence-context-size', '0',
    '--anki-csv-header', json.dumps(['WordSource', 'WordDestination']),
    '--anki-field-mapping', json.dumps({'WordSource': 'lemma'}),
    '--output-file', 'test_trennbar_out2.tsv',
    '--text1-file', text1_file,
    '--tts-destination-lang', 'ru',
    '--use-simplemma-correction'
]

print("Running command...")
res = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
print("TSV OUTPUT:")
if os.path.exists('test_trennbar_out2.tsv'):
    with open('test_trennbar_out2.tsv', 'r', encoding='utf-8') as f:
        print(f.read())
