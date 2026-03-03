import subprocess
import unittest
from pathlib import Path
import os
import sys

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

    def test_german_mixed_triple_from_cases(self):
        test_case_dir = self.project_root / "tests" / "cases" / "20260303214721-de"
        
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

    def test_english_mixed_triple_from_cases(self):
        test_case_dir = self.project_root / "tests" / "cases" / "20260303214728-en"
        
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

if __name__ == '__main__':
    unittest.main()
