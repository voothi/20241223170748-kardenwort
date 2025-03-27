import sys
import spacy
import csv
import argparse
from datetime import datetime
import os


def get_verb_with_particle(token):
    """
    Check if a verb token has a separable prefix and combine them.
    Returns the combined form for separable verbs or just the lemma for regular verbs.
    """
    if token.pos_ == "VERB":
        for particle in token.rights:
            if particle.dep_ == "svp":  # svp = separable verb prefix
                return f"{particle.text}{token.lemma_}"
    return token.lemma_


def get_original_form_with_particle(token):
    if token.pos_ == "VERB":
        particle = next(
            (child for child in token.children if child.dep_ == "svp"), None
        )
        if particle:
            return f"{token.text} {particle.text}"
    return token.text


def load_lemma_index(file_path):
    lemma_index = {}
    try:
        with open(file_path, "r", newline="", encoding="utf-8") as csvfile:
            csv_reader = csv.reader(csvfile)
            for line_number, row in enumerate(csv_reader):
                if row:  # Skip empty rows
                    word = row[0]
                    if (
                        word not in lemma_index
                    ):  # Add only if the lemma is not yet in the dictionary
                        lemma_index[word] = line_number
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        return {}
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return {}
    return lemma_index


def read_input_text(input_file):
    try:
        with open(input_file, "r", encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError:
        print(f"File not found: {input_file}")
        exit(1)
    except Exception as e:
        print(f"Error reading file {input_file}: {e}")
        exit(1)


def process_sentence_lemmas(sentence, lemma_index, nlp):
    """
    Extract and sort lemmas from a sentence based on frequency index.
    """
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


def process_text(
    input_text,
    output_file,
    sentence_context_size,
    detailed_output,
    include_simple_list,
    lemma_index_file,
    two_column_output,
    html_output,
    timestamp,
    original_form_in_simple_list,
    two_column_output_to_file,
    language,
    text2=None,
):
    # Load the lemma index
    lemma_index = load_lemma_index(lemma_index_file)

    # Check if input_text is a file path or raw text
    if "\n" in input_text or not os.path.exists(input_text):
        # Treat input_text as raw text
        text1_lines = input_text.splitlines()
    else:
        # Treat input_text as a file path
        with open(input_text, "r", encoding="utf-8") as f1:
            text1_lines = [line.rstrip("\n") for line in f1]

    if text2:
        # Read text2 as a file
        with open(text2, "r", encoding="utf-8") as f2:
            text2_lines = [line.rstrip("\\n") for line in f2]

        if len(text1_lines) != len(text2_lines):
            print(
                f"Warning: Mismatch in line counts - text1: {len(text1_lines)}, text2: {len(text2_lines)}",
                file=sys.stderr,
            )
            min_length = min(len(text1_lines), len(text2_lines))
            text1_lines = text1_lines[:min_length]
            text2_lines = text2_lines[:min_length]

        # Process each line
        unique_lemmatized_tokens = set()
        token_to_sentence = {}
        token_to_original_form = {}

        for i, (line1, line2) in enumerate(zip(text1_lines, text2_lines)):
            # Process tokens in line1 using spaCy
            doc = nlp(line1)
            for token in doc:
                if token.is_alpha:
                    if token.pos_ == "VERB":
                        if language == "de":
                            verb_form = get_verb_with_particle(token)
                        else:
                            verb_form = token.lemma_
                        unique_lemmatized_tokens.add(verb_form)
                        token_to_sentence[verb_form] = (i, line1)
                        if language == "de":
                            token_to_original_form[verb_form] = (
                                get_original_form_with_particle(token)
                            )
                        else:
                            token_to_original_form[verb_form] = token.text
                    elif token.dep_ != "svp":
                        unique_lemmatized_tokens.add(token.lemma_)
                        token_to_sentence[token.lemma_] = (i, line1)
                        token_to_original_form[token.lemma_] = token.text

    else:
        # Handle single text processing
        unique_lemmatized_tokens = set()
        token_to_sentence = {}
        token_to_original_form = {}

        # Process the entire input_text as a single document
        if "\n" in input_text or not os.path.exists(input_text):
            # Treat as raw text
            text_content = input_text
        else:
            # Read the file
            with open(input_text, "r", encoding="utf-8") as f:
                text_content = f.read()

        doc = nlp(text_content)
        sentences = list(doc.sents)
        for token in doc:
            if token.is_alpha and token.dep_ != "svp":
                if token.pos_ == "VERB":
                    if language == "de":
                        verb_form = get_verb_with_particle(token)
                    else:
                        verb_form = token.lemma_
                    unique_lemmatized_tokens.add(verb_form)
                    token_to_sentence[verb_form] = (
                        0,
                        token.sent.text,
                    )  # Use sentence context
                    if language == "de":
                        token_to_original_form[verb_form] = (
                            get_original_form_with_particle(token)
                        )
                    else:
                        token_to_original_form[verb_form] = token.text
                else:
                    unique_lemmatized_tokens.add(token.lemma_)
                    token_to_sentence[token.lemma_] = (0, token.sent.text)
                    token_to_original_form[token.lemma_] = token.text

        # Divide tokens into found and not found
        found_tokens = [
            token for token in unique_lemmatized_tokens if token in lemma_index
        ]
        not_found_tokens = [
            token for token in unique_lemmatized_tokens if token not in lemma_index
        ]

        # Sort tokens
        sorted_found_tokens = sorted(found_tokens, key=lambda token: lemma_index[token])
        sorted_not_found_tokens = sorted(not_found_tokens)
        final_sorted_tokens = sorted_found_tokens + sorted_not_found_tokens

        # Write TSV without text2 columns
        if output_file:
            if timestamp:
                # Extract the directory and filename from the output path
                output_dir = os.path.dirname(output_file)
                output_filename = os.path.basename(output_file)
                # Prepend timestamp to the filename
                timestamp_str = datetime.now().strftime("%Y%m%d%H%M%S")
                new_output_filename = f"{timestamp_str}-{output_filename}"
                output_file = os.path.join(output_dir, new_output_filename)
            with open(output_file, "w", newline="", encoding="utf-8") as tsvfile:
                tsv_writer = csv.writer(tsvfile, delimiter="\t")
                for token in final_sorted_tokens:
                    sent_index, sentence = token_to_sentence[token]
                    original_form = token_to_original_form[token]

                    # Context sentences for single text
                    start_index = max(0, sent_index - sentence_context_size)
                    end_index = min(
                        len(sentences), sent_index + sentence_context_size + 1
                    )
                    left_context = " ".join(
                        sent.text for sent in sentences[start_index:sent_index]
                    )
                    right_context = " ".join(
                        sent.text for sent in sentences[sent_index + 1 : end_index]
                    )

                    # Simple list entry
                    simple_list_entry = ""
                    if include_simple_list:
                        lemmas = process_sentence_lemmas(sentence, lemma_index, nlp)
                        simple_list_entry = "\n".join(lemmas)

                    # Write row without text2 columns
                    if language == "de":
                        tsv_writer.writerow(
                            [
                                token,
                                token,
                                original_form,
                                "",
                                "",
                                left_context,
                                sentence,
                                right_context,
                                "",
                                "",
                                "",
                                simple_list_entry,
                                sentence,
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
                            ]
                        )
                    else:
                        tsv_writer.writerow(
                            [
                                token,
                                token,
                                "",
                                "",
                                "",
                                left_context,
                                sentence,
                                right_context,
                                "",
                                "",
                                "",
                                simple_list_entry,
                                sentence,
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
                            ]
                        )

        # Handle HTML, two-column, etc. outputs for single text case
        if html_output:
            print("<table>")
            for token in final_sorted_tokens:
                original_form = token_to_original_form[token]
                print(f"<tr><td>{token}</td><td>{original_form}</td></tr>")
            print("</table>")
        elif two_column_output:
            for token in final_sorted_tokens:
                original_form = token_to_original_form[token]
                print(f"{token}\t{original_form}")
        else:
            for token in final_sorted_tokens:
                print(token)
            print()

        if detailed_output:
            for token in final_sorted_tokens:
                sent_index, sentence = token_to_sentence[token]
                start_index = max(0, sent_index - sentence_context_size)
                end_index = min(len(sentences), sent_index + sentence_context_size + 1)
                left_context = " ".join(
                    sent.text for sent in sentences[start_index:sent_index]
                )
                right_context = " ".join(
                    sent.text for sent in sentences[sent_index + 1 : end_index]
                )
                print(token)
                if left_context:
                    print(left_context)
                print(sentence)
                if right_context:
                    print(right_context)
                print()
        # Divide tokens into two groups: found in reference and not found
        found_tokens = [
            token for token in unique_lemmatized_tokens if token in lemma_index
        ]
        not_found_tokens = [
            token for token in unique_lemmatized_tokens if token not in lemma_index
        ]

        # Sort tokens: found tokens by their reference index, not found tokens alphabetically
        sorted_found_tokens = sorted(found_tokens, key=lambda token: lemma_index[token])
        sorted_not_found_tokens = sorted(not_found_tokens)

        # Combine both lists: found tokens first, then not found tokens
        final_sorted_tokens = sorted_found_tokens + sorted_not_found_tokens

        # Write the results to TSV if output file is specified
        if output_file:
            if timestamp:

                # Extract the directory and filename from the output path
                output_dir = os.path.dirname(output_file)
                output_filename = os.path.basename(output_file)
                # Prepend timestamp to the filename
                timestamp_str = datetime.now().strftime("%Y%m%d%H%M%S")
                new_output_filename = f"{timestamp_str}-{output_filename}"
                output_file = os.path.join(output_dir, new_output_filename)

            with open(output_file, "w", newline="", encoding="utf-8") as tsvfile:
                tsv_writer = csv.writer(tsvfile, delimiter="\t")
                for token in final_sorted_tokens:
                    sent_index, l1_sentence = token_to_sentence[token]
                    l2_sentence = text2_lines[sent_index]

                    # Get context sentences
                    start_index = max(0, sent_index - sentence_context_size)
                    end_index = min(
                        len(text1_lines), sent_index + sentence_context_size + 1
                    )
                    l1_left_context = " ".join(text1_lines[start_index:sent_index])
                    l1_right_context = " ".join(text1_lines[sent_index + 1 : end_index])
                    l2_left_context = " ".join(text2_lines[start_index:sent_index])
                    l2_right_context = " ".join(text2_lines[sent_index + 1 : end_index])

                    # Перед циклом или использованием simple_list_entry
                    simple_list_entry = ""  # Инициализация переменной

                    # Внутри цикла или при обработке
                    if include_simple_list:
                        # Если требуется, обработайте и заполните simple_list_entry
                        lemmas = process_sentence_lemmas(l1_sentence, lemma_index, nlp)
                        simple_list_entry = "\n".join(lemmas)  # Пример заполнения

                    # Write the row
                    original_form = token_to_original_form[token]
                    if language == "de":
                        if two_column_output_to_file:
                            tsv_writer.writerow(
                                [
                                    token,
                                    token,
                                    original_form,
                                    "",
                                    "",
                                    l1_left_context,
                                    l1_sentence,
                                    l1_right_context,
                                    l2_left_context,
                                    l2_sentence,
                                    l2_right_context,
                                    simple_list_entry,
                                    l1_sentence,
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
                        else:
                            tsv_writer.writerow(
                                [
                                    token,
                                    token,
                                    "",
                                    "",
                                    "",
                                    l1_left_context,
                                    l1_sentence,
                                    l1_right_context,
                                    l2_left_context,
                                    l2_sentence,
                                    l2_right_context,
                                    simple_list_entry,
                                    l1_sentence,
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

                    if language == "en":
                        if two_column_output_to_file:
                            tsv_writer.writerow(
                                [
                                    token,
                                    token,
                                    original_form,
                                    "",
                                    "",
                                    l1_left_context,
                                    l1_sentence,
                                    l1_right_context,
                                    l2_left_context,
                                    l2_sentence,
                                    l2_right_context,
                                    simple_list_entry,
                                    l1_sentence,
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
                        else:
                            tsv_writer.writerow(
                                [
                                    token,
                                    token,
                                    "",
                                    "",
                                    "",
                                    l1_left_context,
                                    l1_sentence,
                                    l1_right_context,
                                    l2_left_context,
                                    l2_sentence,
                                    l2_right_context,
                                    simple_list_entry,
                                    l1_sentence,
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

        # Output tokens in HTML table if html_output is enabled
        if html_output:
            print("<table>")
            for token in final_sorted_tokens:
                original_form = token_to_original_form[token]
                print(f"<tr><td>{token}</td><td>{original_form}</td></tr>")
            print("</table>")
        elif two_column_output:
            for token in final_sorted_tokens:
                original_form = token_to_original_form[token]
                print(f"{token}\t{original_form}")
        else:
            for token in final_sorted_tokens:
                print(token)
            print()  # Empty line to separate the list of tokens from the detailed output

    # Print each token with its sentence and context if detailed output is requested
    if detailed_output:
        for token in final_sorted_tokens:
            sent_index, l1_sentence = token_to_sentence[token]
            # Get context sentences
            start_index = max(0, sent_index - sentence_context_size)
            end_index = min(len(text1_lines), sent_index + sentence_context_size + 1)
            l1_left_context = " ".join(
                line.strip() for line in text1_lines[start_index:sent_index]
            )
            l1_right_context = " ".join(
                line.strip() for line in text1_lines[sent_index + 1 : end_index]
            )

            # Print the formatted output
            print(token)
            if l1_left_context:
                print(l1_left_context)
            print(l1_sentence)
            if l1_right_context:
                print(l1_right_context)
            print()  # Empty line between entries


def process_sentences(
    text1,
    text2,
    output_file,
    sentence_context_size,
    include_simple_list,
    timestamp,
    lemma_index_file,
    language,
):
    # Determine the lemma index file based on the language
    if not lemma_index_file:
        if language == "de":
            lemma_index_file = (
                "U:\\voothi\\20241223170748-token-extraction\\de-default.csv"
            )
        elif language == "en":
            lemma_index_file = (
                "U:\\voothi\\20241223170748-token-extraction\\en-default.csv"
            )

    # Add timestamp to the output file name if requested
    if timestamp:
        # Extract the directory and filename from the output path
        output_dir = os.path.dirname(output_file)
        output_filename = os.path.basename(output_file)
        # Prepend timestamp to the filename
        timestamp_str = datetime.now().strftime("%Y%m%d%H%M%S")
        new_output_filename = f"{timestamp_str}-{output_filename}"
        output_file = os.path.join(output_dir, new_output_filename)

    # Load spaCy model based on language
    language_model_map = {"de": "de_core_news_lg", "en": "en_core_web_lg"}
    nlp = spacy.load(language_model_map[language])

    # Load lemma index if simple list is requested
    lemma_index = {}
    if include_simple_list:
        lemma_index = load_lemma_index(lemma_index_file)

    # Read input files
    try:
        with open(text1, "r", encoding="utf-8") as f:
            text1_lines = [line.rstrip("\n") for line in f]
        with open(text2, "r", encoding="utf-8") as f:
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

    context_size = sentence_context_size
    min_length = min(len(text1_lines), len(text2_lines))

    # Process lines and write output
    try:
        with open(output_file, "w", newline="", encoding="utf-8") as out_file:
            tsv_writer = csv.writer(out_file, delimiter="\t")
            for i in range(min_length):
                # Process German text
                l1_sentence = text1_lines[i]
                l1_left = text1_lines[max(0, i - context_size) : i]
                l1_right = text1_lines[i + 1 : i + 1 + context_size]

                # Process English text
                l2_sentence = text2_lines[i]
                l2_left = text2_lines[max(0, i - context_size) : i]
                l2_right = text2_lines[i + 1 : i + 1 + context_size]

                # Join context sentences
                l1_left_context = " ".join(line.strip() for line in l1_left)
                l1_right_context = " ".join(line.strip() for line in l1_right)
                l2_left_context = " ".join(line.strip() for line in l2_left)
                l2_right_context = " ".join(line.strip() for line in l2_right)

                # Process lemmas if simple list is requested
                simple_list_entry = ""
                if include_simple_list:
                    lemmas = process_sentence_lemmas(l1_sentence, lemma_index, nlp)
                    simple_list_entry = "\n".join(
                        lemmas
                    )  # Newline-separated without quotes

                # Format TSV line
                if language == "de":
                    tsv_line = (
                        "\t".join(
                            [
                                l1_sentence,
                                "",
                                "",
                                "",
                                "",
                                l1_left_context,
                                l1_sentence,
                                l1_right_context,
                                l2_left_context,
                                l2_sentence,
                                l2_right_context,
                                simple_list_entry,
                                l1_sentence,
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

                if language == "en":
                    tsv_line = (
                        "\t".join(
                            [
                                l1_sentence,
                                "",
                                "",
                                "",
                                "",
                                l1_left_context,
                                l1_sentence,
                                l1_right_context,
                                l2_left_context,
                                l2_sentence,
                                l2_right_context,
                                simple_list_entry,
                                l1_sentence,
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


def main():
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
        "--language",
        type=str,
        default="de",
        choices=["de", "en"],
        help="Language for processing (default: de)",
    )
    parser.add_argument(
        "--lemma-index-file",
        type=str,
        default="",
        help="Path to the lemma index CSV file",
    )
    parser.add_argument("--text", type=str, help="Input text to process")  # Добавлено
    parser.add_argument("--text1", type=str, help="Path to input text file to process")
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="STDOUT: Enable detailed output in console with sentence and context",
    )
    parser.add_argument(
        "--two-column-output",
        action="store_true",
        help="STDOUT: Output tokens in two columns: token and original form",
    )
    parser.add_argument(
        "--html", action="store_true", help="STDOUT: Output tokens in an HTML table"
    )
    parser.add_argument(
        "--sentence-context-size",
        type=int,
        default=1,
        help="CSV: Number of sentences to include before and after the target sentence (default: 1)",
    )
    parser.add_argument(
        "--output",
        type=str,
        required=False,
        help="CSV: Output TSV file path for saving results",
    )
    parser.add_argument(
        "--timestamp",
        action="store_true",
        help="CSV: Prepend timestamp to the output file name",
    )
    parser.add_argument(
        "--two-column-output-to-file",
        action="store_true",
        help="CSV: Include original forms in the TSV output file when writing to file",
    )
    parser.add_argument(
        "--include-simple-list",
        action="store_true",
        help="CSV: Include a simple list of tokens in the last column of the output file",
    )
    parser.add_argument(
        "--original-form-in-simple-list",
        action="store_true",
        help="CSV: Include original forms in the simple list entry in the TSV file",
    )
    parser.add_argument(
        "--text2",
        type=str,
        help="Path to the second text file (German/English translations)",
    )

    args = parser.parse_args()

    # Load the appropriate spaCy model based on the language
    global nlp
    if args.language == "de":
        nlp = spacy.load("de_core_news_lg")
    else:
        nlp = spacy.load("en_core_web_lg")

    if args.type == "token":
        # Determine input text
        if args.text and args.text1:
            print("Error: Both --text and --text1 cannot be specified simultaneously.")
            exit(1)
        elif args.text:
            input_text = args.text
        elif args.text1:
            input_text = read_input_text(args.text1)
        else:
            print("Error: Either --text or --text1 must be specified.")
            exit(1)

        # Process the text
        process_text(
            input_text,
            args.output,
            args.sentence_context_size,
            args.detailed,
            args.include_simple_list,
            args.lemma_index_file,
            args.two_column_output,
            args.html,
            args.timestamp,
            args.original_form_in_simple_list,
            args.two_column_output_to_file,
            args.language,
            args.text2,  # Добавлено для второго текста
        )
    elif args.type == "sentence":
        if not args.text1 or not args.text2:
            print(
                "Error: Both --text1 and --text2 must be specified for sentence mode."
            )
            exit(1)

        # Process sentences
        process_sentences(
            args.text1,
            args.text2,
            args.output,
            args.sentence_context_size,
            args.include_simple_list,
            args.timestamp,
            args.lemma_index_file,
            args.language,
        )
    else:
        print("Error: Invalid --type specified.")
        exit(1)


if __name__ == "__main__":
    main()
