import subprocess
from pathlib import Path
import argparse
import configparser
import sys
import os
import re
import json

# Temporarily add current dir to sys.path so we can import errors
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from errors import setup_structured_logging, ErrorCode, StructuredError
setup_structured_logging()
sys.path.pop(0)

class ConfigurationError(Exception):
    """Exception raised for errors in the configuration."""
    pass

if sys.platform == "win32":
    import winsound

def print_debug(message):
    print(message, file=sys.stderr)

def load_config():
    config_path = Path(__file__).resolve().parent.parent.parent.parent / 'config.ini'
    if not config_path.exists():
        print_debug(f"ERROR: Configuration file not found at {config_path}")
        print_debug("Please copy 'config.ini.template' to 'config.ini' and fill it in.")
        raise ConfigurationError(f"Configuration file not found at {config_path}")

    project_root = config_path.parent
    
    config = configparser.ConfigParser(allow_no_value=True)
    config.optionxform = str
    config.read(config_path, encoding='utf-8')

    section = 'environment'

    if section not in config:
        print_debug(f"ERROR: Missing section [{section}] in {config_path}")
        raise ConfigurationError(f"Missing section [{section}] in {config_path}")

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
        raise ConfigurationError(f"Missing key {e} in section [{section}] of {config_path}")
        
    return python_path, workspace_path, importer_workspace, config


def load_anki_mapping():
    mapping_path = Path(__file__).resolve().parent.parent.parent.parent / 'anki-mapping.ini'
    if not mapping_path.exists():
        print_debug(f"ERROR: Anki mapping file not found at {mapping_path}")
        print_debug("Please copy 'anki-mapping.ini.template' to 'anki-mapping.ini' and fill it in.")
        raise ConfigurationError(f"Anki mapping file not found at {mapping_path}")
        
    mapping = configparser.ConfigParser(allow_no_value=True)
    mapping.optionxform = str
    mapping.read(mapping_path, encoding='utf-8')
    return mapping


