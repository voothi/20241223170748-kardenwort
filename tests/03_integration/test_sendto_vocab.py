import configparser
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Add project root to sys.path to allow importing scripts package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import scripts.install as inst
import scripts.sendto_vocab as sv

# ==============================================================================
# UNIT TESTS FOR SENDTO_VOCAB.PY HELPERS
# ==============================================================================

def test_parse_filename():
    # Scenario 1: Sequential ZID plus numbered postfix
    p1 = Path("20260626231725-text.1.en.txt")
    zid, title, lang = sv.parse_filename(p1)
    assert zid == "20260626231725"
    assert title == "text.1"
    assert lang == "en"
    
    # Scenario 2: Plain numbered files
    p2 = Path("text1.txt")
    zid, title, lang = sv.parse_filename(p2)
    assert zid is None
    assert title == "text1"
    assert lang is None
    
    # Scenario 3: Same-ZID batch
    p3 = Path("20260626232001-text1.txt")
    zid, title, lang = sv.parse_filename(p3)
    assert zid == "20260626232001"
    assert title == "text1"
    assert lang is None

def test_detect_language():
    # Valid postfix
    paths1 = [Path("text.1.en.txt"), Path("text.2.de.txt")]
    assert sv.detect_language(paths1, "de") == "en"
    
    # Unsupported postfix
    paths2 = [Path("text.1.ru.txt")]
    assert sv.detect_language(paths2, "en") == "en"
    
    # No postfix
    paths3 = [Path("text1.txt")]
    assert sv.detect_language(paths3, "de") == "de"

def test_sort_send_order():
    # Mix of different files to check sorting keys
    paths = [
        Path("20260626232001-text3.txt"),
        Path("20260626231725-text.1.en.txt"),
        Path("text2.txt"),
        Path("20260626232001-text1.txt"),
        Path("text1.txt")
    ]
    
    sorted_paths = sv.sort_send_order(paths)
    expected = [
        Path("text1.txt"),
        Path("text2.txt"),
        Path("20260626231725-text.1.en.txt"),
        Path("20260626232001-text1.txt"),
        Path("20260626232001-text3.txt")
    ]
    assert sorted_paths == expected

def test_clean_subtitle_text():
    raw_sub = "Hello <i>world</i>! Welcome {\\an8}here. <b>Enjoy</b> the show."
    cleaned = sv.clean_subtitle_text(raw_sub)
    assert cleaned == "Hello world! Welcome here. Enjoy the show."

def test_stage_inputs_txt_and_srt(tmp_path):
    sent_dir = tmp_path / "session"
    sent_dir.mkdir()
    
    t1 = sent_dir / "input1.txt"
    t1.write_text("Hello plain text.", encoding="utf-8")
    
    t2 = sent_dir / "input2.srt"
    t2.write_text(
        "1\n"
        "00:00:01,000 --> 00:00:03,000\n"
        "Hello <i>subtitles</i>!\n"
        "\n"
        "2\n"
        "00:00:04,000 --> 00:00:06,000\n"
        "Line two.\n"
        "Line three.\n",
        encoding="utf-8"
    )
    
    slots = sv.resolve_slots([t1, t2], {"en": 1, "de": 2, "ru": 3}, "en", "en")
    staged = sv.stage_inputs(slots, sent_dir)
    
    assert len(staged) == 3
    assert staged[0].read_text(encoding="utf-8") == "Hello plain text."
    
    # Asserting that lines are separated by newline (\n) as in whisper project
    staged_srt_content = staged[1].read_text(encoding="utf-8")
    assert staged_srt_content == "Hello subtitles!\nLine two.\nLine three."
    
    # Slot 3 is empty placeholder
    assert staged[2].read_text(encoding="utf-8") == ""

