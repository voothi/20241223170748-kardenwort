import subprocess
import pytest
from pathlib import Path
import os
import sys
import json
import re
import csv
import configparser

def load_integration_config(project_root):
    config = configparser.ConfigParser(allow_no_value=True)
    config.read(project_root / "config.ini", encoding='utf-8')
    return config

def load_integration_mapping(project_root):
    mapping = configparser.ConfigParser(allow_no_value=True)
    mapping.optionxform = str
    mapping.read(project_root / "anki-mapping.ini", encoding='utf-8')
    return mapping

def get_field_mapping_indices(config, extraction_type):
    """
    Returns a map of {internal_data_source: column_index} 
    based on [anki_fields] and [anki_field_mapping.{extraction_type}]
    """
    if 'anki_fields' not in config:
        return {}
    
    # anki_fields is an ordered list of fields in the TSV
    raw_fields = list(dict(config.items('anki_fields')).keys())
    
    mapping_section = f'anki_field_mapping.{extraction_type}'
    if mapping_section not in config:
        return {}
    
    mapping = dict(config[mapping_section])
    # {AnkiFieldName: InternalSource}
    
    source_to_index = {}
    for i, field_name in enumerate(raw_fields):
        internal_source = mapping.get(field_name)
        if internal_source:
            # Note: Multiple Anki fields can map to the same internal source
            if internal_source not in source_to_index:
                source_to_index[internal_source] = []
            source_to_index[internal_source].append(i)
            
    return source_to_index

class IntegrationTester:
    def __init__(self):
        self.project_root = Path(__file__).resolve().parent.parent.parent
        self.runner_path = self.project_root / "src" / "kardenwort" / "core" / "kardenwort_runner.py"
        self.config = load_integration_config(self.project_root)
        self.mapping = load_integration_mapping(self.project_root)
        self.results_dir = self.project_root / "results"
        
        self.env = os.environ.copy()
        self.env["PYTHONPATH"] = str(self.project_root / "src")
        self.env["KARDENWORT_TESTING"] = "true"

        if not self.results_dir.exists():
            self.results_dir.mkdir(parents=True)

    def run_runner(self, args):
        cmd = [sys.executable, str(self.runner_path)] + args
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=self.env,
            cwd=str(self.project_root)
        )
        return result

    def normalize_metadata(self, metadata):
        if "deck_descriptions" not in metadata:
            return metadata
        normalized = {}
        for deck_name, desc in metadata["deck_descriptions"].items():
            clean_deck_name = re.sub(r'\d{14}-', '', deck_name)
            normalized[clean_deck_name] = desc
        return {"deck_descriptions": normalized}

    def verify_tsv(self, language, suffix, reference_tsv_path):
        ref_slug = re.sub(r'^\d{14}-', '', reference_tsv_path.name)
        tsv_files = list(self.results_dir.glob(f"*{ref_slug}"))
        if not tsv_files:
            tsv_pattern = f"*.{suffix}.{language}.tsv"
            tsv_files = list(self.results_dir.glob(tsv_pattern))
        if not tsv_files:
            pytest.fail(f"No matching TSV file for {ref_slug} found in results")
        
        latest_tsv = max(tsv_files, key=os.path.getmtime)
        
        with open(latest_tsv, 'r', encoding='utf-8') as f:
            gen_rows = list(csv.reader(f, delimiter='\t'))
        
        with open(reference_tsv_path, 'r', encoding='utf-8') as f:
            ref_rows = list(csv.reader(f, delimiter='\t'))
            
        assert len(gen_rows) == len(ref_rows), f"Row count mismatch for {latest_tsv}"
        
        # Verify headers match up to the reference row length
        ref_len = len(ref_rows[0])
        assert gen_rows[0][:ref_len] == ref_rows[0], f"Header mismatch in {latest_tsv}"
        
        # Verify field mapping indices based on config
        mapping_indices = get_field_mapping_indices(self.mapping, suffix)
        
        # We check critical fields if they are mapped
        # In current config.ini:
        # WordSource = lemma (at index 1 usually)
        # SentenceSource = source_sentence (at index 9 usually)
        
        for i, (gen_row, ref_row) in enumerate(zip(gen_rows, ref_rows)):
            if i == 0: continue # Skip header
            
            # Slice gen_row to match ref_row columns count and strip timestamps from all columns
            gen_row_norm = [re.sub(r'\d{14}-', '', col) for col in gen_row[:len(ref_row)]]
            ref_row_norm = [re.sub(r'\d{14}-', '', col) for col in ref_row]
            
            # Compare rows
            assert gen_row_norm == ref_row_norm, f"Content mismatch at row {i+1} in {latest_tsv}"

    def verify_json(self, language, reference_json_path):
        ref_slug = re.sub(r'^\d{14}-', '', reference_json_path.name)
        json_files = list(self.results_dir.glob(f"*{ref_slug}"))
        if not json_files:
            json_pattern = f"*.sentence.{language}.json"
            json_files = list(self.results_dir.glob(json_pattern))
        if not json_files:
            pytest.fail(f"No matching JSON file for {ref_slug} found in results")
        
        latest_json = max(json_files, key=os.path.getmtime)
        
        with open(latest_json, 'r', encoding='utf-8') as f:
            gen_data = json.load(f)
        with open(reference_json_path, 'r', encoding='utf-8') as f:
            ref_data = json.load(f)
            
        assert self.normalize_metadata(gen_data) == self.normalize_metadata(ref_data)

@pytest.fixture(scope="module")
def tester():
    return IntegrationTester()

def discover_test_cases():
    cases_root = Path(__file__).resolve().parent.parent / "cases"
    cases = []
    # Only look at top-level directories in cases/ to avoid legacy/stale subfolders like 'a/'
    for case_dir in cases_root.iterdir():
        if case_dir.is_dir() and (case_dir / "text1.txt").exists():
            lang = "de" if "de" in case_dir.name else "en"
            cases.append((case_dir, lang))
    return cases

@pytest.mark.parametrize("case_dir, lang", discover_test_cases())
def test_integration_case(tester, case_dir, lang):
    # Prepare arguments
    args = [
        "--language", lang,
        "--mode", "mixed-triple",
        "--tts-destination-lang", "ru",
        "--deduplication-scope", "global",
        "--anki-create-subdecks",
        "--anki-markdown-decks",
        "--anki-sentence-subdecks",
        "--anki-deck-content", "parent-source", "parent-translations", "subdeck-source", "subdeck-translations",
        "--suspend-cards",
        "--text1-file", str(case_dir / "text1.txt"),
    ]
    
    if (case_dir / "text2.txt").exists():
        args.extend(["--text2-file", str(case_dir / "text2.txt")])
    if (case_dir / "text3.txt").exists():
        args.extend(["--text3-file", str(case_dir / "text3.txt")])

    result = tester.run_runner(args)
    assert result.returncode == 0, f"Runner failed with: {result.stderr}"

    # Verify TSVs
    for ref_tsv in case_dir.glob("*.tsv"):
        suffix = "sentence" if ".sentence." in ref_tsv.name else "word"
        tester.verify_tsv(lang, suffix, ref_tsv)
        
    # Verify JSON
    for ref_json in case_dir.glob("*.json"):
        tester.verify_json(lang, ref_json)
