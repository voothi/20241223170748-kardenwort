import subprocess
from pathlib import Path
import argparse
import configparser
import sys
import os
import re
import json

if sys.platform == "win32":
    import winsound

def print_debug(message):
    print(message, file=sys.stderr)

def load_config():
    config_path = Path(__file__).resolve().parent.parent.parent.parent / 'config.ini'
    if not config_path.exists():
        print_debug(f"ERROR: Configuration file not found at {config_path}")
        print_debug("Please copy 'config.ini.template' to 'config.ini' and fill it in.")
        sys.exit(1)

    project_root = config_path.parent
    
    config = configparser.ConfigParser(allow_no_value=True)
    config.optionxform = str
    config.read(config_path, encoding='utf-8')

    section = 'environment'

    if section not in config:
        print_debug(f"ERROR: Missing section [{section}] in {config_path}")
        sys.exit(1)

    try:
        python_path_str = config[section]['python_executable']
        workspace_path_str = config[section]['kardenwort_workspace']
        importer_workspace_str = config[section]['importer_workspace']

        python_path = Path(python_path_str)
        workspace_path = Path(workspace_path_str)
        importer_workspace = Path(importer_workspace_str)
        
        if not python_path.is_absolute():
            python_path = (project_root / python_path).resolve()
        if not workspace_path.is_absolute():
            workspace_path = (project_root / workspace_path).resolve()
        if not importer_workspace.is_absolute():
            importer_workspace = (project_root / importer_workspace).resolve()

    except KeyError as e:
        print_debug(f"ERROR: Missing key {e} in section [{section}] of {config_path}")
        sys.exit(1)
        
    return python_path, workspace_path, importer_workspace, config