def test_resolve_slots_by_language_and_index():
    lang_slots = {"en": 1, "de": 2, "ru": 3}
    
    # Case 1: Language-based mapping for 2 files (en and ru) -> slots 1 and 3
    p_en = Path("20260606211142-anthropic-just-warned-everyone.en.srt")
    p_ru = Path("20260606211142-anthropic-just-warned-everyone.ru.srt")
    slots = sv.resolve_slots([p_en, p_ru], lang_slots, "en", "en")
    assert slots[1] == p_en
    assert slots[2] is None
    assert slots[3] == p_ru
    
    # Case 2: Index-based mapping (file1.txt and file3.txt) -> slots 1 and 3
    p1 = Path("file1.txt")
    p3 = Path("file3.txt")
    slots = sv.resolve_slots([p1, p3], lang_slots, "en", "en")
    assert slots[1] == p1
    assert slots[2] is None
    assert slots[3] == p3
    
    # Case 3: Mixed case and fallbacks
    p_extra = Path("unmapped.txt")
    slots = sv.resolve_slots([p_en, p_ru, p_extra], lang_slots, "en", "en")
    assert slots[1] == p_en
    assert slots[2] == p_extra # Fallback to first available empty slot
    assert slots[3] == p_ru
    
    # Case 4: German is source language, should map to slot 1 even though de:2 is in mapping
    p_de = Path("20260606211142-anthropic-just-warned-everyone.de.srt")
    slots = sv.resolve_slots([p_de, p_ru], lang_slots, "en", "de")
    assert slots[1] == p_de
    assert slots[2] is None
    assert slots[3] == p_ru
    
    # Case 5: User's exact config mapping string
    user_slots_str = "en:1, de:1, ru:3, 1.en:1, 1.de:1, 2.ru:2, 3.ru:3, text1:1, text2:2, text3:3"
    user_lang_slots = {}
    for item in user_slots_str.split(','):
        k, v = item.split(':', 1)
        user_lang_slots[k.strip().lower()] = int(v.strip())
    
    slots = sv.resolve_slots([p_en, p_ru], user_lang_slots, "en", "en")
    assert slots[1] == p_en
    assert slots[2] is None
    assert slots[3] == p_ru

# ==============================================================================
# INTEGRATION TESTS FOR HARDENED SENDTO_VOCAB.PY
# ==============================================================================