def get_script_args(args, python_path, workspace_path, config, anki_mapping):
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
        
    anki_context_use_br = config.getboolean('output_format', 'anki_context_use_br', fallback=False)
    if anki_context_use_br:
        base_args.append("--anki-context-use-br")
        
    add_header = config.getboolean('output_format', 'add_header', fallback=True)
    if add_header:
        base_args.append("--add-header")

    if 'anki_fields' not in anki_mapping:
        raise ConfigurationError("Missing '[anki_fields]' section in anki-mapping.ini. Please update your configuration following anki-mapping.ini.template to define your Anki structure.")
    
    # Support both numbered lists (backward compatibility) and simple ordered lists
    raw_fields_dict = dict(anki_mapping.items('anki_fields'))
    
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
        raise ConfigurationError("No fields defined in '[anki_fields]' section of anki-mapping.ini.")
    base_args.extend(["--anki-csv-header", json.dumps(anki_header)])

    mapping_section = f'anki_field_mapping.{args.type}'
    if mapping_section not in anki_mapping:
        raise ConfigurationError(f"Missing '[{mapping_section}]' section in anki-mapping.ini. Please define your data mappings.")
    
    field_mapping = dict(anki_mapping[mapping_section])
    base_args.extend(["--anki-field-mapping", json.dumps(field_mapping)])

    if args.tts_destination_lang:
        base_args.extend(["--tts-destination-lang", args.tts_destination_lang])

    if args.multi_text:
        base_args.append("--multi-text")

    if getattr(args, 'disable_dictionary_validation', False):
        base_args.append("--disable-dictionary-validation")

    if getattr(args, 'structured_output', False):
        base_args.append("--structured-output")
    elif getattr(args, 'json_ipc', False):
        base_args.append("--json-ipc")

    if getattr(args, 'simplemma_after_spacy', False):
        base_args.append("--simplemma-after-spacy")

    if getattr(args, 'simplemma_pos_aware', False):
        base_args.append("--simplemma-pos-aware")

    if getattr(args, 'simplemma_smart_fallback', False):
        base_args.append("--simplemma-smart-fallback")

    if args.prefer_shortest_form:
        base_args.append("--prefer-shortest-form")

    preserve_composite = getattr(args, 'preserve_composite_tokens', False)
    if not preserve_composite and config:
        if config.has_section('lemmatization') and config.has_option('lemmatization', 'preserve_composite_tokens'):
            preserve_composite = config.getboolean('lemmatization', 'preserve_composite_tokens', fallback=False)
        elif config.has_section('settings') and config.has_option('settings', 'preserve_composite_tokens'):
            preserve_composite = config.getboolean('settings', 'preserve_composite_tokens', fallback=False)

    if preserve_composite:
        base_args.append("--preserve-composite-tokens")

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
            gcs_args = ["--de-gcs"]
            if getattr(args, 'de_gcs_split_mode', None):
                gcs_args.extend(["--de-gcs-split-mode", args.de_gcs_split_mode])
            if getattr(args, 'de_gcs_part_singularization', None):
                gcs_args.extend(["--de-gcs-part-singularization", args.de_gcs_part_singularization])
            if getattr(args, 'de_gcs_preserve_compound_word', False):
                gcs_args.append("--de-gcs-preserve-compound-word")
            if getattr(args, 'de_gcs_add_parts_to_wordlist', False):
                gcs_args.append("--de-gcs-add-parts-to-wordlist")
            if getattr(args, 'de_gcs_skip_merge_fractions', False):
                gcs_args.append("--de-gcs-skip-merge-fractions")
            if getattr(args, 'de_gcs_mask_unknown_parts', False):
                gcs_args.append("--de-gcs-mask-unknown-parts")
            if getattr(args, 'de_gcs_pos_tags', None):
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

        # Resolve sibling subtitle timestamps sidecar file if it exists
        candidate_ts = Path(text1_path).parent / (Path(text1_path).stem + ".timestamps.txt")
        if candidate_ts.exists() and not getattr(args, 'subtitle_timestamps_file', None):
            args.subtitle_timestamps_file = str(candidate_ts.resolve())

    if getattr(args, 'subtitle_timestamps_file', None):
        mode_args.extend(["--subtitle-timestamps-file", args.subtitle_timestamps_file])

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

    tsv_path = Path(output_filename_basename)
    if not tsv_path.is_absolute():
        tsv_path = workspace_path / output_dir_name / output_filename_basename

    importer_command = [
        str(python_path),
        str(importer_workspace / importer_script),
        "--path", str(tsv_path),
        "--note", note_type,
    ]
    
    single_deck_name_for_importer = ""
    if not args.anki_markdown_decks:
        if args.anki_create_subdecks:
            basename = os.path.basename(output_filename_basename)
            sub_deck_name = os.path.splitext(basename)[0]
            if args.anki_parent_deck:
                parent_deck_name = args.anki_parent_deck
            else:
                parent_deck_name = re.sub(r'\.(word|sentence)', '', sub_deck_name)

            if parent_deck_name != sub_deck_name:
                single_deck_name_for_importer = f"{parent_deck_name}::{sub_deck_name}"
            else:
                single_deck_name_for_importer = parent_deck_name
        else:
            basename = os.path.basename(output_filename_basename)
            single_deck_name_for_importer = os.path.splitext(basename)[0]

    if single_deck_name_for_importer:
        importer_command.extend(["--deck", single_deck_name_for_importer])

    if args.suspend_cards:
        importer_command.append("--suspend")
    
    output_base_path = Path(output_filename_basename)
    if not output_base_path.is_absolute():
        output_base_path = workspace_path / output_dir_name / output_filename_basename

    zid = getattr(args, 'zid', None)
    if not zid and output_filename_basename:
        m = re.search(r'(\d{14})', os.path.basename(str(output_filename_basename)))
        if m:
            zid = m.group(1)

    trace_id = getattr(args, 'trace_id', None)
    if not trace_id and zid:
        trace_id = f"{zid}:export:anki"

    if zid:
        importer_command.extend(["--zid", str(zid)])
    if trace_id:
        importer_command.extend(["--trace-id", str(trace_id)])

    metadata_path = output_base_path.with_suffix('.json')
    if metadata_path.exists():
        importer_command.extend(["--deck-metadata-file", str(metadata_path)])
    else:
        print_debug(f"Warning: Sibling metadata JSON file not found at {metadata_path}. Proceeding with importer defaults.")

    print_debug(f"Running importer with command:\n{' '.join(map(str, importer_command))}\n")
    
    try:
        subprocess.run(importer_command, check=True, text=True, encoding='utf-8')
    except subprocess.CalledProcessError as e:
        print_debug(f"ERROR: Anki importer failed with exit code {e.returncode}.")
        sys.exit(1)