def get_script_args(args, python_path, workspace_path, config):
    src_path = workspace_path / config.get('project_structure', 'source_code_dir', fallback='src/kardenwort/core')
    data_path = workspace_path / config.get('project_structure', 'data_dir', fallback='data')
    input_path = workspace_path / config.get('project_structure', 'source_texts_dir', fallback='source_texts')
    output_path = workspace_path / config.get('project_structure', 'generated_results_dir', fallback='results')
    
    kardenwort_script = config.get('scripts', 'kardenwort_script_filename', fallback='kardenwort.py')
    
    try:
        lemma_file = config['language_resources'][f'lemma_file_{args.language}']
        override_file = config['language_resources'][f'override_file_{args.language}']
    except KeyError as e:
        raise ValueError(f"Missing config for language '{args.language}': {e}") from e

    base_args = [
        str(python_path),
        str(src_path / kardenwort_script),
        "--type", args.type,
        "--language", args.language,
        "--deduplication-scope", args.deduplication_scope,
        "--lemma-index-file", str(data_path / lemma_file),
        "--lemma-override-file", str(data_path / override_file),
        "--basename-add-timestamp",
        "--basename-add-first-words",
        "--stdout-print-output-basename",
        "--sentence-context-size", "4",
    ]
    
    wordlist_use_br = config.getboolean('output_format', 'wordlist_use_br', fallback=False)
    if wordlist_use_br:
        base_args.append("--wordlist-use-br")
        
    add_header = config.getboolean('output_format', 'add_header', fallback=True)
    if add_header:
        base_args.append("--add-header")

    if 'anki_fields' not in config:
        sys.exit("Error: Missing '[anki_fields]' section in config.ini. Please update your configuration following config.ini.template to define your Anki structure.")
    
    # Support both numbered lists (backward compatibility) and simple ordered lists
    raw_fields_dict = dict(config.items('anki_fields'))
    
    # Check if we should use numeric sorting (old format) or list order (new format)
    # If all keys are numeric, use numeric sorting. Otherwise, use keys as field names in order.
    try:
        # Check if all keys are integers
        [int(k) for k in raw_fields_dict.keys()]
        # Numeric format detected
        sorted_keys = sorted(raw_fields_dict.keys(), key=lambda x: int(x))
        anki_header = [raw_fields_dict[k] for k in sorted_keys]
    except (ValueError, TypeError):
        # Key format detected (list of names)
        # config.items() preserves order in Python 3.7+
        anki_header = list(raw_fields_dict.keys())

    if not anki_header:
        sys.exit("Error: No fields defined in '[anki_fields]' section of config.ini.")
    base_args.extend(["--anki-csv-header", json.dumps(anki_header)])

    mapping_section = f'anki_field_mapping.{args.type}'
    if mapping_section not in config:
        sys.exit(f"Error: Missing '[{mapping_section}]' section in config.ini. Please define your data mappings.")
    
    field_mapping = dict(config[mapping_section])
    base_args.extend(["--anki-field-mapping", json.dumps(field_mapping)])

    if args.tts_destination_lang:
        base_args.extend(["--tts-destination-lang", args.tts_destination_lang])

    if args.multi_text:
        base_args.append("--multi-text")

    if args.prefer_shortest_form:
        base_args.append("--prefer-shortest-form")

    if args.anki_create_subdecks:
        base_args.append("--anki-create-subdecks")
        if args.anki_parent_deck:
            base_args.extend(["--anki-parent-deck", args.anki_parent_deck])

    if args.anki_markdown_decks:
        base_args.append("--anki-markdown-decks")
    
    if args.anki_sentence_subdecks:
        base_args.append("--anki-sentence-subdecks")
    
    if args.anki_deck_content:
        base_args.extend(["--anki-deck-content"] + args.anki_deck_content)

    if args.strip_headers is not None:
        base_args.extend(["--strip-headers"] + args.strip_headers)

    if args.language == "de":
        de_dictionary_file = config.get('language_resources', 'dictionary_file_de', fallback='german.dic')
        german_enhancement_args = [
            "--de-fix-genitive",
            "--de-dictionary-file", str(data_path / de_dictionary_file),
        ]
        base_args.extend(german_enhancement_args)
        
        if args.de_gcs:
            gcs_args = [
                "--de-gcs",
                "--de-gcs-split-mode", "combined",
                "--de-gcs-preserve-compound-word",
                "--de-gcs-add-parts-to-wordlist",
                "--de-gcs-skip-merge-fractions",
            ]
            if args.de_gcs_pos_tags:
                gcs_args.append("--de-gcs-pos-tags")
                gcs_args.extend(args.de_gcs_pos_tags)
            base_args.extend(gcs_args)

    output_suffix = "sentence" if args.type == "sentence" else "word"
    
    mode_for_filename = "triple" if args.mode == "mixed-triple" else args.mode
    
    output_template = config.get('output_format', 'output_template', fallback='result.{mode}.{suffix}.{language}.tsv')
    output_filename = output_template.format(
        mode=mode_for_filename,
        suffix=output_suffix,
        language=args.language
    )
    
    mode_args = []
    text1_filename = config.get('input_files', 'text1_file', fallback='text1.txt')
    text2_filename = config.get('input_files', 'text2_file', fallback='text2.txt')
    text3_filename = config.get('input_files', 'text3_file', fallback='text3.txt')
    
    input_text_arg = None
    if args.text:
        input_text_arg = args.text
    elif os.environ.get('KARDENWORT_INPUT_TEXT'):
        input_text_arg = os.environ.get('KARDENWORT_INPUT_TEXT')

    if input_text_arg:
        mode_args.extend(["--text", input_text_arg])
    else:
        mode_for_input_files = "triple" if args.mode == "mixed-triple" else args.mode

        # Define the paths, prioritizing command-line arguments over config defaults
        text1_path = args.text1_file if args.text1_file else str(input_path / text1_filename)
        text2_path = args.text2_file if args.text2_file else str(input_path / text2_filename)
        text3_path = args.text3_file if args.text3_file else str(input_path / text3_filename)

        if mode_for_input_files == "single":
             mode_args.extend(["--text1-file", text1_path])
        elif mode_for_input_files == "dual":
            mode_args.extend(["--text1-file", text1_path])
            mode_args.extend(["--text2-file", text2_path])
        elif mode_for_input_files == "triple":
            mode_args.extend(["--text1-file", text1_path])
            mode_args.extend(["--text2-file", text2_path])
            mode_args.extend(["--text3-file", text3_path])
        else:
            raise ValueError(f"Unknown mode: {args.mode}")

    mode_args.extend(["--output-file", str(output_path / output_filename)])
    return base_args + mode_args

def run_extraction_script(script_args):
    """Executes the kardenwort.py script and returns the output filename."""
    print_debug(f"Running extraction script with command:\n{' '.join(map(str, script_args))}\n")
    
    script_process = subprocess.Popen(
        script_args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding='utf-8',
        errors='replace'
    )
    stdout_output, stderr_output = script_process.communicate()
    
    if script_process.returncode != 0:
        print_debug(f"ERROR: The extraction script failed with exit code {script_process.returncode}.")
        if stderr_output:
            print_debug("--- Stderr from kardenwort.py ---")
            print_debug(stderr_output)
            print_debug("---------------------------------")
        return None

    output_lines = stdout_output.strip().splitlines()
    if not output_lines:
        print_debug("ERROR: No output filename was captured from the script.")
        if stderr_output:
            print_debug("--- Stderr from kardenwort.py ---")
            print_debug(stderr_output)
            print_debug("---------------------------------")
        return None
        
    return output_lines[0].strip()

