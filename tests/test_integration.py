import subprocess
import unittest
from pathlib import Path
import os
import sys
import json
import re

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

if __name__ == '__main__':
    unittest.main()
