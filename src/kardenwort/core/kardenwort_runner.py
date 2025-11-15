import subprocess
from pathlib import Path
import argparse
import configparser
import sys
import os
import re

def print_debug(message):
    print(message, file=sys.stderr)

def load_config():
    config_path = Path(__file__).resolve().parent.parent.parent.parent / 'config.ini'
    if not config_path.exists():
        print_debug(f"ERROR: Configuration file not found at {config_path}")
        print_debug("Please copy 'config.ini.template' to 'config.ini' and fill it in.")
        sys.exit(1)

    project_root = config_path.parent
    
    config = configparser.ConfigParser()
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
        "--add-source-word-col",
        "--add-wordlist-col",
        "--add-sentence-index-col",
        "--wordlist-use-br",
        "--add-header",
        "--sentence-context-size", "4",
    ]

    if args.tts_destination_lang:
        base_args.extend(["--tts-destination-lang", args.tts_destination_lang])

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
    output_template = config.get('output_format', 'output_template', fallback='result.{mode}.{suffix}.{language}.tsv')
    output_filename = output_template.format(
        mode=args.mode,
        suffix=output_suffix,
        language=args.language
    )
    
    mode_args = []
    text1_filename = config.get('input_files', 'text1_file', fallback='text1.txt')
    text2_filename = config.get('input_files', 'text2_file', fallback='text2.txt')
    text3_filename = config.get('input_files', 'text3_file', fallback='text3.txt')

    if args.mode == "single":
        input_text_from_env = os.environ.get('KARDENWORT_INPUT_TEXT')
        if input_text_from_env:
            mode_args.extend(["--text", input_text_from_env])
        elif args.text:
            mode_args.extend(["--text", args.text])
        else:
            mode_args.extend(["--text1-file", str(input_path / text1_filename)])
    elif args.mode == "dual":
        mode_args.extend(["--text1-file", str(input_path / text1_filename)])
        mode_args.extend(["--text2-file", str(input_path / text2_filename)])
    elif args.mode == "triple":
        mode_args.extend(["--text1-file", str(input_path / text1_filename)])
        mode_args.extend(["--text2-file", str(input_path / text2_filename)])
        mode_args.extend(["--text3-file", str(input_path / text3_filename)])
    else:
        raise ValueError(f"Unknown mode: {args.mode}")

    mode_args.extend(["--output-file", str(output_path / output_filename)])
    return base_args + mode_args


def main():
    if "--get-python-path" in sys.argv:
        python_path, _, _, _ = load_config()
        print(python_path)
        sys.exit(0)

    parser = argparse.ArgumentParser(
        description="A wrapper script to extract and process words or sentences from text files and import them into Anki."
    )
    parser.add_argument("--type", type=str, required=True, choices=["word", "sentence"], help="Type of processing: 'word' for word extraction, 'sentence' for parallel sentences.")
    parser.add_argument("--mode", type=str, required=True, choices=["single", "dual", "triple"], help="Processing mode: single (text1), dual (text1 + text2), or triple (text1 + text2 + text3).")
    parser.add_argument("--language", type=str, required=True, choices=["de", "en"], help="Language for processing: German (de) or English (en).")
    parser.add_argument("--deduplication-scope", type=str, choices=['global', 'sentence', 'none'], default='global', help="Set the scope for lemma deduplication.")
    parser.add_argument("--tts-destination-lang", type=str, help="Specify the destination language for TTS field activation (e.g., 'ru', 'en').")
    parser.add_argument("--text", type=str, help="Directly pass a text string for 'single' mode processing, bypassing the default text1.txt file.")
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

    args = parser.parse_args()

    python_path, workspace_path, importer_workspace, config = load_config()
    script_args = get_script_args(args, python_path, workspace_path, config)

    print_debug(f"Running extraction script with command:\n{' '.join(map(str, script_args))}\n")
    
    script_process = subprocess.Popen(
        script_args,
        stdout=subprocess.PIPE,
        stderr=None,
        text=True,
        encoding='utf-8',
        errors='replace'
    )
    stdout_output, _ = script_process.communicate()
    
    if script_process.returncode != 0:
        print_debug(f"ERROR: The extraction script failed with exit code {script_process.returncode}.")
        sys.exit(1)

    output_lines = stdout_output.strip().splitlines()
    if not output_lines:
        print_debug("ERROR: No output filename was captured from the script.")
        sys.exit(1)
        
    output_filename_basename = output_lines[0].strip()

    print_debug(f"Processing file: {output_filename_basename}")

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

    print(output_filename_basename)

if __name__ == "__main__":
    main()