def run_importer_script(output_filename_basename, args, python_path, workspace_path, importer_workspace, config):
    """Executes the anki-csv-importer.py script for a given file."""
    print_debug(f"Processing file for import: {output_filename_basename}")

    importer_script = config.get('scripts', 'importer_script_filename', fallback='anki-csv-importer.py')
    note_type = config.get('anki_importer_settings', 'note_type', fallback='Basic')
    output_dir_name = config.get('project_structure', 'generated_results_dir', fallback='results')

    importer_command = [
        str(python_path),
        str(importer_workspace / importer_script),
        "--path", str(workspace_path / output_dir_name / output_filename_basename),
        "--note", note_type,
    ]
    
    single_deck_name_for_importer = ""
    if not args.anki_markdown_decks:
        if args.anki_create_subdecks:
            sub_deck_name = os.path.splitext(output_filename_basename)[0]
            if args.anki_parent_deck:
                parent_deck_name = args.anki_parent_deck
            else:
                parent_deck_name = re.sub(r'\.(word|sentence)', '', sub_deck_name)

            if parent_deck_name != sub_deck_name:
                single_deck_name_for_importer = f"{parent_deck_name}::{sub_deck_name}"
            else:
                single_deck_name_for_importer = parent_deck_name
        else:
            single_deck_name_for_importer = os.path.splitext(output_filename_basename)[0]

    if single_deck_name_for_importer:
        importer_command.extend(["--deck", single_deck_name_for_importer])

    if args.suspend_cards:
        importer_command.append("--suspend")
    
    output_base_path = workspace_path / output_dir_name / output_filename_basename
    metadata_path = output_base_path.with_suffix('.json')
    if metadata_path.exists():
        importer_command.extend(["--deck-metadata-file", str(metadata_path)])

    print_debug(f"Running importer with command:\n{' '.join(map(str, importer_command))}\n")
    
    try:
        subprocess.run(importer_command, check=True, text=True, encoding='utf-8')
    except subprocess.CalledProcessError as e:
        print_debug(f"ERROR: Anki importer failed with exit code {e.returncode}.")
        sys.exit(1)

