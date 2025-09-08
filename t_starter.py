import subprocess
from pathlib import Path
import argparse

def get_token_args(args, python_path, token_workspace):
    """Builds the list of command-line arguments for calling token_mix_combined.py."""
    if args.language == "en":
        lemma_file = "en-news-2023-1m-words.csv"
        override_file = "U:\\voothi\\20241223170748-token-extraction\\lemma_override_en.tsv"
    elif args.language == "de":
        lemma_file = "deu-mixed-typical-2011-1m-words.csv"
        override_file = "U:\\voothi\\20241223170748-token-extraction\\lemma_override_de.tsv"
    else:
        raise ValueError(f"Unsupported language: {args.language}")

    base_args = [
        str(python_path),
        str(token_workspace / "token_mix_combined.py"),
        "--type",
        args.type,
        "--language",
        args.language,
        "--lemma-index-file",
        str(token_workspace / lemma_file),
        "--sentence-context-size",
        "2",
        "--file-timestamp",
        "--file-autoname",
        "--file-print-name",
        "--output-anki-header",
        "--column-source-word",
        "--column-sentence-wordlist",
        "--column-wordlist-use-br",
        "--lemma-override-file",
        override_file,
    ]

    if args.language == "de":
        german_enhancement_args = [
            "--de-fix-genitive",
            "--de-dictionary",
            "U:\\voothi\\20241223170748-token-extraction\\20250826000433-test\\german.dic",
        ]
        base_args.extend(german_enhancement_args)

        if args.gcs:
            gcs_args = [
                "--de-gcs",
                "--de-gcs-preserve-compound-word",
                "--de-gcs-add-parts-to-wordlist",
                "--de-gcs-split-mode", "combined",
                "--de-gcs-skip-merge-fractions",
            ]

            if args.gcs_pos_tags:
                gcs_args.append("--de-gcs-pos-tags")
                gcs_args.extend(args.gcs_pos_tags)
            
            base_args.extend(gcs_args)

    output_suffix = "sentence" if args.type == "sentence" else "token"

    if args.mode == "single":
        single_mode_args = []
        
        if args.text:
            single_mode_args.extend(["--text", args.text])
        else:
            single_mode_args.extend(["--text1", str(token_workspace / "in/text1.txt")])
            
        single_mode_args.extend([
            "--output",
            str(token_workspace / f"out/result.single.{output_suffix}.{args.language}.tsv"),
        ])
        
        return base_args + single_mode_args
        
    elif args.mode == "dual":
        return base_args + [
            "--text1",
            str(token_workspace / "in/text1.txt"),
            "--text2",
            str(token_workspace / "in/text2.txt"),
            "--output",
            str(token_workspace / f"out/result.dual.{output_suffix}.{args.language}.tsv"),
        ]
    elif args.mode == "triple":
        return base_args + [
            "--text1",
            str(token_workspace / "in/text1.txt"),
            "--text2",
            str(token_workspace / "in/text2.txt"),
            "--text3",
            str(token_workspace / "in/text3.txt"),
            "--output",
            str(token_workspace / f"out/result.triple.{output_suffix}.{args.language}.tsv"),
        ]

    raise ValueError(f"Unknown mode: {args.mode}")


def main():
    parser = argparse.ArgumentParser(
        description="A wrapper script to extract and process tokens or sentences from text files and import them."
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
        "--gcs",
        action='store_true',
        help="Enable German Compound Splitting (only effective when --language is 'de').",
    )
    parser.add_argument(
        "--gcs-pos-tags",
        nargs='+',
        default=['NOUN', 'PROPN', 'ADV', 'ADJ'],
        help="Specify which Part-of-Speech tags to apply GCS splitting to (e.g., NOUN PROPN or !VERB).",
    )
    args = parser.parse_args()

    python_path = Path(
        r"U:/voothi/20250825231214-spacy-env/Scripts/python.exe"
    )
    token_workspace = Path(r"U:/voothi/20241223170748-token-extraction")
    importer_workspace = Path(r"U:/voothi/20250401192017-anki-csv-importer")

    token_args = get_token_args(args, python_path, token_workspace)

    print(f"Running token extraction with command:\n{' '.join(token_args)}\n")
    token_process = subprocess.Popen(
        token_args,
        stdout=subprocess.PIPE,
        text=True,
        encoding='utf-8',
        errors='replace'
    )

    output_file = token_process.stdout.readline().strip()
    if not output_file:
        print("ERROR: No output file was captured from token_mix_combined.py")
        stderr_output, _ = token_process.communicate()
        if stderr_output:
            print("--- Stderr from token_mix_combined.py ---")
            print(stderr_output)
            print("-----------------------------------------")
        return

    print(f"Processing file: {output_file}")

    importer_command = [
        str(python_path),
        str(importer_workspace / "anki-csv-importer.py"),
        "--path",
        str(token_workspace / "out" / output_file),
        "--deck",
        output_file,
        "--note",
        "Basic 20240218092126",
    ]
    print(f"Running importer with command:\n{' '.join(importer_command)}\n")
    subprocess.run(importer_command, check=True)


if __name__ == "__main__":
    main()