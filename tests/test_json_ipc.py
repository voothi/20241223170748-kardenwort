import sys
import json
import pytest
from pathlib import Path

from kardenwort.core import kardenwort
from kardenwort.core.errors import ErrorCode

def test_jsonl_payload_parsing_and_escapes(tmp_path, mock_nlp, monkeypatch, capsys):
    """
    Test 3.1: Verifies JSONL payload parses successfully and handles complex/escaped text.
    """
    input_text = 'Test sentence with "quotes", \\backslashes\\, and \nnewlines.'
    input_file = tmp_path / "input.txt"
    input_file.write_text(input_text, encoding="utf-8")
    
    test_argv = [
        "kardenwort.py",
        "--type", "word",
        "--text1-file", str(input_file),
        "--structured-output"
    ]
    monkeypatch.setattr(sys, 'argv', test_argv)
    
    from kardenwort.core.errors import setup_structured_logging
    setup_structured_logging()
    
    import spacy
    monkeypatch.setattr(spacy, 'load', lambda *args, **kwargs: mock_nlp)
    
    kardenwort.main()
    
    captured = capsys.readouterr()
    lines = [l for l in captured.out.strip().split('\n') if l]
    assert len(lines) > 0
    
    for line in lines:
        record = json.loads(line)
        assert isinstance(record, dict)

def test_semantic_parity_jsonl_vs_tsv(tmp_path, mock_nlp, monkeypatch, capsys):
    """
    Test 3.2: Verifies semantic parity between JSON record schema fields and TSV columns.
    """
    input_text = "This is a simple test."
    input_file = tmp_path / "input.txt"
    input_file.write_text(input_text, encoding="utf-8")
    
    tsv_out = tmp_path / "output.tsv"
    
    # TSV mode
    test_argv_tsv = [
        "kardenwort.py",
        "--type", "word",
        "--text1-file", str(input_file),
        "--output-file", str(tsv_out),
        "--anki-csv-header", '["word","translation"]',
        "--anki-field-mapping", '{"word":"source_word","translation":"target_lemma"}'
    ]
    monkeypatch.setattr(sys, 'argv', test_argv_tsv)
    
    import spacy
    monkeypatch.setattr(spacy, 'load', lambda *args, **kwargs: mock_nlp)
    
    kardenwort.main()
    
    # JSON mode
    test_argv_json = [
        "kardenwort.py",
        "--type", "word",
        "--text1-file", str(input_file),
        "--structured-output"
    ]
    monkeypatch.setattr(sys, 'argv', test_argv_json)
    monkeypatch.setattr(spacy, 'load', lambda *args, **kwargs: mock_nlp)
    from kardenwort.core.errors import setup_structured_logging
    setup_structured_logging()
    
    kardenwort.main()
    
    captured = capsys.readouterr()
    json_lines = [l for l in captured.out.strip().split('\n') if l]
    
    tsv_lines = [l for l in tsv_out.read_text(encoding="utf-8").strip().split('\n') if l]
    
    assert len(tsv_lines) - 1 == len(json_lines)
    headers = tsv_lines[0].split('\t')
    
    for i in range(len(json_lines)):
        tsv_row = tsv_lines[i+1].split('\t')
        json_row = json.loads(json_lines[i])
        for j, header in enumerate(headers):
            if header in json_row:
                assert str(json_row[header]) == str(tsv_row[j])
                
def test_deterministic_exit_codes_missing_dict(tmp_path, mock_nlp, monkeypatch, capsys):
    """
    Test 3.3: Validate deterministic exit code routing.
    In kardenwort.py, reading a non-existent file causes sys.exit(1).
    Since we are calling main() directly without the __main__ wrapper, it should raise SystemExit(1).
    """
    test_argv = [
        "kardenwort.py",
        "--type", "word",
        "--text1-file", "nonexistent_file.txt",
        "--structured-output"
    ]
    monkeypatch.setattr(sys, 'argv', test_argv)
    
    import spacy
    monkeypatch.setattr(spacy, 'load', lambda *args, **kwargs: mock_nlp)
    
    from kardenwort.core.errors import setup_structured_logging
    setup_structured_logging()
    
    with pytest.raises(SystemExit) as exc_info:
        kardenwort.main()
    
    assert exc_info.value.code == 1
    
    captured = capsys.readouterr()
    # It prints to stderr because of our logger mapping sys.stderr to StructuredStderrLogger
    err_output = captured.err.strip()
    # Check if the error was formatted as telemetry JSON
    lines = err_output.split('\n')
    found_telemetry = False
    for line in lines:
        if not line.strip(): continue
        try:
            obj = json.loads(line)
            if "telemetry" in obj and "nonexistent_file.txt" in obj["telemetry"]:
                found_telemetry = True
        except ValueError:
            pass
    assert found_telemetry, "Non-JSON error messages should be formatted as telemetry JSON"
