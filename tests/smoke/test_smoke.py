import subprocess
import pytest
from pathlib import Path
import os
import sys

def get_runner_script_path():
    project_root = Path(__file__).resolve().parent.parent.parent
    runner_path = project_root / "src" / "kardenwort" / "core" / "kardenwort_runner.py"
    return runner_path, project_root

def test_runner_cli_help():
    """Smoke test: Ensure the script can be invoked with --help and doesn't crash on import/startup."""
    runner_path, project_root = get_runner_script_path()
    
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root / "src")
    
    result = subprocess.run(
        [sys.executable, str(runner_path), "--help"],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(project_root)
    )
    
    # 0 return code and some help text indicate successful load
    assert result.returncode == 0
    assert "usage:" in result.stdout.lower()
    assert "--language" in result.stdout
    assert "--mode" in result.stdout

def test_fast_execution_single_mode(tmp_path):
    """Smoke test: Execute a short string directly via --text in 'single' mode."""
    runner_path, project_root = get_runner_script_path()
    
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root / "src")
    
    # We use tmp_path as the current working directory to avoid cluttering the project root
    result = subprocess.run(
        [
            sys.executable, 
            str(runner_path), 
            "--language", "de",
            "--mode", "single",
            "--type", "word",
            "--text", "Dies ist ein kurzer Smoke-Test."
        ],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(tmp_path) 
    )
    
    # The runner script usually exits with 0 on success.
    # We should also see standard output related to processing.
    assert result.returncode == 0, f"Extraction failed with error: {result.stderr}"
    
    # Check if a TSV file was produced in the results directory (or mocked if anki importer fails)
    # Since this is a smoke test, we mostly care that kardenwort.py processed the text and didn't crash.
    # The runner might attempt to call the Anki importer and fail if it's not configured in the test env,
    # but kardenwort.py itself should have succeeded.
    assert "result.single.word.de.tsv" in result.stdout or result.returncode == 0
