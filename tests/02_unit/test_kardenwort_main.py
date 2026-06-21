import sys
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add src to sys.path to allow importing from kardenwort
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / 'src'))

# Import the main function we want to test
from kardenwort.core.kardenwort import main

@pytest.fixture
def mock_config_lite_enabled():
    with patch('configparser.ConfigParser') as mock_cp, \
         patch('pathlib.Path.exists', return_value=True):
        instance = mock_cp.return_value
        instance.__contains__.side_effect = lambda k: k == 'optimization'
        instance.getboolean.side_effect = lambda s, k, fallback=False: True if s == 'optimization' and k == 'auto_lite_mode' else fallback
        yield

@pytest.fixture
def mock_config_lite_disabled():
    with patch('configparser.ConfigParser') as mock_cp, \
         patch('pathlib.Path.exists', return_value=True):
        instance = mock_cp.return_value
        instance.__contains__.side_effect = lambda k: k == 'optimization'
        instance.getboolean.side_effect = lambda s, k, fallback=False: False
        yield

@pytest.fixture
def mock_kardenwort_lite():
    with patch.dict('sys.modules', {'kardenwort_lite': MagicMock()}):
        import kardenwort_lite
        def mock_lite_main():
            print("mock_lemma", end="")
        kardenwort_lite.main.side_effect = mock_lite_main
        yield kardenwort_lite

@pytest.fixture
def mock_spacy_and_argparse():
    # Mock spacy and argparse to prevent heavy initialization and parse errors when falling back
    with patch.dict('sys.modules', {'spacy': MagicMock()}), \
         patch('argparse.ArgumentParser.parse_args') as mock_parse:
        mock_parse.side_effect = SystemExit(99) # Unique exit code to indicate fallback
        yield mock_parse

def test_auto_lite_single_word_direct_arg(mock_config_lite_enabled, mock_kardenwort_lite, mock_spacy_and_argparse, capsys):
    with patch.object(sys, 'argv', ['kardenwort.py', 'Hund']):
        with pytest.raises(SystemExit) as exc_info:
            main()
        
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert captured.out == "mock_lemma"
        
        mock_kardenwort_lite.main.assert_called_once()
        assert sys.argv == ['kardenwort.py', 'Hund']

def test_auto_lite_single_word_text_arg(mock_config_lite_enabled, mock_kardenwort_lite, mock_spacy_and_argparse, capsys):
    with patch.object(sys, 'argv', ['kardenwort.py', '--text', 'Katze', '--language', 'de']):
        with pytest.raises(SystemExit) as exc_info:
            main()
            
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert captured.out == "mock_lemma"
        
        mock_kardenwort_lite.main.assert_called_once()
        assert sys.argv == ['kardenwort.py', '--langs=de', 'Katze']

def test_auto_lite_html_format(mock_config_lite_enabled, mock_kardenwort_lite, mock_spacy_and_argparse, capsys):
    with patch.object(sys, 'argv', ['kardenwort.py', '--text', 'Vogel', '--stdout-format', 'html']):
        with pytest.raises(SystemExit) as exc_info:
            main()
            
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "<table>" in captured.out
        assert "<td>mock_lemma</td>" in captured.out
        assert "<td>Vogel</td>" in captured.out

def test_fallback_multiple_words(mock_config_lite_enabled, mock_kardenwort_lite, mock_spacy_and_argparse):
    with patch.object(sys, 'argv', ['kardenwort.py', 'ein Hund']):
        with pytest.raises(SystemExit) as exc_info:
            main()
        
        assert exc_info.value.code == 99
        mock_kardenwort_lite.main.assert_not_called()

def test_fallback_output_file_arg(mock_config_lite_enabled, mock_kardenwort_lite, mock_spacy_and_argparse):
    with patch.object(sys, 'argv', ['kardenwort.py', 'Hund', '--output-file', 'out.txt']):
        with pytest.raises(SystemExit) as exc_info:
            main()
        
        assert exc_info.value.code == 99
        mock_kardenwort_lite.main.assert_not_called()

def test_fallback_stdout_print_output_basename_arg(mock_config_lite_enabled, mock_kardenwort_lite, mock_spacy_and_argparse):
    with patch.object(sys, 'argv', ['kardenwort.py', 'Hund', '--stdout-print-output-basename']):
        with pytest.raises(SystemExit) as exc_info:
            main()
        
        assert exc_info.value.code == 99
        mock_kardenwort_lite.main.assert_not_called()

def test_fallback_lite_disabled(mock_config_lite_disabled, mock_kardenwort_lite, mock_spacy_and_argparse):
    with patch.object(sys, 'argv', ['kardenwort.py', 'Hund']):
        with pytest.raises(SystemExit) as exc_info:
            main()
            
        assert exc_info.value.code == 99
        mock_kardenwort_lite.main.assert_not_called()

def test_fallback_import_error(mock_config_lite_enabled, mock_spacy_and_argparse):
    # Mask out kardenwort_lite to trigger ImportError
    with patch.dict('sys.modules', {'kardenwort_lite': None}):
        with patch.object(sys, 'argv', ['kardenwort.py', 'Hund']):
            with pytest.raises(SystemExit) as exc_info:
                main()
                
            assert exc_info.value.code == 99
            # Verify argv is reverted correctly
            assert sys.argv == ['kardenwort.py', 'Hund']
