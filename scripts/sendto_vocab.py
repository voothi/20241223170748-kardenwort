#!/usr/bin/env python
# ==============================================================================
# Kardenwort SendTo Vocab Processor
# Accepts dropped files, stages inputs, runs extraction, and saves results.
#
# Usage (CLI):
#   python sendto_vocab.py --sendto --pause <files>
# ==============================================================================

import argparse
import configparser
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Tuple, Optional

# ==============================================================================
# GLOBAL CONSTANTS
# ==============================================================================
PAUSE_AUTO_CLOSE_TIMEOUT_SECS = 15

# ==============================================================================
# CONSOLE OUTPUT HELPERS
# ==============================================================================
_IS_TTY = sys.stdout.isatty()

def _c(code, text):
    return f"\x1b[{code}m{text}\x1b[0m" if _IS_TTY else text

def _tag_info():    return _c("1;36", "[INFO]")    # bold cyan
def _tag_warn():    return _c("1;33", "[WARN]")    # bold yellow
def _tag_error():   return _c("1;31", "[ERROR]")   # bold red
def _tag_ok():      return _c("1;32", "[OK]")      # bold green

def log_info(msg):
    print(f"{_tag_info()} {msg}", flush=True)

def log_warn(msg):
    print(f"{_tag_warn()} {msg}", flush=True)

def log_error(msg):
    print(f"{_tag_error()} {msg}", file=sys.stderr, flush=True)

def log_ok(msg):
    print(f"{_tag_ok()} {msg}", flush=True)

# ==============================================================================
# CONFIGURATION LOADING
# ==============================================================================
def load_config() -> Tuple[Path, configparser.ConfigParser]:
    """Loads configuration settings from the project's config.ini."""
    config_path = Path(__file__).resolve().parent.parent / "config.ini"
    if not config_path.exists():
        log_error(f"Configuration file not found at {config_path}")
        sys.exit(1)
        
    config = configparser.ConfigParser(allow_no_value=True)
    config.optionxform = str
    config.read(config_path, encoding="utf-8")
    return config_path.parent, config

# ==============================================================================
# FILENAME PARSING
# ==============================================================================
def parse_filename(file_path: Path) -> Tuple[Optional[str], str, Optional[str], str]:
    """Parses a filename to extract ZID, title, source language, and extension.
    
    Mirrors the logic in subtitle_translator.py.
    """
    name = file_path.name
    ext = file_path.suffix.lstrip('.')
    stem = file_path.stem

    # 1. Match ZID (14 digits)
    zid_match = re.match(r'^(\d{14})-(.*)$', name)
    if zid_match:
        zid = zid_match.group(1)
        remaining = zid_match.group(2)
        if remaining.endswith('.' + ext):
            remaining_stem = remaining[:-len('.' + ext)]
        else:
            remaining_stem = remaining
    else:
        zid = None
        remaining_stem = stem

    # 2. Match language code suffix (.en, .ru, etc. before the extension)
    lang_match = re.search(r'\.([a-zA-Z]{2,3}(?:-[a-zA-Z]{2,4})?)$', remaining_stem)
    if lang_match:
        lang = lang_match.group(1)
        clean_title = remaining_stem[:-len('.' + lang)]
    else:
        lang = None
        clean_title = remaining_stem

    return zid, clean_title, lang, ext

def detect_language(paths: List[Path], default_lang: str) -> str:
    """Picks the language from the first/primary sent file's postfix."""
    if not paths:
        return default_lang
    primary_file = paths[0]
    _, _, lang, _ = parse_filename(primary_file)
    if lang:
        lang_lower = lang.lower()
        if lang_lower in ('en', 'de'):
            return lang_lower
        else:
            log_warn(f"Unsupported language postfix '{lang}' detected on primary file '{primary_file.name}'. Falling back to default language '{default_lang}'.")
    return default_lang

