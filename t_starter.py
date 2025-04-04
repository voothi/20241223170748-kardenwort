import subprocess
from pathlib import Path
import argparse


def get_token_args(args, python_path, token_workspace):
    """Configure token extraction arguments based on input parameters"""
    base_args = [
        str(python_path),
        str(token_workspace / "token_mix_combined.py"),
        "--type",
        args.type,
        "--language",
        "de",
        "--lemma-index-file",
        str(token_workspace / "deu-mixed-typical-2011-1m-words.csv"),
        "--sentence-context-size",
        "2",
        "--timestamp",
        "--two-column-output-to-file",
        "--include-simple-list",
        "--with-fields",
        "--with-br",
        "--pipe",
    ]

    output_suffix = "sentence" if args.type == "sentence" else "token"

    if args.mode == "single":
        return base_args + [
            "--text1",
            str(token_workspace / "in/text1.txt"),
            "--output",
            str(token_workspace / f"out/result.single.{output_suffix}.de.tsv"),
        ]
    elif args.mode == "dual":
        return base_args + [
            "--text1",
            str(token_workspace / "in/text1.txt"),
            "--text2",
            str(token_workspace / "in/text2.txt"),
            "--output",
            str(token_workspace / f"out/result.dual.{output_suffix}.de.tsv"),
        ]

    raise ValueError(f"Unknown mode: {args.mode}")


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Extract and process tokens or sentences from text."
    )
    parser.add_argument(
        "--type",
        type=str,
        required=True,
        choices=["token", "sentence"],
        help="Type of processing: token or sentence",
    )
    parser.add_argument(
        "--mode",
        type=str,
        required=True,
        choices=["single", "dual"],
        help="Processing mode: single (text1) or dual (text1 + text2)",
    )
    args = parser.parse_args()

    # Configure paths
    python_path = Path(
        r"C:/Users/voothi/AppData/Roaming/Anki2/addons21/spacyenv/Scripts/python.exe"
    )
    token_workspace = Path(r"U:/voothi/20241223170748-token-extraction")
    importer_workspace = Path(r"U:/voothi/20250401192017-anki-csv-importer")

    # Get command arguments based on type
    token_args = get_token_args(args, python_path, token_workspace)

    # Token extraction process
    token_process = subprocess.Popen(
        token_args,
        stdout=subprocess.PIPE,
        text=True,
    )

    # Get output filename from token extraction
    output_file = token_process.stdout.readline().strip()
    if not output_file:
        print("ERROR: No output file was captured")
        return

    print(f"Processing file: {output_file}")

    # Run Anki importer with the captured filename
    subprocess.run(
        [
            str(python_path),
            str(importer_workspace / "anki-csv-importer.py"),
            "--path",
            str(token_workspace / "out" / output_file),
            "--deck",
            output_file,
            "--note",
            "Basic 20240218092126",
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