def main():
    if "--get-python-path" in sys.argv:
        python_path, _, _, _ = load_config()
        print(python_path)
        sys.exit(0)

    parser = argparse.ArgumentParser(
        description="A wrapper script to extract and process words or sentences from text files and import them into Anki."
    )
    parser.add_argument("--play-sound-on-completion", action="store_true", help="Play a system beep sound upon successful completion.")
    parser.add_argument("--show-success-message", action="store_true", help="Display a user-friendly success message on stdout. Useful for interactive tools like GoldenDict.")
    parser.add_argument("--type", type=str, choices=["word", "sentence"], help="Type of processing: 'word' for word extraction, 'sentence' for parallel sentences. Not required for 'mixed-triple' mode.")
    parser.add_argument("--mode", type=str, required=True, choices=["single", "dual", "triple", "mixed-triple"], help="Processing mode: single, dual, triple, or mixed-triple (runs sentence and word modes sequentially).")
    parser.add_argument("--language", type=str, required=True, choices=["de", "en"], help="Language for processing: German (de) or English (en).")
    parser.add_argument("--deduplication-scope", type=str, choices=['global', 'sentence', 'none'], default='global', help="Set the scope for lemma deduplication.")
    parser.add_argument("--tts-destination-lang", type=str, help="Specify the destination language for TTS field activation (e.g., 'ru', 'en').")
    parser.add_argument("--text", type=str, help="Directly pass a text string for 'single' mode processing, bypassing the default text1.txt file.")
    parser.add_argument("--multi-text", action="store_true", help="Enable multi-text parsing from a single text input source using '---' as a separator.")
    parser.add_argument("--prefer-shortest-form", action="store_true", help="When deduplicating globally, prefer the shortest word form of a lemma, even if it appears later in the text. Default is to keep the first occurrence.")
    parser.add_argument("--de-gcs", action='store_true', help="Enable German Compound Splitting (only effective when --language is 'de').")
    parser.add_argument("--de-gcs-pos-tags", nargs='+', help="Specify POS tags for GCS (e.g., 'NOUN PROPN' or '!VERB').")
    parser.add_argument("--anki-create-subdecks", action="store_true", help="Automatically generate a parent deck and sub-decks for Anki based on the output filename.")
    parser.add_argument("--anki-markdown-decks", action="store_true", help="Parse Markdown headers in source text to create a hierarchical deck structure in Anki.")
    parser.add_argument("--anki-sentence-subdecks", action="store_true", help="Create a final subdeck level for each sentence.")
    parser.add_argument("--anki-parent-deck", type=str, help="Specify the parent deck name, used by subsequent calls in a batch process to ensure a shared parent deck.")
    parser.add_argument("--suspend-cards", action="store_true", help="Suspend all newly imported/updated cards in Anki.")
    parser.add_argument("--anki-deck-content", nargs='+', choices=['parent-source', 'parent-translations', 'subdeck-source', 'subdeck-translations'], help="Adds content to the Anki deck description.")
    parser.add_argument("--strip-headers", nargs='*', choices=['all', 'source', 'translations'], help="Strip Markdown headers (#) from text fields in the final output. No arguments implies 'all'.")
    parser.add_argument("--text1-file", type=str, help="Path to the first source text file.")
    parser.add_argument("--text2-file", type=str, help="Path to the second source text file (for dual/triple modes).")
    parser.add_argument("--text3-file", type=str, help="Path to the third source text file (for triple mode).")

    args = parser.parse_args()
    
    if args.mode != 'mixed-triple' and not args.type:
        parser.error('--type is required for modes single, dual, and triple.')
    if args.mode == 'mixed-triple' and args.type:
        print_debug("Warning: --type is ignored when --mode is mixed-triple.")

    if args.mode == 'mixed-triple' and args.text and not args.multi_text:
        print_debug("Info: Automatically enabling --multi-text for mixed-triple mode with --text input.")
        args.multi_text = True

    python_path, workspace_path, importer_workspace, config = load_config()

    if args.mode == "mixed-triple":
        print_debug("--- Running mixed-triple mode: SENTENCE pass ---")
        args.type = "sentence"
        sentence_script_args = get_script_args(args, python_path, workspace_path, config)
        
        sentence_filename_basename = run_extraction_script(sentence_script_args)
        if not sentence_filename_basename:
            sys.exit(1)

        temp_deck_name = os.path.splitext(sentence_filename_basename)[0]
        parent_deck_name = temp_deck_name.replace('.sentence', '')
        print_debug(f"Parent Deck Name for this session is: {parent_deck_name}")
        args.anki_parent_deck = parent_deck_name

        print_debug("\n--- Running mixed-triple mode: WORD pass ---")
        args.type = "word"
        original_deck_content = args.anki_deck_content
        args.anki_deck_content = None 
        word_script_args = get_script_args(args, python_path, workspace_path, config)
        
        word_filename_basename = run_extraction_script(word_script_args)
        if not word_filename_basename:
            sys.exit(1)

        args.anki_deck_content = original_deck_content
        args.anki_parent_deck = None 
        print_debug(f"\n--- Importing SENTENCE file: {sentence_filename_basename} ---")
        run_importer_script(sentence_filename_basename, args, python_path, workspace_path, importer_workspace, config)

        args.anki_parent_deck = parent_deck_name
        print_debug(f"\n--- Importing WORD file: {word_filename_basename} ---")
        run_importer_script(word_filename_basename, args, python_path, workspace_path, importer_workspace, config)

        print_debug("\nAll operations for mixed-triple mode completed successfully.")
        
        if args.show_success_message:
            success_message = f"Completed successfully!\n\nCards have been imported into the deck:\n{parent_deck_name}"
            print(success_message)

    else: # Logic for single, dual, triple modes
        script_args = get_script_args(args, python_path, workspace_path, config)
        output_filename_basename = run_extraction_script(script_args)
        
        if not output_filename_basename:
            sys.exit(1)
        
        run_importer_script(output_filename_basename, args, python_path, workspace_path, importer_workspace, config)
        
        print(output_filename_basename)

    if args.play_sound_on_completion:
        try:
            if sys.platform == "win32":
                winsound.MessageBeep(winsound.MB_OK)
            else:
                print('\a', file=sys.stderr, flush=True)
        except Exception as e:
            print_debug(f"Warning: Could not play completion sound. Error: {e}")


if __name__ == "__main__":
    main()