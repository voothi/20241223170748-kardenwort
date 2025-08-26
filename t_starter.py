import subprocess
from pathlib import Path
import argparse


def get_token_args(args, python_path, token_workspace):
    """Configure token extraction arguments based on input parameters"""
    # Select lemma index file based on language
    if args.language == "en":
        lemma_file = "en-news-2023-1m-words.csv"
    elif args.language == "de":
        lemma_file = "deu-mixed-typical-2011-1m-words.csv"
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
        "--timestamp",
        "--two-column-output-to-file",
        "--include-simple-list",
        "--with-fields",
        "--with-br",
        "--autoname",
        "--gcs",
        "--gcs-dictionary",
        "U:/voothi/20241223170748-token-extraction/20250826000433-test/german.dic",
        "--gcs-in-wordlist",
        "--pipe"
    ]

    output_suffix = "sentence" if args.type == "sentence" else "token"

    # --- ИЗМЕНЕННЫЙ БЛОК ДЛЯ РЕЖИМА 'single' ---
    if args.mode == "single":
        # Создаем изменяемый список аргументов для этого режима
        single_mode_args = []
        
        # Если передан текст напрямую через --text, используем его
        if args.text:
            single_mode_args.extend(["--text", args.text])
        # В противном случае, используем файл text1.txt (старое поведение)
        else:
            single_mode_args.extend(["--text1", str(token_workspace / "in/text1.txt")])
            
        # Добавляем общие для режима 'single' аргументы
        single_mode_args.extend([
            "--output",
            str(token_workspace / f"out/result.single.{output_suffix}.{args.language}.tsv"),
        ])
        
        return base_args + single_mode_args
    # --- КОНЕЦ ИЗМЕНЕННОГО БЛОКА ---
        
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
        choices=["single", "dual", "triple"],
        help="Processing mode: single (text1), dual (text1 + text2), or triple (text1 + text2 + text3)",
    )
    parser.add_argument(
        "--language",
        type=str,
        required=True,
        choices=["de", "en"],
        help="Language for processing: German (de) or English (en)",
    )
    # --- НОВЫЙ АРГУМЕНТ ---
    parser.add_argument(
        "--text",
        type=str,
        help="Directly pass a text string for 'single' mode processing, bypassing the text1.txt file."
    )
    args = parser.parse_args()

    # Configure paths
    python_path = Path(
        r"U:/voothi/20250825231214-spacy-env/Scripts/python.exe"
    )
    token_workspace = Path(r"U:/voothi/20241223170748-token-extraction")
    importer_workspace = Path(r"U:/voothi/20250401192017-anki-csv-importer")

    # Get command arguments based on type
    token_args = get_token_args(args, python_path, token_workspace)

    # Token extraction process
    print(f"Running token extraction with command:\n{' '.join(token_args)}\n")
    token_process = subprocess.Popen(
        token_args,
        stdout=subprocess.PIPE,
        text=True,
        encoding='utf-8', # Явно указываем кодировку для надежности
        errors='replace'
    )

    # Get output filename from token extraction
    output_file = token_process.stdout.readline().strip()
    if not output_file:
        print("ERROR: No output file was captured from token_mix_combined.py")
        # Выводим возможные ошибки из stderr для диагностики
        stderr_output = token_process.communicate()[1]
        if stderr_output:
            print("--- Stderr from token_mix_combined.py ---")
            print(stderr_output)
            print("-----------------------------------------")
        return

    print(f"Processing file: {output_file}")

    # Run Anki importer with the captured filename
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