def test_sendto_vocab_full_flow(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    results_dir = workspace / "results"
    results_dir.mkdir()
    
    # Create mock runner script so path exists
    runner_path = workspace / "src" / "kardenwort" / "core" / "runner.py"
    runner_path.parent.mkdir(parents=True, exist_ok=True)
    runner_path.write_text("# mock runner", encoding="utf-8")
    
    sent_dir = tmp_path / "sent_files"
    sent_dir.mkdir()
    
    # Mock load_config
    config = configparser.ConfigParser()
    config.read_string(
        "[environment]\n"
        "python_executable = python\n"
        f"kardenwort_workspace = {workspace.as_posix()}\n"
        "[scripts]\n"
        "kardenwort_runner_filename = runner.py\n"
        "[project_structure]\n"
        "generated_results_dir = results\n"
    )
    monkeypatch.setattr(sv, "load_config", lambda: (workspace, config))
    
    # Mock subprocess.run to simulate a successful runner execution
    called_args = []
    def mock_run(args, **kwargs):
        called_args.append(args)
        # Simulate runner writing a new result file
        res_file = results_dir / "20260626232001-mock.triple.sentence.en.tsv"
        res_file.write_text("mock sentence tsv", encoding="utf-8")
        res_json = results_dir / "20260626232001-mock.triple.sentence.en.json"
        res_json.write_text("{}", encoding="utf-8")
        
        # Return a mock completed process
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        return mock_proc
        
    monkeypatch.setattr(subprocess, "run", mock_run)
    
    # Create input file
    f1 = sent_dir / "text1.txt"
    f1.write_text("Sentence content", encoding="utf-8")
    
    # Mock sys.argv to simulate SendTo call
    monkeypatch.setattr(sys, "argv", ["sendto_vocab.py", "--sendto", str(f1)])
    
    # Run main
    sv.main()
    
    # Assertions
    staged_dir = sent_dir / "source_texts"
    assert not staged_dir.exists()  # Staging directory cleaned up on success
    
    # Runner was called with correct arguments
    assert len(called_args) == 1
    run_args = called_args[0]
    assert "--mode" in run_args
    assert "mixed-triple" in run_args
    
    # Results were relocated
    relocated_tsv = sent_dir / "results" / "20260626232001-mock.triple.sentence.en.tsv"
    relocated_json = sent_dir / "results" / "20260626232001-mock.triple.sentence.en.json"
    assert relocated_tsv.exists()
    assert relocated_json.exists()
    assert not (results_dir / "20260626232001-mock.triple.sentence.en.tsv").exists()

def test_sendto_skip_import(tmp_path, monkeypatch):
    """Verify that --skip-import is passed to the runner when configured to False."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    results_dir = workspace / "results"
    results_dir.mkdir()
    
    runner_path = workspace / "src" / "kardenwort" / "core" / "runner.py"
    runner_path.parent.mkdir(parents=True, exist_ok=True)
    runner_path.write_text("# mock runner", encoding="utf-8")
    
    sent_dir = tmp_path / "sent_files"
    sent_dir.mkdir()
    
    config = configparser.ConfigParser()
    config.read_string(
        "[environment]\n"
        "python_executable = python\n"
        f"kardenwort_workspace = {workspace.as_posix()}\n"
        "[scripts]\n"
        "kardenwort_runner_filename = runner.py\n"
        "[project_structure]\n"
        "generated_results_dir = results\n"
        "[sendto]\n"
        "sendto_upload_to_anki = False\n"
    )
    monkeypatch.setattr(sv, "load_config", lambda: (workspace, config))
    
    called_args = []
    def mock_run(args, **kwargs):
        called_args.append(args)
        # Simulate runner output
        res_file = results_dir / "20260626232001-mock.triple.sentence.en.tsv"
        res_file.write_text("mock", encoding="utf-8")
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        return mock_proc
        
    monkeypatch.setattr(subprocess, "run", mock_run)
    
    f1 = sent_dir / "text1.txt"
    f1.write_text("content", encoding="utf-8")
    
    monkeypatch.setattr(sys, "argv", ["sendto_vocab.py", "--sendto", str(f1)])
    
    sv.main()
    
    assert len(called_args) == 1
    run_args = called_args[0]
    assert "--skip-import" in run_args

def test_sendto_extraction_mode(tmp_path, monkeypatch):
    """Verify that --mode and --type are correctly built based on configured extraction mode."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    results_dir = workspace / "results"
    results_dir.mkdir()
    
    runner_path = workspace / "src" / "kardenwort" / "core" / "runner.py"
    runner_path.parent.mkdir(parents=True, exist_ok=True)
    runner_path.write_text("# mock runner", encoding="utf-8")
    
    sent_dir = tmp_path / "sent_files"
    sent_dir.mkdir()
    
    config = configparser.ConfigParser()
    config.read_string(
        "[environment]\n"
        "python_executable = python\n"
        f"kardenwort_workspace = {workspace.as_posix()}\n"
        "[scripts]\n"
        "kardenwort_runner_filename = runner.py\n"
        "[project_structure]\n"
        "generated_results_dir = results\n"
        "[sendto]\n"
        "sendto_extraction_mode = word\n"
    )
    monkeypatch.setattr(sv, "load_config", lambda: (workspace, config))
    
    called_args = []
    def mock_run(args, **kwargs):
        called_args.append(args)
        # Simulate runner output
        res_file = results_dir / "20260626232001-mock.triple.word.en.tsv"
        res_file.write_text("mock", encoding="utf-8")
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        return mock_proc
        
    monkeypatch.setattr(subprocess, "run", mock_run)
    
    f1 = sent_dir / "text1.txt"
    f1.write_text("content", encoding="utf-8")
    
    monkeypatch.setattr(sys, "argv", ["sendto_vocab.py", "--sendto", str(f1)])
    
    sv.main()
    
    assert len(called_args) == 1
    run_args = called_args[0]
    
    # Assert that mode is 'triple' and type is 'word'
    assert "--mode" in run_args
    assert "triple" in run_args
    assert "--type" in run_args
    assert "word" in run_args

def test_sendto_auto_close_timeout(tmp_path, monkeypatch):
    """Verify that pause_console is called with the configured timeout_secs."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    results_dir = workspace / "results"
    results_dir.mkdir()
    
    runner_path = workspace / "src" / "kardenwort" / "core" / "runner.py"
    runner_path.parent.mkdir(parents=True, exist_ok=True)
    runner_path.write_text("# mock runner", encoding="utf-8")
    
    sent_dir = tmp_path / "sent_files"
    sent_dir.mkdir()
    
    config = configparser.ConfigParser()
    config.read_string(
        "[environment]\n"
        "python_executable = python\n"
        f"kardenwort_workspace = {workspace.as_posix()}\n"
        "[scripts]\n"
        "kardenwort_runner_filename = runner.py\n"
        "[project_structure]\n"
        "generated_results_dir = results\n"
        "[sendto]\n"
        "sendto_auto_close_timeout_secs = 5\n"
    )
    monkeypatch.setattr(sv, "load_config", lambda: (workspace, config))
    
    # Mock subprocess.run
    def mock_run(args, **kwargs):
        res_file = results_dir / "20260626232001-mock.triple.sentence.en.tsv"
        res_file.write_text("mock", encoding="utf-8")
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        return mock_proc
    monkeypatch.setattr(subprocess, "run", mock_run)
    
    # Mock pause_console to capture call args
    captured_calls = []
    def mock_pause_console(success, timeout_secs):
        captured_calls.append((success, timeout_secs))
    monkeypatch.setattr(sv, "pause_console", mock_pause_console)
    
    f1 = sent_dir / "text1.txt"
    f1.write_text("content", encoding="utf-8")
    
    monkeypatch.setattr(sys, "argv", ["sendto_vocab.py", "--sendto", "--pause", str(f1)])
    
    sv.main()
    
    assert len(captured_calls) == 1
    assert captured_calls[0] == (True, 5)
    
    # Case 2: Negative value configured (disabling auto-close)
    config.set("sendto", "sendto_auto_close_timeout_secs", "-1")
    captured_calls.clear()
    sv.main()
    assert len(captured_calls) == 1
    assert captured_calls[0] == (True, -1)

def test_concurrent_writer(tmp_path, monkeypatch):
    """Scenario 12.3: Verify foreign files are not relocated."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    results_dir = workspace / "results"
    results_dir.mkdir()
    
    # Create mock runner script
    runner_path = workspace / "src" / "kardenwort" / "core" / "runner.py"
    runner_path.parent.mkdir(parents=True, exist_ok=True)
    runner_path.write_text("# mock", encoding="utf-8")
    
    sent_dir = tmp_path / "sent_files"
    sent_dir.mkdir()
    
    config = configparser.ConfigParser()
    config.read_string(
        "[environment]\n"
        "python_executable = python\n"
        f"kardenwort_workspace = {workspace.as_posix()}\n"
        "[scripts]\n"
        "kardenwort_runner_filename = runner.py\n"
        "[project_structure]\n"
        "generated_results_dir = results\n"
    )
    monkeypatch.setattr(sv, "load_config", lambda: (workspace, config))
    
    # Mock subprocess.run: simulates runner writing new results AND a foreign writer placing a file
    def mock_run(args, **kwargs):
        # Runner writes its files
        (results_dir / "mock.triple.sentence.en.tsv").write_text("runner", encoding="utf-8")
        
        # Concurrent writer writes a foreign file
        (results_dir / "foreign_file.tsv").write_text("foreign content", encoding="utf-8")
        
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        return mock_proc
        
    monkeypatch.setattr(subprocess, "run", mock_run)
    
    f1 = sent_dir / "text1.txt"
    f1.write_text("content", encoding="utf-8")
    
    # Mock sys.argv
    monkeypatch.setattr(sys, "argv", ["sendto_vocab.py", "--sendto", str(f1)])
    
    # Run
    sv.main()
    
    # Assertions
    # 1. Runner's file is relocated
    assert (sent_dir / "results" / "mock.triple.sentence.en.tsv").exists()
    # 2. Foreign file is NOT relocated (stays in project results/)
    assert not (sent_dir / "results" / "foreign_file.tsv").exists()
    assert (results_dir / "foreign_file.tsv").exists()

def test_atomic_overwrite_and_rollback(tmp_path, monkeypatch):
    """Scenario 12.4: Verify atomic replacement and rollback on relocation failure."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    results_dir = workspace / "results"
    results_dir.mkdir()
    
    runner_path = workspace / "src" / "kardenwort" / "core" / "runner.py"
    runner_path.parent.mkdir(parents=True, exist_ok=True)
    runner_path.write_text("# mock", encoding="utf-8")
    
    sent_dir = tmp_path / "sent_files"
    sent_dir.mkdir()
    
    # Pre-create results folder next to source with an existing file to test overwrite
    src_results_dir = sent_dir / "results"
    src_results_dir.mkdir(parents=True, exist_ok=True)
    existing_dest_file = src_results_dir / "mock.triple.sentence.en.tsv"
    existing_dest_file.write_text("old content", encoding="utf-8")
    
    config = configparser.ConfigParser()
    config.read_string(
        "[environment]\n"
        "python_executable = python\n"
        f"kardenwort_workspace = {workspace.as_posix()}\n"
        "[scripts]\n"
        "kardenwort_runner_filename = runner.py\n"
        "[project_structure]\n"
        "generated_results_dir = results\n"
    )
    monkeypatch.setattr(sv, "load_config", lambda: (workspace, config))
    
    # Mock runner: creates two result files
    def mock_run(args, **kwargs):
        (results_dir / "mock.triple.sentence.en.tsv").write_text("new content", encoding="utf-8")
        (results_dir / "mock.triple.sentence.en.json").write_text("{}", encoding="utf-8")
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        return mock_proc
        
    monkeypatch.setattr(subprocess, "run", mock_run)
    
    # Mock shutil.move to fail on the second file (.json) to trigger rollback
    original_move = shutil.move
    def mock_move(src, dst, *args, **kwargs):
        if "mock.triple.sentence.en.json" in str(src):
            raise IOError("Simulated move failure")
        return original_move(src, dst, *args, **kwargs)
    monkeypatch.setattr(shutil, "move", mock_move)
    
    f1 = sent_dir / "text1.txt"
    f1.write_text("content", encoding="utf-8")
    
    monkeypatch.setattr(sys, "argv", ["sendto_vocab.py", "--sendto", str(f1)])
    
    # Run should raise SystemExit because of hard relocation failure
    with pytest.raises(SystemExit) as exc:
        sv.main()
    assert exc.value.code == 1
    
    # Assertions
    # 1. Rollback occurred: the first file was restored back to project results/
    assert (results_dir / "mock.triple.sentence.en.tsv").exists()
    assert (results_dir / "mock.triple.sentence.en.json").exists()
    
    # 2. The existing destination file next to source remains untouched with its original content
    assert existing_dest_file.read_text(encoding="utf-8") == "old content"

def test_language_detection_first_selected(tmp_path, monkeypatch):
    """Scenario 12.5: Language detected from first selected file regardless of sort order."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    results_dir = workspace / "results"
    results_dir.mkdir()
    
    runner_path = workspace / "src" / "kardenwort" / "core" / "runner.py"
    runner_path.parent.mkdir(parents=True, exist_ok=True)
    runner_path.write_text("# mock", encoding="utf-8")
    
    sent_dir = tmp_path / "sent_files"
    sent_dir.mkdir()
    
    config = configparser.ConfigParser()
    config.read_string(
        "[environment]\n"
        "python_executable = python\n"
        f"kardenwort_workspace = {workspace.as_posix()}\n"
        "[scripts]\n"
        "kardenwort_runner_filename = runner.py\n"
        "[project_structure]\n"
        "generated_results_dir = results\n"
    )
    monkeypatch.setattr(sv, "load_config", lambda: (workspace, config))
    
    # We send a .de file first, and a .en file second.
    # Note that 20260626231737-text.2.de.txt sorts *after* 20260626231725-text.1.en.txt.
    # But because it was selected first (comes first in sys.argv), the language should be "de"!
    f_de = sent_dir / "20260626231737-text.2.de.txt"
    f_en = sent_dir / "20260626231725-text.1.en.txt"
    
    f_de.write_text("German content", encoding="utf-8")
    f_en.write_text("English content", encoding="utf-8")
    
    called_args = []
    def mock_run(args, **kwargs):
        called_args.append(args)
        # Simulate writing result
        (results_dir / "mock.triple.sentence.de.tsv").write_text("content", encoding="utf-8")
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        return mock_proc
        
    monkeypatch.setattr(subprocess, "run", mock_run)
    
    # sys.argv has f_de first
    monkeypatch.setattr(sys, "argv", ["sendto_vocab.py", "--sendto", str(f_de), str(f_en)])
    
    sv.main()
    
    # Assertions
    assert len(called_args) == 1
    run_args = called_args[0]
    # Check that --language is de
    assert "--language" in run_args
    assert run_args[run_args.index("--language") + 1] == "de"
    print("✓ Language detected from first selected file correctly")

def test_sendto_relocation_on_runner_failure(tmp_path, monkeypatch):
    """Verify that generated TSV/JSON files are still relocated even if the runner fails."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    results_dir = workspace / "results"
    results_dir.mkdir()
    
    runner_path = workspace / "src" / "kardenwort" / "core" / "runner.py"
    runner_path.parent.mkdir(parents=True, exist_ok=True)
    runner_path.write_text("# mock runner", encoding="utf-8")
    
    sent_dir = tmp_path / "sent_files"
    sent_dir.mkdir()
    
    config = configparser.ConfigParser()
    config.read_string(
        "[environment]\n"
        "python_executable = python\n"
        f"kardenwort_workspace = {workspace.as_posix()}\n"
        "[scripts]\n"
        "kardenwort_runner_filename = runner.py\n"
        "[project_structure]\n"
        "generated_results_dir = results\n"
    )
    monkeypatch.setattr(sv, "load_config", lambda: (workspace, config))
    
    # Mock subprocess.run to raise CalledProcessError (importer failure)
    # but simulate that the extraction step had already written the TSV file
    def mock_run(args, **kwargs):
        res_file = results_dir / "20260626232001-mock.triple.sentence.en.tsv"
        res_file.write_text("mock content", encoding="utf-8")
        
        # Raise error representing importer failure
        raise subprocess.CalledProcessError(1, args)
        
    monkeypatch.setattr(subprocess, "run", mock_run)
    
    f1 = sent_dir / "text1.txt"
    f1.write_text("content", encoding="utf-8")
    
    monkeypatch.setattr(sys, "argv", ["sendto_vocab.py", "--sendto", str(f1)])
    
    # The script should fail and raise SystemExit
    with pytest.raises(SystemExit) as exc:
        sv.main()
    assert exc.value.code == 1
    
    # Verify that the TSV file was successfully relocated despite the runner failure
    relocated_tsv = sent_dir / "results" / "20260626232001-mock.triple.sentence.en.tsv"
    assert relocated_tsv.exists()
    assert relocated_tsv.read_text(encoding="utf-8") == "mock content"

def test_sendto_relocate_to_root(tmp_path, monkeypatch):
    """Verify that results are relocated directly to the dropped folder root if subfolder is empty."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    results_dir = workspace / "results"
    results_dir.mkdir()
    
    runner_path = workspace / "src" / "kardenwort" / "core" / "runner.py"
    runner_path.parent.mkdir(parents=True, exist_ok=True)
    runner_path.write_text("# mock runner", encoding="utf-8")
    
    sent_dir = tmp_path / "sent_files"
    sent_dir.mkdir()
    
    config = configparser.ConfigParser()
    config.read_string(
        "[environment]\n"
        "python_executable = python\n"
        f"kardenwort_workspace = {workspace.as_posix()}\n"
        "[scripts]\n"
        "kardenwort_runner_filename = runner.py\n"
        "[project_structure]\n"
        "generated_results_dir = results\n"
        "[sendto]\n"
        "sendto_relocation_subfolder = \n"
    )
    monkeypatch.setattr(sv, "load_config", lambda: (workspace, config))
    
    def mock_run(args, **kwargs):
        res_file = results_dir / "20260626232001-mock.triple.sentence.en.tsv"
        res_file.write_text("root content", encoding="utf-8")
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        return mock_proc
        
    monkeypatch.setattr(subprocess, "run", mock_run)
    
    f1 = sent_dir / "text1.txt"
    f1.write_text("content", encoding="utf-8")
    
    monkeypatch.setattr(sys, "argv", ["sendto_vocab.py", "--sendto", str(f1)])
    
    sv.main()
    
    # Verify that the TSV file was successfully relocated directly into sent_dir (root)
    relocated_tsv = sent_dir / "20260626232001-mock.triple.sentence.en.tsv"
    assert relocated_tsv.exists()
    assert relocated_tsv.read_text(encoding="utf-8") == "root content"
    assert not (sent_dir / "results").exists()

# ==============================================================================
# INTEGRATION TESTS FOR INSTALL.PY
# ==============================================================================

def test_install_script(tmp_path, monkeypatch):
    # Override SENDTO_DIRECTORY to a temp folder under tmp_path
    temp_sendto = tmp_path / "SendTo"
    monkeypatch.setattr(inst, "SENDTO_DIRECTORY", str(temp_sendto))
    
    # Create a legacy shortcut to verify cleanup
    temp_sendto.mkdir(parents=True, exist_ok=True)
    legacy_shortcut = temp_sendto / "Kardenwort Vocab Processor.lnk"
    legacy_shortcut.write_text("old shortcut content", encoding="utf-8")
    
    # Run the installer main
    inst.main()
    
    # Assertions
    # 1. Legacy shortcut should be deleted
    assert not legacy_shortcut.exists()
    
    # 2. New shortcut should be created by the OS's PowerShell COM script
    new_shortcut = temp_sendto / "Kardenwort Vocab.lnk"
    assert new_shortcut.exists()