def run_fill_stage(tsv_filename_basename, args, python_path, workspace_path, config):
    """Runs headless IntelliFiller to enrich the generated TSV."""
    print_debug(f"Processing file for AI enrichment (fill): {tsv_filename_basename}")
    
    intellifiller_workspace_str = config.get('environment', 'intellifiller_workspace', fallback='../20251206123938-intellifiller-ai-addon-for-anki')
    intellifiller_workspace = Path(intellifiller_workspace_str)
    if not intellifiller_workspace.is_absolute():
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        intellifiller_workspace = (project_root / intellifiller_workspace).resolve()
        
    headless_script = intellifiller_workspace / "IntelliFiller" / "headless_entrypoint.py"
    if not headless_script.exists():
        print_debug(f"Warning: IntelliFiller headless script not found at {headless_script}. Skipping fill stage.")
        return
        
    prompt_name = "English Vocabulary Analysis and Translation (JSON)"
    if args.language == "de":
        prompt_name = "German Vocabulary Analysis and Translation (JSON)"
        
    tsv_path = Path(tsv_filename_basename)
    if not tsv_path.is_absolute():
        tsv_path = workspace_path / config.get('project_structure', 'generated_results_dir', fallback='results') / tsv_filename_basename
        
    fill_command = [
        str(python_path),
        str(headless_script),
        "--tsv", str(tsv_path),
        "--prompt", prompt_name,
    ]
    
    print_debug(f"Running fill stage with command:\n{' '.join(map(str, fill_command))}\n")
    try:
        subprocess.run(fill_command, check=True, text=True, encoding='utf-8')
    except subprocess.CalledProcessError as e:
        print_debug(f"ERROR: IntelliFiller headless fill failed with exit code {e.returncode}.")
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
    parser.add_argument("--use-simplemma-correction", action="store_true", help="Apply simplemma as an unconditional override after SpaCy processing.")
    parser.add_argument("--simplemma-after-spacy", action="store_true", help="Sequential post-processing mode where Simplemma evaluates SpaCy derived lemma.")
    parser.add_argument("--simplemma-pos-aware", action="store_true", help="Lower-case input string passed to Simplemma at sentence start if not a noun or proper noun.")
    parser.add_argument("--simplemma-smart-fallback", action="store_true", help="Evaluate Simplemma solely when SpaCy returns an unreduced inflected verb or an unverified dictionary lemma.")
    parser.add_argument("--show-success-message", action="store_true", help="Display a user-friendly success message on stdout. Useful for interactive tools like GoldenDict.")
    parser.add_argument("--type", type=str, choices=["word", "sentence"], help="Type of processing: 'word' for word extraction, 'sentence' for parallel sentences. Not required for 'mixed-triple' mode.")
    parser.add_argument("--mode", type=str, choices=["single", "dual", "triple", "mixed-triple"], help="Processing mode: single, dual, triple, or mixed-triple (runs sentence and word modes sequentially).")
    parser.add_argument("--language", type=str, choices=["de", "en"], help="Language for processing: German (de) or English (en).")
    parser.add_argument("--deduplication-scope", type=str, choices=['global', 'sentence', 'none'], default='global', help="Set the scope for lemma deduplication.")
    parser.add_argument("--tts-destination-lang", type=str, help="Specify the destination language for TTS field activation (e.g., 'ru', 'en').")
    parser.add_argument("--text", type=str, help="Directly pass a text string for 'single' mode processing, bypassing the default text1.txt file.")
    parser.add_argument("--multi-text", action="store_true", help="Enable multi-text parsing from a single text input source using '---' as a separator.")
    parser.add_argument("--prefer-shortest-form", action="store_true", help="When deduplicating globally, prefer the shortest word form of a lemma, even if it appears later in the text. Default is to keep the first occurrence.")
    parser.add_argument("--preserve-composite-tokens", action="store_true", help="Keep the whole composite token / hyphenated compound lemma in addition to decomposed sub-lemmas.")
    parser.add_argument("--de-gcs", action='store_true', help="Enable German Compound Splitting (only effective when --language is 'de').")
    parser.add_argument("--de-gcs-pos-tags", nargs='+', help="Specify POS tags for GCS (e.g., 'NOUN PROPN' or '!VERB').")
    parser.add_argument("--de-gcs-split-mode", type=str, choices=["only-nouns", "any", "combined"], help="Specify the rule set for GCS dissection.")
    parser.add_argument("--de-gcs-part-singularization", type=str, choices=["only-nouns", "all", "none"], help="Control whether parts are converted to singular form.")
    parser.add_argument("--de-gcs-preserve-compound-word", action="store_true", help="Keep the original compound word in the lemma list along with its parts.")
    parser.add_argument("--de-gcs-mask-unknown-parts", action="store_true", help="Mask unknown intermediate segments when dissecting compounds.")
    parser.add_argument("--de-gcs-add-parts-to-wordlist", action="store_true", help="Add split compound parts to the sentence wordlist.")
    parser.add_argument("--de-gcs-skip-merge-fractions", action="store_true", help="Disable merging of components, outputting raw parts from dissection.")
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
    parser.add_argument("--skip-import", action="store_true", help="Skip importing TSV files to Anki.")
    parser.add_argument("--skip-fill", action="store_true", help="Skip the IntelliFiller fill stage.")
    parser.add_argument("--fill", action="store_true", help="Explicitly run the IntelliFiller fill stage.")
    parser.add_argument("--stages", type=str, help="Override pipeline stages (comma-separated, e.g., 'extract,import').")
    parser.add_argument("--subtitle-timestamps-file", type=str, help="Path to the sidecar subtitle timestamps file.")
    parser.add_argument("--import-only", action="store_true", help="Import an existing TSV directly into Anki without running extraction.")
    parser.add_argument("--tsv", nargs="+", help="Path to the TSV file(s) (required for --import-only).")
    parser.add_argument("--structured-output", "--json-ipc", action="store_true", dest="structured_output", help="Emit JSON/JSONL output instead of plain text, enabling structured IPC communication.")
    parser.add_argument("--zid", type=str, help="Session ZID for correlation")
    parser.add_argument("--trace-id", type=str, help="Trace correlation ID")
    parser.add_argument("--serve", action="store_true", help="Start the persistent SpaCy HTTP microservice daemon.")
    parser.add_argument("--port", type=int, default=8081, help="Port to bind the HTTP microservice daemon (default: 8081).")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host interface to bind the HTTP microservice daemon (default: 127.0.0.1).")

    args = parser.parse_args()
    
    if getattr(args, 'serve', False) is True:
        from kardenwort.server.spacy_server import start_spacy_server
        start_spacy_server(host=getattr(args, 'host', '127.0.0.1'), port=getattr(args, 'port', 8081))
        sys.exit(0)
    
    python_path, workspace_path, importer_workspace, config = load_config()
    anki_mapping = load_anki_mapping()

    if args.import_only:
        if not args.tsv:
            parser.error('--tsv is required when running in --import-only mode.')
        
        # Support both a single string (from older APIs/tests) and a list of paths
        raw_tsv_list = args.tsv if isinstance(args.tsv, list) else [args.tsv]
        
        # Expand any folders in the input list
        expanded_files = []
        for f in raw_tsv_list:
            if f:
                path = Path(f).resolve()
                if path.is_dir():
                    expanded_files.extend(list(path.glob("*.tsv")))
                else:
                    expanded_files.append(path)
                    
        def extract_runner_zid(path):
            match = re.search(r'^(\d{14})', path.name)
            return match.group(1) if match else ""

        def map_to_tsv(path):
            if path.suffix.lower() == '.tsv':
                return path
            zid = extract_runner_zid(path)
            if zid:
                parent = path.parent
                matches = []
                for pattern in (f"{zid}-*.tsv", f"{zid}.*.tsv", f"{zid}.tsv"):
                    for m in parent.glob(pattern):
                        m_res = m.resolve()
                        if m_res not in matches:
                            matches.append(m_res)
                if matches:
                    return matches[0]
            return None

        tsv_files = []
        for f in expanded_files:
            tsv_path = map_to_tsv(f)
            if tsv_path and tsv_path not in tsv_files:
                tsv_files.append(tsv_path)
            
        if len(tsv_files) == 2 and tsv_files[0].parent == tsv_files[1].parent:
            parent_dir = tsv_files[0].parent
            all_tsvs = sorted(list(parent_dir.glob("*.tsv")), key=extract_runner_zid)
            
            tsv_files.sort(key=extract_runner_zid)
            start_zid = extract_runner_zid(tsv_files[0])
            end_zid = extract_runner_zid(tsv_files[1])
            
            if start_zid and end_zid:
                range_files = []
                for f in all_tsvs:
                    f_zid = extract_runner_zid(f)
                    if f_zid and start_zid <= f_zid <= end_zid:
                        range_files.append(f)
                if range_files:
                    tsv_files = range_files

        if not tsv_files:
            print_debug("ERROR: No TSV files found in the selection to import.")
            sys.exit(1)
            
        tsv_files.sort(key=extract_runner_zid)

        for tsv_path in tsv_files:
            if not tsv_path.exists():
                print_debug(f"ERROR: TSV file not found at {tsv_path}")
                sys.exit(1)
            run_importer_script(str(tsv_path), args, python_path, workspace_path, importer_workspace, config)
        sys.exit(0)

    # Standard run validation
    if not args.mode:
        parser.error('the following arguments are required: --mode')
    if not args.language:
        parser.error('the following arguments are required: --language')

    if args.mode != 'mixed-triple' and not args.type:
        parser.error('--type is required for modes single, dual, and triple.')
    if args.mode == 'mixed-triple' and args.type:
        print_debug("Warning: --type is ignored when --mode is mixed-triple.")

    if args.mode == 'mixed-triple' and args.text and not args.multi_text:
        print_debug("Info: Automatically enabling --multi-text for mixed-triple mode with --text input.")
        args.multi_text = True


    # Load and validate pipeline stages
    if getattr(args, 'stages', None) and isinstance(args.stages, str):
        pipeline_stages_str = args.stages
    else:
        pipeline_stages_str = config.get('pipeline', 'stages', fallback='extract, import')
    if os.environ.get('KARDENWORT_TESTING') == 'true':
        pipeline_stages_str = 'extract'
    stages = [s.strip().lower() for s in pipeline_stages_str.split(',') if s.strip()]
    
    # By default, do not run the fill stage unless explicitly requested via --fill or --stages
    if 'fill' in stages:
        has_explicit_fill = (getattr(args, 'fill', False) is True) or (getattr(args, 'stages', None) and isinstance(args.stages, str) and 'fill' in args.stages.lower())
        if not has_explicit_fill:
            stages.remove('fill')
            
    if getattr(args, 'skip_fill', False) is True and 'fill' in stages:
        stages.remove('fill')
    if getattr(args, 'skip_import', False) is True and 'import' in stages:
        stages.remove('import')
    
    valid_stages = {'extract', 'fill', 'import'}
    unknown = set(stages) - valid_stages
    if unknown:
        print_debug(f"ERROR: Unknown pipeline stage(s): {', '.join(unknown)}")
        sys.exit(1)
        
    idx_extract = stages.index('extract') if 'extract' in stages else -1
    idx_fill = stages.index('fill') if 'fill' in stages else -1
    idx_import = stages.index('import') if 'import' in stages else -1
    
    if 'fill' in stages and 'extract' not in stages:
        print_debug("ERROR: Pipeline configuration error: 'fill' stage requires 'extract' stage.")
        sys.exit(1)
    if 'import' in stages and 'extract' not in stages:
        print_debug("ERROR: Pipeline configuration error: 'import' stage requires 'extract' stage.")
        sys.exit(1)
    if 'extract' in stages and 'fill' in stages and idx_fill < idx_extract:
        print_debug("ERROR: Out-of-order pipeline: 'extract' must precede 'fill'.")
        sys.exit(1)
    if 'fill' in stages and 'import' in stages and idx_import < idx_fill:
        print_debug("ERROR: Out-of-order pipeline: 'fill' must precede 'import'.")
        sys.exit(1)
    if 'extract' in stages and 'import' in stages and idx_import < idx_extract:
        print_debug("ERROR: Out-of-order pipeline: 'extract' must precede 'import'.")
        sys.exit(1)

    if args.mode == "mixed-triple":
        sentence_filename_basename = None
        if 'extract' in stages:
            print_debug("--- Running mixed-triple mode: SENTENCE pass ---")
            args.type = "sentence"
            sentence_script_args = get_script_args(args, python_path, workspace_path, config, anki_mapping)
            sentence_filename_basename = run_extraction_script(sentence_script_args)
            if not sentence_filename_basename:
                sys.exit(1)

            temp_deck_name = os.path.splitext(sentence_filename_basename)[0]
            parent_deck_name = temp_deck_name.replace('.sentence', '')
            print_debug(f"Parent Deck Name for this session is: {parent_deck_name}")
            args.anki_parent_deck = parent_deck_name
        else:
            parent_deck_name = args.anki_parent_deck or "DefaultParentDeck"

        word_filename_basename = None
        if 'extract' in stages:
            print_debug("\n--- Running mixed-triple mode: WORD pass ---")
            args.type = "word"
            original_deck_content = args.anki_deck_content
            args.anki_deck_content = None 
            word_script_args = get_script_args(args, python_path, workspace_path, config, anki_mapping)
            
            word_filename_basename = run_extraction_script(word_script_args)
            if not word_filename_basename:
                sys.exit(1)

            args.anki_deck_content = original_deck_content
            args.anki_parent_deck = parent_deck_name

        if 'fill' in stages:
            if word_filename_basename:
                run_fill_stage(word_filename_basename, args, python_path, workspace_path, config)

        if 'import' in stages and not args.skip_import:
            if sentence_filename_basename:
                args.anki_parent_deck = parent_deck_name
                print_debug(f"\n--- Importing SENTENCE file: {sentence_filename_basename} ---")
                run_importer_script(sentence_filename_basename, args, python_path, workspace_path, importer_workspace, config)

            if word_filename_basename:
                args.anki_parent_deck = parent_deck_name
                print_debug(f"\n--- Importing WORD file: {word_filename_basename} ---")
                run_importer_script(word_filename_basename, args, python_path, workspace_path, importer_workspace, config)

        print_debug("\nAll operations for mixed-triple mode completed successfully.")
        
        if args.show_success_message:
            if 'import' not in stages or args.skip_import:
                success_message = f"Completed successfully!\n\nTSV files generated."
            else:
                success_message = f"Completed successfully!\n\nCards have been imported into the deck:\n{parent_deck_name}"
            print(success_message)

    else: # Logic for single, dual, triple modes
        output_filename_basename = None
        if 'extract' in stages:
            script_args = get_script_args(args, python_path, workspace_path, config, anki_mapping)
            output_filename_basename = run_extraction_script(script_args)
            if not output_filename_basename:
                sys.exit(1)
        
        if 'fill' in stages and args.type == "word":
            if output_filename_basename:
                run_fill_stage(output_filename_basename, args, python_path, workspace_path, config)
        
        if 'import' in stages and not args.skip_import:
            if output_filename_basename:
                run_importer_script(output_filename_basename, args, python_path, workspace_path, importer_workspace, config)
        
        if output_filename_basename:
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
    if "--structured-output" in sys.argv or "--json-ipc" in sys.argv:
        try:
            main()
        except StructuredError as e:
            e.exit()
        except ConfigurationError as e:
            err = StructuredError(ErrorCode.ERR_SCHEMA_MISMATCH, str(e))
            err.exit()
        except SystemExit as e:
            if e.code != 0:
                msg = str(e.code) if e.code else "Unknown exit code"
                err = StructuredError(ErrorCode.ERR_UNHANDLED_EXCEPTION, f"Process exited with {msg}")
                err.exit()
            else:
                sys.exit(0)
        except Exception as e:
            import traceback
            context = {"traceback": traceback.format_exc()}
            err = StructuredError(ErrorCode.ERR_UNHANDLED_EXCEPTION, str(e), context)
            err.exit()
    else:
        try:
            main()
        except ConfigurationError as e:
            print_debug(f"ERROR: {e}")
            sys.exit(1)