# ==============================================================================
# SEND-ORDER SORTING
# ==============================================================================
def sort_send_order(paths: List[Path]) -> List[Path]:
    """Sorts paths using: leading 14-digit ZID, trailing numeric index, and argv order."""
    indexed_paths = list(enumerate(paths))
    
    def extract_key(item):
        index, path = item
        zid, clean_title, lang, ext = parse_filename(path)
        
        # Primary: ZID (defaults to empty string so it sorts predictably)
        primary = zid if zid else ""
        
        # Secondary: trailing numeric index in the stem
        match = re.search(r'(\d+)\D*$', clean_title)
        if match:
            secondary = int(match.group(1))
        else:
            secondary = float('inf')
            
        return (primary, secondary, index)
        
    indexed_paths.sort(key=extract_key)
    return [path for _, path in indexed_paths]

# ==============================================================================
# SRT PARSING & CLEANING
# ==============================================================================
def parse_srt(content: str) -> List[dict]:
    """Parses SRT content into structured blocks."""
    content = content.replace('\r\n', '\n').replace('\r', '\n')
    lines = content.split('\n')
    
    blocks = []
    current_block_lines = []
    
    for line in lines:
        if line.strip() == "":
            if current_block_lines:
                blocks.append(current_block_lines)
                current_block_lines = []
        else:
            current_block_lines.append(line)
    if current_block_lines:
        blocks.append(current_block_lines)
        
    parsed_blocks = []
    for block_lines in blocks:
        index = ""
        timeline = ""
        text_lines = []
        
        if len(block_lines) > 0:
            first = block_lines[0].strip()
            if first.isdigit():
                index = first
                if len(block_lines) > 1 and '-->' in block_lines[1]:
                    timeline = block_lines[1].strip()
                    text_lines = block_lines[2:]
                else:
                    text_lines = block_lines[1:]
            elif '-->' in first:
                timeline = first
                text_lines = block_lines[1:]
            else:
                text_lines = block_lines
                
        parsed_blocks.append({
            'index': index,
            'timeline': timeline,
            'text_lines': [t.strip() for t in text_lines]
        })
        
    return parsed_blocks

def clean_subtitle_text(text: str) -> str:
    """Strips HTML-like tags, ASS formatting tags, and collapses whitespace."""
    if not text:
        return ""
    # Remove HTML-like tags (e.g. <i>, <b>, <font...>, </font>, etc.)
    text = re.sub(r'<[^>]+>', '', text)
    # Remove ASS formatting tags (e.g. {\an8}, {\pos(100,100)}, etc.)
    text = re.sub(r'\{[^}]+\}', '', text)
    # Replace any literal newlines, carriage returns, or tabs with spaces
    text = text.replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
    # Normalize multiple consecutive spaces to a single space
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

# ==============================================================================
# INPUT STAGING
# ==============================================================================
def stage_inputs(sorted_paths: List[Path], sent_dir: Path) -> List[Path]:
    """Writes staged files to <sent_dir>/source_texts/textN.txt (N=1..3)."""
    source_texts_dir = sent_dir / "source_texts"
    source_texts_dir.mkdir(parents=True, exist_ok=True)
    
    staged_paths = []
    for i in range(3):
        slot_num = i + 1
        target_path = source_texts_dir / f"text{slot_num}.txt"
        
        if i < len(sorted_paths):
            src_path = sorted_paths[i]
            log_info(f"Staging slot {slot_num}: '{src_path.name}' -> '{target_path.relative_to(sent_dir)}'")
            
            try:
                content = src_path.read_text(encoding="utf-8", errors="replace")
                
                if src_path.suffix.lower() == ".srt":
                    blocks = parse_srt(content)
                    cleaned_lines = []
                    for block in blocks:
                        block_text = " ".join(block['text_lines'])
                        cleaned_text = clean_subtitle_text(block_text)
                        if cleaned_text:
                            cleaned_lines.append(cleaned_text)
                    cleaned_content = " ".join(cleaned_lines)
                else:
                    cleaned_content = content
                    
                target_path.write_text(cleaned_content, encoding="utf-8", newline="\n")
            except Exception as e:
                log_error(f"Failed to stage file '{src_path.name}': {e}")
                sys.exit(1)
        else:
            log_info(f"Staging slot {slot_num}: [empty placeholder] -> '{target_path.relative_to(sent_dir)}'")
            target_path.write_text("", encoding="utf-8", newline="\n")
            
        staged_paths.append(target_path)
    return staged_paths

