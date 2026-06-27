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
PAUSE_ON_ERROR = False

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
# ERROR & CONFIG HELPERS
# ==============================================================================
def _fail(msg: str, pause: bool = False):
    """Logs error, optionally pauses, and exits with code 1."""
    log_error(msg)
    if pause or PAUSE_ON_ERROR:
        pause_console(success=False)
    sys.exit(1)

def _sendto_config_get(cfg: configparser.ConfigParser, key: str, getter_name: str, fallback):
    """Resolves config key with fallback from [sendto] to [environment]."""
    for section in ("sendto", "environment"):
        if section in cfg and key in cfg[section]:
            getter = getattr(cfg, getter_name)
            return getter(section, key)
    return fallback

# ==============================================================================
# CONFIGURATION LOADING
# ==============================================================================
def load_config() -> Tuple[Path, configparser.ConfigParser]:
    """Loads configuration settings from the project's config.ini."""
    config_path = Path(__file__).resolve().parent.parent / "config.ini"
    if not config_path.exists():
        _fail(f"Configuration file not found at {config_path}")
        
    config = configparser.ConfigParser(allow_no_value=True)
    config.optionxform = str
    config.read(config_path, encoding="utf-8")
    return config_path.parent, config

# ==============================================================================
# FILENAME PARSING
# ==============================================================================
def parse_filename(file_path: Path) -> Tuple[Optional[str], str, Optional[str]]:
    """Parses a filename to extract ZID, title, and source language.
    
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

    return zid, clean_title, lang

def detect_language(paths: List[Path], default_lang: str) -> str:
    """Picks the language from the first/primary sent file's postfix."""
    if not paths:
        return default_lang
    primary_file = paths[0]
    _, _, lang = parse_filename(primary_file)
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
        zid, clean_title, lang = parse_filename(path)
        
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
def parse_srt(content: str) -> List[List[str]]:
    """Parses SRT content to extract only subtitle text lines."""
    content = content.replace('\r\n', '\n').replace('\r', '\n')
    
    blocks = []
    current_block_lines = []
    for line in content.split('\n'):
        if line.strip() == "":
            if current_block_lines:
                blocks.append(current_block_lines)
                current_block_lines = []
        else:
            current_block_lines.append(line.strip())
    if current_block_lines:
        blocks.append(current_block_lines)
        
    parsed_blocks = []
    for block_lines in blocks:
        if not block_lines:
            continue
        # Skip index if it's a digit
        start_idx = 0
        if block_lines[0].isdigit():
            start_idx = 1
        # Skip timeline if it contains '-->'
        if start_idx < len(block_lines) and '-->' in block_lines[start_idx]:
            start_idx += 1
        
        text_lines = block_lines[start_idx:]
        if text_lines:
            parsed_blocks.append(text_lines)
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
# ==============================================================================
# SLOT MAPPING RESOLUTION
# ==============================================================================
def resolve_slots(sorted_paths: List[Path], lang_slots: dict, default_lang: str, batch_lang: str) -> dict:
    """Assigns each path in sorted_paths to slot 1, 2, or 3 based on numeric index/language rules."""
    slots = {1: None, 2: None, 3: None}
    unassigned = []
    
    for path in sorted_paths:
        zid, clean_title, lang = parse_filename(path)
        
        # Rule 1: Filename numeric index (1, 2, or 3)
        match = re.search(r'(\d+)\D*$', clean_title)
        assigned_slot = None
        if match:
            num = int(match.group(1))
            if num in (1, 2, 3):
                assigned_slot = num
                
        # Rule 2: If the file language matches the batch source language, it goes to slot 1
        if not assigned_slot:
            resolved_lang = (lang if lang else default_lang).lower()
            if resolved_lang == batch_lang.lower():
                assigned_slot = 1
                
        # Rule 3: Language mapping
        if not assigned_slot:
            resolved_lang = (lang if lang else default_lang).lower()
            if resolved_lang in lang_slots:
                assigned_slot = lang_slots[resolved_lang]
                
        if assigned_slot:
            if slots[assigned_slot] is None:
                slots[assigned_slot] = path
            else:
                unassigned.append(path)
        else:
            unassigned.append(path)
            
    # Second pass: fill empty slots
    for slot_num in (1, 2, 3):
        if slots[slot_num] is None and unassigned:
            slots[slot_num] = unassigned.pop(0)
            
    return slots

