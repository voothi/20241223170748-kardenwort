import subprocess
import unittest
from pathlib import Path
import os
import sys
import json
import re
import csv

class TestIntegration(unittest.TestCase):
    def setUp(self):
        self.project_root = Path(__file__).resolve().parent.parent
        self.runner_path = self.project_root / "src" / "kardenwort" / "core" / "kardenwort_runner.py"
        
        self.env = os.environ.copy()
        self.env["PYTHONPATH"] = str(self.project_root / "src")

        self.results_dir = self.project_root / "results"
        if not self.results_dir.exists():
            self.results_dir.mkdir(parents=True)

    def run_runner(self, args):
        cmd = [sys.executable, str(self.runner_path)] + args
        print(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=self.env,
            cwd=str(self.project_root)
        )
        return result

    def normalize_metadata(self, metadata):
        """Removes timestamps from deck names for stable comparison."""
        if "deck_descriptions" not in metadata:
            return metadata
        
        normalized = {}
        for deck_name, desc in metadata["deck_descriptions"].items():
            # Replace YYYYMMDDHHMMSS- with nothing in the deck name
            clean_deck_name = re.sub(r'\d{14}-', '', deck_name)
            normalized[clean_deck_name] = desc
        return {"deck_descriptions": normalized}

    def assert_json_metadata_match(self, result_stdout, reference_json_path, language):
        # Extract output filename from stdout
        # Let's look for the .sentence.[language].json file in results
        json_pattern = f"*.sentence.{language}.json"
        json_files = list(self.results_dir.glob(json_pattern))
        if not json_files:
            self.fail(f"No {json_pattern} file found in results")
        
        # Sort by mtime to get the latest one
        latest_json = max(json_files, key=os.path.getmtime)
        
        with open(latest_json, 'r', encoding='utf-8') as f:
            generated_data = json.load(f)
        
        with open(reference_json_path, 'r', encoding='utf-8') as f:
            reference_data = json.load(f)
            
        norm_generated = self.normalize_metadata(generated_data)
        norm_reference = self.normalize_metadata(reference_data)
        
        self.assertEqual(norm_generated, norm_reference, f"Metadata mismatch for {latest_json}")

    def assert_tsv_content_match(self, result_stdout, reference_tsv_path, language, suffix):
        """Verifies TSV content, field order, and sorting."""
        tsv_pattern = f"*.{suffix}.{language}.tsv"
        tsv_files = list(self.results_dir.glob(tsv_pattern))
        if not tsv_files:
            self.fail(f"No {tsv_pattern} file found in results")
        
        latest_tsv = max(tsv_files, key=os.path.getmtime)
        
        with open(latest_tsv, 'r', encoding='utf-8') as f:
            generated_rows = list(csv.reader(f, delimiter='\t'))
        
        with open(reference_tsv_path, 'r', encoding='utf-8') as f:
            reference_rows = list(csv.reader(f, delimiter='\t'))
            
        self.assertEqual(len(generated_rows), len(reference_rows), f"Row count mismatch for {latest_tsv}")
        
        # Verify headers match
        self.assertEqual(generated_rows[0], reference_rows[0], f"Header mismatch in {latest_tsv}")
        
        # Identifying critical fields
        header = generated_rows[0]
        try:
            word_source_idx = header.index("WordSource")
            sentence_source_idx = header.index("SentenceSource")
            wordlist_idx = header.index("SentenceSourceWordlist")
        except ValueError as e:
            self.fail(f"Required field missing in TSV header: {e}")

        # Check field order (sanity check against known indices)
        self.assertEqual(word_source_idx, 1, "WordSource should be at index 1")
        self.assertEqual(sentence_source_idx, 9, "SentenceSource should be at index 9")

        # Compare content excluding dynamic/calculated fields if necessary, 
        # but here we expect exact match for stable test cases.
        for i, (gen_row, ref_row) in enumerate(zip(generated_rows, reference_rows)):
            # Normalize deck names in the last column if they contain timestamps
            # (Though the user didn't explicitly ask for this, it's good for stability)
            gen_deck = re.sub(r'\d{14}-', '', gen_row[-1])
            ref_deck = re.sub(r'\d{14}-', '', ref_row[-1])
            
            gen_row_norm = gen_row[:-1] + [gen_deck]
            ref_row_norm = ref_row[:-1] + [ref_deck]
            
            self.assertEqual(gen_row_norm, ref_row_norm, f"Content mismatch at row {i+1} in {latest_tsv}")

    def test_german_mixed_triple_from_cases(self):
        test_case_dir = self.project_root / "tests" / "cases" / "20260303214721-de"
        reference_json = test_case_dir / "20260303220432-testen-deutscher-trennbarer-verben.triple.sentence.de.json"
        
        args = [
            "--language", "de",
            "--mode", "mixed-triple",
            "--tts-destination-lang", "ru",
            "--deduplication-scope", "global",
            "--anki-create-subdecks",
            "--anki-markdown-decks",
            "--anki-sentence-subdecks",
            "--anki-deck-content", "parent-source", "parent-translations", "subdeck-source", "subdeck-translations",
            "--suspend-cards",
            "--show-success-message",
            "--play-sound-on-completion",
            "--text1-file", str(test_case_dir / "text1.txt"),
            "--text2-file", str(test_case_dir / "text2.txt"),
            "--text3-file", str(test_case_dir / "text3.txt")
        ]
        
        result = self.run_runner(args)
        
        self.assertEqual(result.returncode, 0, f"Runner failed with: {result.stderr}")
        self.assertIn("All operations for mixed-triple mode completed successfully", result.stdout + result.stderr)
        self.assert_json_metadata_match(result.stdout, reference_json, "de")
        
        # Verify TSVs
        reference_sentence_tsv = test_case_dir / "20260303220432-testen-deutscher-trennbarer-verben.triple.sentence.de.tsv"
        reference_word_tsv = test_case_dir / "20260303220436-testen-deutscher-trennbarer-verben.triple.word.de.tsv"
        
        self.assert_tsv_content_match(result.stdout, reference_sentence_tsv, "de", "sentence")
        self.assert_tsv_content_match(result.stdout, reference_word_tsv, "de", "word")

    def test_english_mixed_triple_from_cases(self):
        test_case_dir = self.project_root / "tests" / "cases" / "20260303214728-en"
        reference_json = test_case_dir / "20260303215150-false-string-introduction-to.triple.sentence.en.json"
        
        args = [
            "--language", "en",
            "--mode", "mixed-triple",
            "--tts-destination-lang", "ru",
            "--deduplication-scope", "global",
            "--anki-create-subdecks",
            "--anki-markdown-decks",
            "--anki-sentence-subdecks",
            "--anki-deck-content", "parent-source", "parent-translations", "subdeck-source", "subdeck-translations",
            "--suspend-cards",
            "--show-success-message",
            "--play-sound-on-completion",
            "--text1-file", str(test_case_dir / "text1.txt"),
            "--text2-file", str(test_case_dir / "text2.txt"),
            "--text3-file", str(test_case_dir / "text3.txt")
        ]
        
        result = self.run_runner(args)
        self.assertEqual(result.returncode, 0, f"Runner failed with: {result.stderr}")
        self.assertIn("All operations for mixed-triple mode completed successfully", result.stdout + result.stderr)
        self.assert_json_metadata_match(result.stdout, reference_json, "en")
        
        # Verify TSVs
        reference_sentence_tsv = test_case_dir / "20260303215150-false-string-introduction-to.triple.sentence.en.tsv"
        reference_word_tsv = test_case_dir / "20260303215152-false-string-introduction-to.triple.word.en.tsv"
        
        self.assert_tsv_content_match(result.stdout, reference_sentence_tsv, "en", "sentence")
        self.assert_tsv_content_match(result.stdout, reference_word_tsv, "en", "word")

if __name__ == '__main__':
    unittest.main()