# ==============================================================================
# CONSOLE PAUSING
# ==============================================================================
def pause_console(success: bool = True, timeout_secs: Optional[int] = PAUSE_AUTO_CLOSE_TIMEOUT_SECS):
    """Pauses the console window for inspection."""
    if not success or timeout_secs is None:
        try:
            input("\nPress Enter to exit...")
        except Exception:
            pass
        return

    print(f"\nPress Enter to exit (or wait {timeout_secs}s for auto-close)...", end="", flush=True)
    is_windows = sys.platform.startswith("win")
    if is_windows and _IS_TTY:
        import msvcrt
        start_time = time.time()
        last_remaining = timeout_secs
        while True:
            if msvcrt.kbhit():
                try:
                    msvcrt.getch()
                except Exception:
                    pass
                break
            
            elapsed = time.time() - start_time
            remaining = int(round(timeout_secs - elapsed))
            if remaining <= 0:
                break
                
            if remaining != last_remaining:
                sys.stdout.write(f"\rPress Enter to exit (or wait {remaining}s for auto-close)...")
                sys.stdout.flush()
                last_remaining = remaining
            
            time.sleep(0.05)
        sys.stdout.write("\r\x1b[K" + " " * 65 + "\r")
        sys.stdout.flush()
    else:
        try:
            input("\nPress Enter to exit...")
        except Exception:
            pass