# ==============================================================================
# INPUT STAGING
# ==============================================================================
def stage_inputs(slots: dict, sent_dir: Path) -> List[Path]:
    """Writes staged files to <sent_dir>/source_texts/textN.txt (N=1..3)."""
    source_texts_dir = sent_dir / "source_texts"
    source_texts_dir.mkdir(parents=True, exist_ok=True)
    
    staged_paths = []
    for slot_num in (1, 2, 3):
        target_path = source_texts_dir / f"text{slot_num}.txt"
        src_path = slots[slot_num]
        
        if src_path:
            log_info(f"Staging slot {slot_num}: '{src_path.name}' -> '{target_path.relative_to(sent_dir)}'")
            try:
                content = src_path.read_text(encoding="utf-8", errors="replace")
                
                if src_path.suffix.lower() == ".srt":
                    blocks = parse_srt(content)
                    cleaned_lines = []
                    for block_text_lines in blocks:
                        for line in block_text_lines:
                            cleaned_text = clean_subtitle_text(line)
                            if cleaned_text:
                                cleaned_lines.append(cleaned_text)
                    cleaned_content = "\n".join(cleaned_lines)
                else:
                    cleaned_content = content
                    
                with open(target_path, "w", encoding="utf-8", newline="\n") as f_out:
                    f_out.write(cleaned_content)
            except Exception as e:
                _fail(f"Failed to stage file '{src_path.name}': {e}")
        else:
            log_info(f"Staging slot {slot_num}: [empty placeholder] -> '{target_path.relative_to(sent_dir)}'")
            with open(target_path, "w", encoding="utf-8", newline="\n") as f_out:
                f_out.write("")
            
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
    sendto_mode = False
    pause_mode = False
    files = []
    
    for arg in sys.argv[1:]:
        if arg == "--sendto":
            sendto_mode = True
        elif arg == "--pause":
            pause_mode = True
        else:
            files.append(arg)
            
    global PAUSE_ON_ERROR
    PAUSE_ON_ERROR = pause_mode
            
    if sendto_mode:
        print("=== Kardenwort SendTo Vocab Processor ===")
        
    # 1. Filter files to .txt and .srt
    valid_paths = []
    for f in files:
        p = Path(f)
        if p.suffix.lower() in ('.txt', '.srt'):
            valid_paths.append(p)
        else:
            log_warn(f"Ignoring unsupported file: '{p.name}' (only .txt and .srt are supported)")
            
    if not valid_paths:
        _fail("No valid .txt or .srt files were provided.", pause_mode)
        
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
    default_lang = _sendto_config_get(config, 'sendto_default_language', 'get', 'en').strip().lower()
    
    # Resolve language slots mapping (default: en:1, de:2, ru:3)
    lang_slots_str = _sendto_config_get(config, 'sendto_language_slots', 'get', 'en:1, de:2, ru:3')
    lang_slots = {}
    for item in lang_slots_str.split(','):
        if ':' in item:
            k, v = item.split(':', 1)
            k = k.strip().lower()
            try:
                val = int(v.strip())
                if val in (1, 2, 3):
                    lang_slots[k] = val
            except ValueError:
                pass
    
    # Resolve save results with source
    save_results_with_source = _sendto_config_get(config, 'sendto_save_results_with_source', 'getboolean', True)
        
    # 6. Detect language from original argv order (before sorting)
    language = detect_language(valid_paths, default_lang)
    
    # Resolve slot mapping
    resolved_slots = resolve_slots(sorted_paths, lang_slots, default_lang, language)
    
    # Print resolved mapping if in SendTo mode
    if sendto_mode:
        print("\nResolved File Mapping:")
        for slot_num in (1, 2, 3):
            p = resolved_slots[slot_num]
            name = p.name if p else "[Empty Placeholder]"
            print(f"  Slot {slot_num}: {name}")
        print(f"Detected Language: {language.upper()}\n")
        
    # 7. Stage inputs
    staged_paths = stage_inputs(resolved_slots, sent_dir)
    
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
        _fail(f"Missing required configuration key in config.ini: {e}", pause_mode)
        
    if not runner_path.exists():
        _fail(f"Runner script not found at '{runner_path}'", pause_mode)
        
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
    
    # 10. Record results directory snapshot immediately before running (gated by save_results_with_source)
    existing_results_files = set()
    results_dir = None
    if save_results_with_source:
        results_dir_name = config.get('project_structure', 'generated_results_dir', fallback='results')
        results_dir = (workspace_path / results_dir_name).resolve()
        if results_dir.exists():
            existing_results_files = {f.name for f in results_dir.iterdir() if f.is_file()}
        
    # 11. Run the runner
    log_info("Starting Kardenwort extraction runner...")
    try:
        subprocess.run(cmd_args, check=True)
    except subprocess.CalledProcessError as e:
        _fail(f"Runner failed with exit code {e.returncode}", pause_mode)
    except Exception as e:
        _fail(f"Failed to start runner: {e}", pause_mode)
        
    log_ok("Runner finished successfully.")
    
    # 12. Relocate new results if save_results_with_source is true
    if save_results_with_source and results_dir and results_dir.exists():
        log_info("Scanning for newly generated result files...")
        target_results_dir = sent_dir / "results"
        
        # Compute set-difference to find newly created TSV/JSON files matching the output pattern
        new_files = []
        pattern = rf"\.triple\.(sentence|word)\.{language}\.(tsv|json)$"
        for f in results_dir.iterdir():
            if f.is_file() and re.search(pattern, f.name, re.IGNORECASE):
                if f.name not in existing_results_files:
                    new_files.append(f)
                    
        if new_files:
            target_results_dir.mkdir(parents=True, exist_ok=True)
            moved_files = []
            failed_files = []
            
            try:
                for f in new_files:
                    dest = target_results_dir / f.name
                    log_info(f"Moving result atomically: '{f.name}' -> '{dest.relative_to(sent_dir)}'")
                    
                    # Atomic move: move to a *.tmp sibling, then replace
                    tmp_dest = dest.with_suffix(dest.suffix + ".tmp")
                    
                    try:
                        shutil.move(str(f), str(tmp_dest))
                        os.replace(str(tmp_dest), str(dest))
                        moved_files.append((dest, f))
                    except Exception as file_err:
                        failed_files.append((f, file_err))
                        raise file_err
            except Exception as e:
                # Rollback successfully moved files to keep project results/ untouched
                log_error("Relocation failed. Rolling back successfully moved files...")
                for moved_dest, original_src in moved_files:
                    try:
                        if moved_dest.exists():
                            shutil.move(str(moved_dest), str(original_src))
                    except Exception as rollback_err:
                        log_error(f"Rollback failed for '{moved_dest.name}': {rollback_err}")
                
                # Log the manifest of moved/failed/untouched files
                log_error("\nRelocation Manifest (Failure):")
                log_error("Successfully moved (and rolled back):")
                for _, orig in moved_files:
                    log_error(f"  [ROLLBACK] {orig.name}")
                log_error("Failed to move:")
                for orig, err in failed_files:
                    log_error(f"  [FAILED] {orig.name}: {err}")
                log_error("Remaining files (untouched):")
                untouched_files = [
                    f for f in new_files 
                    if f not in [x[1] for x in moved_files] and f not in [y[0] for y in failed_files]
                ]
                for f in untouched_files:
                    log_error(f"  [UNTOUCHED] {f.name}")
                
                _fail(f"Relocation failed: {e}", pause_mode)
        else:
            log_warn("No newly generated result files were detected.")
            
    if pause_mode:
        pause_console(success=True)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        log_error(f"Unhandled exception occurred:\n{traceback.format_exc()}")
        if "--pause" in sys.argv:
            pause_console(success=False)
        sys.exit(1)
