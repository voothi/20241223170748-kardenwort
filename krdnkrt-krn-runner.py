import subprocess
from pathlib import Path
import argparse
import configparser
import platform
import sys

def load_config():
    """Reads paths from config.ini based on the operating system."""
    config_path = Path(__file__).parent / 'config.ini'
    if not config_path.exists():
        print(f"ERROR: Configuration file not found at {config_path}", file=sys.stderr)
        print("Please copy 'config.ini.template' to 'config.ini' and fill in the correct paths.", file=sys.stderr)
        sys.exit(1)

    config = configparser.ConfigParser()
    config.read(config_path)

    os_type = platform.system()
    section = 'paths_nix' if os_type == "Linux" or os_type == "Darwin" else 'paths_windows'

    if section not in config:
        print(f"ERROR: Missing section [{section}] in {config_path}", file=sys.stderr)
        sys.exit(1)

    try:
        python_path = Path(config[section]['python_path'])
        importer_workspace = Path(config[section]['importer_workspace'])
        workspace_path = Path(__file__).parent
    except KeyError as e:
        print(f"ERROR: Missing key {e} in section [{section}] of {config_path}", file=sys.stderr)
        sys.exit(1)

    return python_path, workspace_path, importer_workspace


def get_script_args(args, python_path, workspace_path):
    """Builds the list of command-line arguments for calling the main script."""

    data_path = workspace_path / "data"

    if args.language == "en":
        lemma_file = "en-news-2023-1m-words.csv"
        override_file = str(data_path / "lemma_override_en.tsv")
    elif args.language == "de":
        lemma_file = "deu-mixed-typical-2011-1m-words.csv"
        override_file = str(data_path / "lemma_override_de.tsv")
    else:
        raise ValueError(f"Unsupported language: {args.language}")

    base_args = [
        str(python_path),
        str(workspace_path / "krdnkrt-krn.py"),
        "--type", args.type,
        "--language", args.language,
        "--lemma-index-file", str(data_path / lemma_file),
        "--sentence-context-size", "2",
        "--basename-add-timestamp",
        "--basename-add-first-words",
        "--stdout-print-output-basename",
        "--add-header",
        "--add-source-word-col",
        "--add-wordlist-col",
        "--wordlist-use-br",
        "--lemma-override-file", override_file,
    ]

    if args.language == "de":
        german_enhancement_args = [
            "--de-fix-genitive",
            "--de-dictionary-file", str(data_path / "german.dic"),
        ]
        base_args.extend(german_enhancement_args)

        if args.de_gcs:
            gcs_args = [
                "--de-gcs",
                "--de-gcs-preserve-compound-word",
                "--de-gcs-add-parts-to-wordlist",
                "--de-gcs-split-mode", "combined",
                "--de-gcs-skip-merge-fractions",
            ]
            
            if args.de_gcs_pos_tags:
                gcs_args.append("--de-gcs-pos-tags")
                gcs_args.extend(args.de_gcs_pos_tags)
            
            base_args.extend(gcs_args)

    output_suffix = "sentence" if args.type == "sentence" else "word"

    if args.mode == "single":
        single_mode_args = []
        
        if args.text:
            single_mode_args.extend(["--text", args.text])
        else:
            single_mode_args.extend(["--text1-file", str(workspace_path / "in/text1.txt")])
            
        single_mode_args.extend([
            "--output-file",
            str(workspace_path / f"out/result.single.{output_suffix}.{args.language}.tsv"),
        ])
        
        return base_args + single_mode_args
        
    elif args.mode == "dual":
        return base_args + [
            "--text1-file", str(workspace_path / "in/text1.txt"),
            "--text2-file", str(workspace_path / "in/text2.txt"),
            "--output-file", str(workspace_path / f"out/result.dual.{output_suffix}.{args.language}.tsv"),
        ]
    elif args.mode == "triple":
        return base_args + [
            "--text1-file", str(workspace_path / "in/text1.txt"),
            "--text2-file", str(workspace_path / "in/text2.txt"),
            "--text3-file", str(workspace_path / "in/text3.txt"),
            "--output-file", str(workspace_path / f"out/result.triple.{output_suffix}.{args.language}.tsv"),
        ]

    raise ValueError(f"Unknown mode: {args.mode}")


def main():
    if "--get-python-path" in sys.argv:
        python_path, _, _ = load_config()
        print(python_path)
        sys.exit(0)

    parser = argparse.ArgumentParser(
        description="A wrapper script to extract and process words or sentences from text files and import them."
    )
    parser.add_argument(
        "--type",
        type=str,
        required=True,
        choices=["word", "sentence"],
        help="Type of processing: 'word' for word extraction, 'sentence' for parallel sentences.",
    )
    parser.add_argument(
        "--mode",
        type=str,
        required=True,
        choices=["single", "dual", "triple"],
        help="Processing mode: single (text1), dual (text1 + text2), or triple (text1 + text2 + text3).",
    )
    parser.add_argument(
        "--language",
        type=str,
        required=True,
        choices=["de", "en"],
        help="Language for processing: German (de) or English (en).",
    )
    parser.add_argument(
        "--text",
        type=str,
        help="Directly pass a text string for 'single' mode processing, bypassing the default text1.txt file.",
    )
    parser.add_argument(
        "--de-gcs",
        action='store_true',
        help="Enable German Compound Splitting (only effective when --language is 'de').",
    )
    parser.add_argument(
        "--de-gcs-pos-tags",
        nargs='+',
        default=['NOUN', 'PROPN', 'ADV', 'ADJ'],
        help="Specify which Part-of-Speech tags to apply GCS splitting to (e.g., NOUN PROPN or !VERB).",
    )
    args = parser.parse_args()

    python_path, workspace_path, importer_workspace = load_config()

    script_args = get_script_args(args, python_path, workspace_path)

    print(f"Running extraction script with command:\n{' '.join(script_args)}\n")
    script_process = subprocess.Popen(
        script_args,
        stdout=subprocess.PIPE,
        text=True,
        encoding='utf-8',
        errors='replace'
    )

    output_file = script_process.stdout.readline().strip()
    if not output_file:
        print("ERROR: No output filename was captured from the script.", file=sys.stderr)
        stderr_output, _ = script_process.communicate()
        if stderr_output:
            print("--- stderr from script ---", file=sys.stderr)
            print(stderr_output, file=sys.stderr)
            print("--------------------------", file=sys.stderr)
        return

    print(f"Processing file: {output_file}")

    importer_command = [
        str(python_path),
        str(importer_workspace / "anki-csv-importer.py"),
        "--path", str(workspace_path / "out" / output_file),
        "--deck", output_file,
        "--note", "Basic 20240218092126",
    ]
    print(f"Running importer with command:\n{' '.join(importer_command)}\n")
    subprocess.run(importer_command, check=True)


if __name__ == "__main__":
    main()