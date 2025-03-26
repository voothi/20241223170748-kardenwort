import argparse
import sys
import spacy
import csv
from datetime import datetime


def get_verb_with_particle(token):
    """Check if a verb token has a separable prefix and combine them"""
    if token.pos_ == "VERB":
        for particle in token.rights:
            if particle.dep_ == "svp":  # svp = separable verb prefix
                return f"{particle.text}{token.lemma_}"
    return token.lemma_


def load_lemma_index(file_path):
    """Load lemma frequency index from CSV file"""
    lemma_index = {}
    try:
        with open(file_path, "r", newline="", encoding="utf-8") as csvfile:
            csv_reader = csv.reader(csvfile)
            for line_number, row in enumerate(csv_reader):
                if row:  # Skip empty rows
                    word = row[0]
                    if (
                        word not in lemma_index
                    ):  # Add only if lemma not yet in dictionary
                        lemma_index[word] = line_number
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        return {}
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return {}
    return lemma_index


def process_sentence_lemmas(sentence, lemma_index, nlp):
    """Extract and sort lemmas from a sentence based on frequency index"""
    doc = nlp(sentence)
    sentence_tokens = set()

    for token in doc:
        if token.is_alpha and token.dep_ != "svp":
            if token.pos_ == "VERB":
                verb_form = get_verb_with_particle(token)
                sentence_tokens.add(verb_form)
            else:
                sentence_tokens.add(token.lemma_)

    # Sort tokens by frequency index
    return sorted(sentence_tokens, key=lambda x: lemma_index.get(x, float("inf")))


def main():
    parser = argparse.ArgumentParser(
        description="Generate TSV with sentence contexts from aligned translations."
    )
    parser.add_argument(
        "--text1",
        required=True,
        help="Path to the first text file (German/English sentences)",
    )
    parser.add_argument(
        "--text2",
        required=True,
        help="Path to the second text file (German/English translations)",
    )
    parser.add_argument("--out", required=True, help="Path to the output TSV file")
    parser.add_argument(
        "--sentence-context-size",
        type=int,
        default=1,
        help="Number of sentences to capture on each side (default: 1)",
    )
    parser.add_argument(
        "--include-simple-list",
        action="store_true",
        help="Include frequency-sorted lemma list column",
    )
    parser.add_argument(
        "--timestamp",
        action="store_true",
        help="Prepend timestamp to the output file name",
    )

    parser.add_argument(
        "--language",
        type=str,
        choices=["de", "en"],
        default="de",
        help="Language of the input text (default: de)",
    )
    parser.add_argument(
        "--lemma-index-file",
        type=str,
        default="",
        help="Path to frequency-ranked lemma CSV",
    )

    args = parser.parse_args()

    if args.timestamp:
        import os

        # Extract the directory and filename from the output path
        output_dir = os.path.dirname(args.out)
        output_filename = os.path.basename(args.out)
        # Prepend timestamp to the filename
        timestamp_str = datetime.now().strftime("%Y%m%d%H%M%S")
        new_output_filename = f"{timestamp_str}-{output_filename}"
        args.out = os.path.join(output_dir, new_output_filename)

    # Determine the lemma index file based on the language
    if not args.lemma_index_file:
        if args.language == "de":
            args.lemma_index_file = "U:\\voothi\\20241223170748-token-extraction\\en-default.csv"
        elif args.language == "en":
            args.lemma_index_file = (
                "U:\\voothi\\20241223170748-token-extraction\\en-default.csv"
            )

    # Load spaCy model based on language
    language_model_map = {"de": "de_core_news_lg", "en": "en_core_web_lg"}
    nlp = spacy.load(language_model_map[args.language])

    # Load lemma index if simple list is requested
    lemma_index = {}
    if args.include_simple_list:
        lemma_index = load_lemma_index(args.lemma_index_file)

    # Read input files
    try:
        with open(args.text1, "r", encoding="utf-8") as f:
            text1_lines = [line.rstrip("\n") for line in f]
        with open(args.text2, "r", encoding="utf-8") as f:
            text2_lines = [line.rstrip("\n") for line in f]
    except IOError as e:
        print(f"Error reading files: {e}", file=sys.stderr)
        sys.exit(1)

    # Validate line counts
    if len(text1_lines) != len(text2_lines):
        print(
            f"Warning: Line count mismatch - Text1: {len(text1_lines)}, Text2: {len(text2_lines)}",
            file=sys.stderr,
        )

    context_size = args.sentence_context_size
    min_length = min(len(text1_lines), len(text2_lines))

    # Process lines and write output
    try:
        with open(args.out, "w", newline="", encoding="utf-8") as out_file:
            tsv_writer = csv.writer(out_file, delimiter="\t")
            for i in range(min_length):
                # Process German text
                de_sentence = text1_lines[i]
                de_left = text1_lines[max(0, i - context_size) : i]
                de_right = text1_lines[i + 1 : i + 1 + context_size]

                # Process Russian text
                ru_sentence = text2_lines[i]
                ru_left = text2_lines[max(0, i - context_size) : i]
                ru_right = text2_lines[i + 1 : i + 1 + context_size]

                # Join context sentences
                de_left_str = " ".join(de_left)
                de_right_str = " ".join(de_right)
                ru_left_str = " ".join(ru_left)
                ru_right_str = " ".join(ru_right)

                # Process lemmas if simple list is requested
                simple_list = ""
                if args.include_simple_list:
                    lemmas = process_sentence_lemmas(de_sentence, lemma_index, nlp)
                    simple_list = "\n".join(lemmas)  # Newline-separated without quotes

                # Format TSV line
                if args.language == "de":
                    tsv_line = (
                        "\t".join(
                            [
                                de_sentence,
                                "",
                                "",
                                "",
                                "",
                                de_left_str,
                                de_sentence,
                                de_right_str,
                                ru_left_str,
                                ru_sentence,
                                ru_right_str,
                                f'"{simple_list}"',
                                de_sentence,
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "1",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "1",
                            ]
                        )
                        + "\n"
                    )

                if args.language == "en":
                    tsv_line = (
                        "\t".join(
                            [
                                de_sentence,
                                "",
                                "",
                                "",
                                "",
                                de_left_str,
                                de_sentence,
                                de_right_str,
                                ru_left_str,
                                ru_sentence,
                                ru_right_str,
                                f'"{simple_list}"',
                                de_sentence,
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "1",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "1",
                            ]
                        )
                        + "\n"
                    )

                out_file.write(tsv_line)
    except IOError as e:
        print(f"Error writing output: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
