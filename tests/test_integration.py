import subprocess
import unittest
from pathlib import Path
import os
import sys

class TestIntegration(unittest.TestCase):
    def setUp(self):
        self.project_root = Path(__file__).resolve().parent.parent
        self.runner_path = self.project_root / "src" / "kardenwort" / "core" / "kardenwort_runner.py"
        
        # Determine python executable from config.ini if possible, otherwise use sys.executable
        # For simplicity in this test, we use sys.executable but ensure src is in PYTHONPATH
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

    def test_german_mixed_triple(self):
        # We use the defaults from config.ini (which should point to text1.txt, etc.)
        # Or we can pass --text if we want to be isolated, but the plan asked for cases in tests/cases.
        # However, kardenwort_runner.py currently reads text files from source_texts_dir in config.ini.
        
        args = [
            "--language", "de",
            "--mode", "mixed-triple",
            "--deduplication-scope", "global",
            "--suspend-cards"
        ]
        
        result = self.run_runner(args)
        
        if result.returncode != 0:
            print(f"STDOUT: {result.stdout}")
            print(f"STDERR: {result.stderr}")
            
        self.assertEqual(result.returncode, 0, f"Runner failed with: {result.stderr}")
        self.assertIn("All operations for mixed-triple mode completed successfully", result.stderr)

    def test_english_mixed_triple(self):
        args = [
            "--language", "en",
            "--mode", "mixed-triple",
            "--deduplication-scope", "global"
        ]
        
        result = self.run_runner(args)
        self.assertEqual(result.returncode, 0, f"Runner failed with: {result.stderr}")
        self.assertIn("All operations for mixed-triple mode completed successfully", result.stderr)

if __name__ == '__main__':
    unittest.main()