# ==============================================================================
# MAIN FLOW
# ==============================================================================
def main():
    parser = argparse.ArgumentParser(description="Kardenwort SendTo Vocab Processor")
    parser.add_argument("--sendto", action="store_true", help="Enable SendTo mode")
    parser.add_argument("--pause", action="store_true", help="Pause console on exit")
    parser.add_argument("files", nargs="*", help="File paths to process")
    
    args = parser.parse_args()
    
    if args.sendto:
        print("=== Kardenwort SendTo Vocab Processor ===")
        
    # 1. Filter files to .txt and .srt
    valid_paths = []
    for f in args.files:
        p = Path(f)
        if p.suffix.lower() in ('.txt', '.srt'):
            valid_paths.append(p)
        else:
            log_warn(f"Ignoring unsupported file: '{p.name}' (only .txt and .srt are supported)")
            
    if not valid_paths:
        log_error("No valid .txt or .srt files were provided.")
        if args.pause:
            pause_console(success=False)
        sys.exit(1)
        
    # 2. Sort the files in send-order
    sorted_paths = sort_send_order(valid_paths)
    
    # 3. Warn about extra files if more than 3
    if len(sorted_paths) > 3:
        ignored_files = sorted_paths[3:]
        sorted_paths = sorted_paths[:3]
        for f in ignored_files:
            log_warn(f"Ignoring extra file: '{f.name}' (maximum 3 files can be processed in a batch)")
            
    # 4. Determine sent directory
    sent_dir = sorted_paths[0].parent.resolve()
    
    # 5. Load configuration
    project_root, config = load_config()
    
    # Resolve default language
    default_lang = config.get('sendto', 'sendto_default_language', fallback=None)
    if not default_lang:
        default_lang = config.get('environment', 'sendto_default_language', fallback='en')
    default_lang = default_lang.strip().lower()
    
    # Resolve save results with source
    save_results_with_source = config.getboolean('sendto', 'sendto_save_results_with_source', fallback=None)
    if save_results_with_source is None:
        save_results_with_source = config.getboolean('environment', 'sendto_save_results_with_source', fallback=True)
        
    # 6. Detect language
    language = detect_language(sorted_paths, default_lang)
    
    # Print resolved mapping if in SendTo mode
    if args.sendto:
        print("\nResolved File Mapping:")
        for i, p in enumerate(sorted_paths):
            print(f"  Slot {i+1}: {p.name}")
        for i in range(len(sorted_paths), 3):
            print(f"  Slot {i+1}: [Empty Placeholder]")
        print(f"Detected Language: {language.upper()}\n")
        
    # 7. Stage inputs
    staged_paths = stage_inputs(sorted_paths, sent_dir)
    
    # 8. Resolve runner path and python path
    try:
        python_path_str = config.get('environment', 'python_executable')
        workspace_path_str = config.get('environment', 'kardenwort_workspace', fallback='./')
        
        python_path = Path(python_path_str)
        workspace_path = Path(workspace_path_str)
        if not python_path.is_absolute():
            python_path = (project_root / python_path).resolve()
        if not workspace_path.is_absolute():
            workspace_path = (project_root / workspace_path).resolve()
            
        runner_filename = config.get('scripts', 'kardenwort_runner_filename', fallback='kardenwort_runner.py')
        source_code_dir = config.get('project_structure', 'source_code_dir', fallback='src/kardenwort/core')
        runner_path = (workspace_path / source_code_dir / runner_filename).resolve()
    except KeyError as e:
        log_error(f"Missing required configuration key in config.ini: {e}")
        if args.pause:
            pause_console(success=False)
        sys.exit(1)
        
    if not runner_path.exists():
        log_error(f"Runner script not found at '{runner_path}'")
        if args.pause:
            pause_console(success=False)
        sys.exit(1)
        
    # 9. Build arguments matching the v3 cmd launcher
    cmd_args = [
        str(python_path),
        str(runner_path),
        "--mode", "mixed-triple",
        "--language", language,
        "--tts-destination-lang", "ru",
        "--deduplication-scope", "global",
        "--anki-create-subdecks",
        "--anki-markdown-decks",
        "--anki-sentence-subdecks",
        "--anki-deck-content", "parent-source", "parent-translations", "subdeck-source", "subdeck-translations",
        "--suspend-cards",
        "--show-success-message",
        "--play-sound-on-completion",
        "--text1-file", str(staged_paths[0]),
        "--text2-file", str(staged_paths[1]),
        "--text3-file", str(staged_paths[2])
    ]
    
    # 10. Record results directory files before running to capture new ones
    results_dir_name = config.get('project_structure', 'generated_results_dir', fallback='results')
    results_dir = (workspace_path / results_dir_name).resolve()
    
    existing_results_files = set()
    if results_dir.exists():
        existing_results_files = {f.name for f in results_dir.iterdir() if f.is_file()}
        
    start_time = time.time()
    
    # 11. Run the runner
    log_info("Starting Kardenwort extraction runner...")
    try:
        # Run directly without capturing output so the user sees the extraction progress
        subprocess.run(cmd_args, check=True)
    except subprocess.CalledProcessError as e:
        log_error(f"Runner failed with exit code {e.returncode}")
        if args.pause:
            pause_console(success=False)
        sys.exit(1)
    except Exception as e:
        log_error(f"Failed to start runner: {e}")
        if args.pause:
            pause_console(success=False)
        sys.exit(1)
        
    log_ok("Runner finished successfully.")
    
    # 12. Capture and move new files if save_results_with_source is true
    if save_results_with_source:
        log_info("Scanning for newly generated result files...")
        target_results_dir = sent_dir / "results"
        
        # Short sleep to allow the filesystem to settle
        time.sleep(1)
        
        new_files = []
        if results_dir.exists():
            for f in results_dir.iterdir():
                if f.is_file() and f.suffix.lower() in ('.tsv', '.json'):
                    # Check if file is new or modified during/after execution
                    if f.name not in existing_results_files or f.stat().st_mtime >= (start_time - 5):
                        new_files.append(f)
                        
        if new_files:
            target_results_dir.mkdir(parents=True, exist_ok=True)
            for f in new_files:
                dest = target_results_dir / f.name
                log_info(f"Moving result: '{f.name}' -> '{dest.relative_to(sent_dir)}'")
                try:
                    if dest.exists():
                        dest.unlink()
                    shutil.move(str(f), str(dest))
                except Exception as e:
                    log_warn(f"Failed to move result file '{f.name}': {e}")
        else:
            log_warn("No newly generated result files were detected.")
            
    if args.pause:
        pause_console(success=True)

if __name__ == "__main__":
    main()
