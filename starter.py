import subprocess
from pathlib import Path


def main():
    # Configure paths
    python_path = Path(
        r"C:/Users/voothi/AppData/Roaming/Anki2/addons21/spacyenv/Scripts/python.exe"
    )
    token_workspace = Path(r"U:/voothi/20241223170748-token-extraction")
    importer_workspace = Path(r"U:/voothi/20250401192017-anki-csv-importer")

    # Token extraction process
    token_process = subprocess.Popen(
        [
            str(python_path),
            str(token_workspace / "token_mix_combined.py"),
            "--type",
            "token",
            "--language",
            "de",
            "--text1",
            str(token_workspace / "in/text1.txt"),
            "--sentence-context-size",
            "2",
            "--output",
            str(token_workspace / "out/result-t1.token.de.tsv"),
            "--timestamp",
            "--include-simple-list",
            "--with-fields",
            "--with-br",
            "--pipe",
            "--lemma-index-file",
            str(token_workspace / "deu-mixed-typical-2011-1m-words.csv"),
        ],
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
