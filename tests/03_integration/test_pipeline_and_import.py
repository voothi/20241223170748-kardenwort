import os
import sys
import pytest
import tempfile
import configparser
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root and src/kardenwort/core to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src" / "kardenwort" / "core"))

import kardenwort_runner

def mock_exit_fn(code=0):
    raise SystemExit(code)

def test_pipeline_validation():
    # Helper to test config parser validation
    # Test unknown stage
    with patch("sys.exit", side_effect=mock_exit_fn) as mock_exit, patch("kardenwort_runner.load_config") as mock_load:
        mock_load.return_value = (
            Path("python.exe"),
            Path("workspace"),
            Path("importer"),
            configparser.ConfigParser()
        )
        # Mock sys.argv
        sys_argv_mock = ["kardenwort_runner.py", "--mode", "triple", "--language", "en", "--type", "word"]
        with patch("sys.argv", sys_argv_mock), patch("argparse.ArgumentParser.parse_args") as mock_parse:
            args = MagicMock()
            args.mode = "triple"
            args.language = "en"
            args.type = "word"
            args.import_only = False
            mock_parse.return_value = args
            
            # Configure bad config
            cfg = configparser.ConfigParser()
            cfg.add_section("pipeline")
            cfg.set("pipeline", "stages", "extract, invalid_stage")
            mock_load.return_value = (Path("python.exe"), Path("workspace"), Path("importer"), cfg)
            
            with pytest.raises(SystemExit) as excinfo:
                kardenwort_runner.main()
            assert excinfo.value.code == 1

def test_pipeline_out_of_order():
    # Test out of order stages
    with patch("sys.exit", side_effect=mock_exit_fn) as mock_exit, patch("kardenwort_runner.load_config") as mock_load:
        cfg = configparser.ConfigParser()
        cfg.add_section("pipeline")
        cfg.set("pipeline", "stages", "import, extract") # Out of order
        mock_load.return_value = (Path("python.exe"), Path("workspace"), Path("importer"), cfg)
        
        sys_argv_mock = ["kardenwort_runner.py", "--mode", "triple", "--language", "en", "--type", "word"]
        with patch("sys.argv", sys_argv_mock), patch("argparse.ArgumentParser.parse_args") as mock_parse:
            args = MagicMock()
            args.mode = "triple"
            args.language = "en"
            args.type = "word"
            args.import_only = False
            mock_parse.return_value = args
            
            with pytest.raises(SystemExit) as excinfo:
                kardenwort_runner.main()
            assert excinfo.value.code == 1

def test_import_only_mode(tmp_path):
    # Test --import-only mode directly calls run_importer_script and exits
    tsv_file = tmp_path / "test.tsv"
    tsv_file.touch()
    
    with patch("kardenwort_runner.run_importer_script") as mock_importer, patch("sys.exit", side_effect=mock_exit_fn) as mock_exit:
        sys_argv_mock = ["kardenwort_runner.py", "--import-only", "--tsv", str(tsv_file)]
        with patch("sys.argv", sys_argv_mock), patch("argparse.ArgumentParser.parse_args") as mock_parse:
            args = MagicMock()
            args.import_only = True
            args.tsv = str(tsv_file)
            mock_parse.return_value = args
            
            cfg = configparser.ConfigParser()
            cfg.add_section("environment")
            cfg.set("environment", "python_executable", "python.exe")
            cfg.set("environment", "kardenwort_workspace", "workspace")
            cfg.set("environment", "importer_workspace", "importer")
            
            with patch("kardenwort_runner.load_config") as mock_load:
                mock_load.return_value = (Path("python.exe"), Path("workspace"), Path("importer"), cfg)
                with pytest.raises(SystemExit) as excinfo:
                    kardenwort_runner.main()
                
                # Check run_importer_script is called
                mock_importer.assert_called_once()
                # Check it exits with 0
                assert excinfo.value.code == 0


def test_import_only_mode_multiple_files_with_filtering(tmp_path):
    tsv_file1 = tmp_path / "test1.tsv"
    tsv_file1.touch()
    tsv_file2 = tmp_path / "test2.tsv"
    tsv_file2.touch()
    txt_file = tmp_path / "test.txt"
    txt_file.touch()
    
    with patch("kardenwort_runner.run_importer_script") as mock_importer, patch("sys.exit", side_effect=mock_exit_fn) as mock_exit:
        sys_argv_mock = ["kardenwort_runner.py", "--import-only", "--tsv", str(tsv_file1), str(txt_file), str(tsv_file2)]
        with patch("sys.argv", sys_argv_mock), patch("argparse.ArgumentParser.parse_args") as mock_parse:
            args = MagicMock()
            args.import_only = True
            args.tsv = [str(tsv_file1), str(txt_file), str(tsv_file2)]
            mock_parse.return_value = args
            
            cfg = configparser.ConfigParser()
            cfg.add_section("environment")
            cfg.set("environment", "python_executable", "python.exe")
            cfg.set("environment", "kardenwort_workspace", "workspace")
            cfg.set("environment", "importer_workspace", "importer")
            
            with patch("kardenwort_runner.load_config") as mock_load:
                mock_load.return_value = (Path("python.exe"), Path("workspace"), Path("importer"), cfg)
                with pytest.raises(SystemExit) as excinfo:
                    kardenwort_runner.main()
                
                # Check run_importer_script is called twice (for the two TSV files, ignoring the txt file)
                assert mock_importer.call_count == 2
                calls = [call[0][0] for call in mock_importer.call_args_list]
                assert str(tsv_file1) in calls
                assert str(tsv_file2) in calls
                assert str(txt_file) not in calls
                # Check it exits with 0
                assert excinfo.value.code == 0
