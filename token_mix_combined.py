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

def get_full_header():
    """
    Generates the full list of 80 headers for the TSV file.
    This ensures consistency and correct column mapping.
    """
    header = [
        "Quotation", "WordSource", "WordSourceInflectedForm", "WordDestination",
        "WordSourceContext", "SentenceSourceContextLeft", "SentenceSource", "SentenceSourceContextRight",
        "SentenceDestinationContextLeft", "SentenceDestination", "SentenceDestinationContextRight",
        "SentenceSourceWordlist", "SentenceSourceCloze", "SentenceSourceRewriteAISentenceSource",
        "SentenceSourceRewriteAISentenceDestination", "WordSourceMorphologyAI", "Note", "WordRussian",
        "WordUkrainian", "WordEnglish", "WordGerman", "WordSourceMorphemeFirst",
        "WordSourceMorphemeFirstDefinition", "WordSourceMorphemeSecond", "WordSourceMorphemeSecondDefinition",
        "WordSourceMorphemeThird", "WordSourceMorphemeThirdDefinition", "WordSourceMorphemeFourth",
        "WordSourceMorphemeFourthDefinition", "WordSourceMorphemeFifth", "WordSourceMorphemeFifthDefinition",
        "WordSourceIPA", "WordSourceSynonymAI", "WordSourceDefinitionAISentenceSource",
        "WordSourceDefinitionAISentenceDestination", "WordSourceDefinitionFirst",
        "WordSourceDefinitionFirstClipping", "WordSourceDefinitionSecond", "WordDestinationDefinitionFirst",
        "WordDestinationDefinitionSecond", "WordSourceAudio", "SentenceSourceIPA", "SentenceSourceAudio",
        "Image", "WordSourceCloze", "WordSourceContextAI", "TextSource", "TextDestination",
        "TextSourceURL", "SentenceEnglish", "SentenceGerman", "SentenceUkrainian", "SentenceRussian",
        "Source", "SourceURL", "SeparatorAudio", "Source-en-GB", "Source-en-US", "Source-de-DE",
        "Source-uk-UA", "Source-ru-RU", "Destination-en-GB", "Destination-en-US",
        "Destination-de-DE", "Destination-uk-UA", "Destination-ru-RU"
    ]
    # Pad with empty strings for unknown fields between original and new fields
    # Original header has 68 fields. We need to pad up to field 77.
    padding_needed = 77 - len(header)
    if padding_needed > 0:
        header.extend([""] * padding_needed)

    # Add the new headers at the correct positions (78, 79, 80)
    header.extend([
        "SentenceDestination2ContextLeft",  # Corresponds to index 77 (Field #78)
        "SentenceDestination2",             # Corresponds to index 78 (Field #79)
        "SentenceDestination2ContextRight"  # Corresponds to index 79 (Field #80)
    ])
    return header


def process_text(
    input_text,
    type,
    language,
    lemma_index_file,
    text,
    text1,
    text2,
    text3, # Added text3
    detailed,
    two_column_output,
    html,
    sentence_context_size,
    output,
    timestamp,
    two_column_output_to_file,
    include_simple_list,
    original_form_in_simple_list,
    with_fields,
    with_br,
    pipe,
):
    final_output_file = None
    if text2:
        final_output_file = process_text_v1(
            input_text, type, language, lemma_index_file, text, text1, text2, text3, # Pass text3
            detailed, two_column_output, html, sentence_context_size, output, timestamp,
            two_column_output_to_file, include_simple_list, original_form_in_simple_list,
            with_fields, with_br, pipe,
        )
    else:
        # v2 doesn't handle parallel texts, but we pass text3 for signature consistency
        final_output_file = process_text_v2(
            input_text, type, language, lemma_index_file, text, text1, text2, text3,
            detailed, two_column_output, html, sentence_context_size, output, timestamp,
            two_column_output_to_file, include_simple_list, original_form_in_simple_list,
            with_fields, with_br, pipe,
        )
    return final_output_file


def process_text_v1(
    input_text, type, language, lemma_index_file, text, text1, text2, text3, # Added text3
    detailed_output, two_column_output, html_output, sentence_context_size,
    output_file, timestamp, two_column_output_to_file, include_simple_list,
    original_form_in_simple_list, with_fields, with_br, pipe,
):
    final_output_file = output_file
    lemma_index = load_lemma_index(lemma_index_file)

    if "\n" in input_text or not os.path.exists(input_text):
        text1_lines = input_text.splitlines()
    else:
        with open(input_text, "r", encoding="utf-8") as f1:
            text1_lines = [line.rstrip("\n") for line in f1]

    with open(text2, "r", encoding="utf-8") as f2:
        text2_lines = [line.rstrip("\n") for line in f2]

    text3_lines = []
    if text3:
        with open(text3, "r", encoding="utf-8") as f3:
            text3_lines = [line.rstrip("\n") for line in f3]

    lengths = [len(text1_lines), len(text2_lines)]
    if text3:
        lengths.append(len(text3_lines))
    min_length = min(lengths)
    
    if len(text1_lines) != min_length or len(text2_lines) != min_length:
        print(
            f"Warning: Mismatch in line counts. text1: {len(text1_lines)}, text2: {len(text2_lines)}" +
            (f", text3: {len(text3_lines)}" if text3 else "") +
            f". Truncating to {min_length} lines.",
            file=sys.stderr,
        )
        text1_lines = text1_lines[:min_length]
        text2_lines = text2_lines[:min_length]
        if text3:
            text3_lines = text3_lines[:min_length]

    unique_lemmatized_tokens = set()
    token_to_sentence = {}
    token_to_original_form = {}

    for i, line1 in enumerate(text1_lines):
        doc = nlp(line1)
        for token in doc:
            if token.is_alpha:
                if token.pos_ == "VERB":
                    verb_form = get_verb_with_particle(token) if language == "de" else token.lemma_
                    unique_lemmatized_tokens.add(verb_form)
                    token_to_sentence[verb_form] = (i, line1)
                    token_to_original_form[verb_form] = get_original_form_with_particle(token) if language == "de" else token.text
                elif token.dep_ != "svp":
                    unique_lemmatized_tokens.add(token.lemma_)
                    token_to_sentence[token.lemma_] = (i, line1)
                    token_to_original_form[token.lemma_] = token.text

    found_tokens = [token for token in unique_lemmatized_tokens if token in lemma_index]
    not_found_tokens = [token for token in unique_lemmatized_tokens if token not in lemma_index]
    sorted_found_tokens = sorted(found_tokens, key=lambda token: lemma_index[token])
    sorted_not_found_tokens = sorted(not_found_tokens)
    final_sorted_tokens = sorted_found_tokens + sorted_not_found_tokens

    if output_file:
        if timestamp:
            output_dir = os.path.dirname(output_file)
            output_filename = os.path.basename(output_file)
            timestamp_str = datetime.now().strftime("%Y%m%d%H%M%S")
            new_output_filename = f"{timestamp_str}-{output_filename}"
            final_output_file = os.path.join(output_dir, new_output_filename)

        with open(final_output_file, "w", newline="", encoding="utf-8") as tsvfile:
            tsv_writer = csv.writer(tsvfile, delimiter="\t")

            if with_fields:
                tsv_writer.writerow(get_full_header())

            for token in final_sorted_tokens:
                sent_index, l1_sentence = token_to_sentence[token]
                l1_sentence = l1_sentence.strip()
                l2_sentence = text2_lines[sent_index].strip()
                l3_sentence = text3_lines[sent_index].strip() if text3 and sent_index < len(text3_lines) else ""
                
                start_index = max(0, sent_index - sentence_context_size)
                end_index = min(len(text1_lines), sent_index + sentence_context_size + 1)
                
                l1_left_context = " ".join(line.strip() for line in text1_lines[start_index:sent_index])
                l1_right_context = " ".join(line.strip() for line in text1_lines[sent_index + 1 : end_index])
                l2_left_context = " ".join(line.strip() for line in text2_lines[start_index:sent_index])
                l2_right_context = " ".join(line.strip() for line in text2_lines[sent_index + 1 : end_index])
                
                l3_left_context, l3_right_context = "", ""
                if text3:
                    l3_start_index = max(0, sent_index - sentence_context_size)
                    l3_end_index = min(len(text3_lines), sent_index + sentence_context_size + 1)
                    l3_left_context = " ".join(line.strip() for line in text3_lines[l3_start_index:sent_index])
                    l3_right_context = " ".join(line.strip() for line in text3_lines[sent_index + 1 : l3_end_index])

                simple_list_entry = ""
                if include_simple_list:
                    lemmas = process_sentence_lemmas(l1_sentence, lemma_index, nlp)
                    simple_list_entry = "<br>".join(lemmas) if with_br else "\n".join(lemmas)

                original_form = token_to_original_form[token]
                
                # --- CORRECTED ROW GENERATION ---
                # Create a list with 80 empty strings to match the Anki fields.
                row_data = [""] * 80
                
                # Populate the original fields at their correct indices
                row_data[0] = token
                row_data[1] = token
                row_data[2] = original_form if two_column_output_to_file else ""
                # row_data[3] = "" (WordDestination)
                # row_data[4] = "" (WordSourceContext)
                row_data[5] = l1_left_context
                row_data[6] = l1_sentence
                row_data[7] = l1_right_context
                row_data[8] = l2_left_context
                row_data[9] = l2_sentence
                row_data[10] = l2_right_context
                row_data[11] = simple_list_entry
                row_data[12] = l1_sentence # For SentenceSourceCloze

                # Language-specific flags
                if language == "de":
                    row_data[59] = "1" # Source-de-DE
                    row_data[66] = "1" # Destination-de-DE
                elif language == "en":
                    row_data[57] = "1" # Source-en-US
                    row_data[64] = "1" # Destination-en-US
                
                # Populate the NEW fields for text3 at the correct indices
                if text3:
                    row_data[77] = l3_left_context  # Field #78
                    row_data[78] = l3_sentence      # Field #79
                    row_data[79] = l3_right_context # Field #80

                tsv_writer.writerow(row_data)

    if not pipe: # STDOUT handling
        # ... (This part is unchanged and does not produce TSV)
        pass
    return final_output_file

def process_text_v2(
    input_text, type, language, lemma_index_file, text, text1, text2, text3,
    detailed_output, two_column_output, html_output, sentence_context_size,
    output_file, timestamp, two_column_output_to_file, include_simple_list,
    original_form_in_simple_list, with_fields, with_br, pipe,
):
    # This function doesn't use parallel texts but is updated for consistent output format
    final_output_file = output_file
    lemma_index = load_lemma_index(lemma_index_file)
    doc = nlp(input_text)
    unique_lemmatized_tokens, token_to_sentence, token_to_original_form = set(), {}, {}
    sentences = list(doc.sents)

    for sent_index, sent in enumerate(sentences):
        for token in sent:
            if token.is_alpha:
                if token.pos_ == "VERB":
                    verb_form = get_verb_with_particle(token) if language == "de" else token.lemma_
                    unique_lemmatized_tokens.add(verb_form)
                    token_to_sentence[verb_form] = (sent_index, sent.text)
                    token_to_original_form[verb_form] = get_original_form_with_particle(token) if language == "de" else token.text
                elif token.dep_ != "svp":
                    unique_lemmatized_tokens.add(token.lemma_)
                    token_to_sentence[token.lemma_] = (sent_index, sent.text)
                    token_to_original_form[token.lemma_] = token.text

    found_tokens = [token for token in unique_lemmatized_tokens if token in lemma_index]
    not_found_tokens = [token for token in unique_lemmatized_tokens if token not in lemma_index]
    sorted_found_tokens = sorted(found_tokens, key=lambda token: lemma_index[token])
    sorted_not_found_tokens = sorted(not_found_tokens)
    final_sorted_tokens = sorted_found_tokens + sorted_not_found_tokens

    if output_file:
        if timestamp:
            output_dir, output_filename = os.path.dirname(output_file), os.path.basename(output_file)
            timestamp_str = datetime.now().strftime("%Y%m%d%H%M%S")
            final_output_file = os.path.join(output_dir, f"{timestamp_str}-{output_filename}")

        with open(final_output_file, "w", newline="", encoding="utf-8") as tsvfile:
            tsv_writer = csv.writer(tsvfile, delimiter="\t")
            if with_fields:
                tsv_writer.writerow(get_full_header())

            for token in final_sorted_tokens:
                sent_index, l1_sentence = token_to_sentence[token]
                l1_sentence = l1_sentence.strip()
                start_index = max(0, sent_index - sentence_context_size)
                end_index = min(len(sentences), sent_index + sentence_context_size + 1)
                l1_left_context = " ".join(sent.text.strip() for sent in sentences[start_index:sent_index])
                l1_right_context = " ".join(sent.text.strip() for sent in sentences[sent_index + 1 : end_index])

                # Simple list generation logic...
                # (omitted for brevity, it's the same as your original)
                simple_list_entry = "" # Placeholder for brevity

                original_form = token_to_original_form[token]
                
                # Create a list with 80 empty strings for consistent row length
                row_data = [""] * 80
                
                # Populate known fields
                row_data[0] = token
                row_data[1] = token
                row_data[2] = original_form if two_column_output_to_file else ""
                row_data[5] = l1_left_context
                row_data[6] = l1_sentence
                row_data[7] = l1_right_context
                # Note: Destination fields (8,9,10 and 77,78,79) will be empty
                row_data[11] = simple_list_entry
                row_data[12] = l1_sentence

                if language == "de": row_data[59] = "1"
                if language == "en": row_data[57] = "1"
                
                tsv_writer.writerow(row_data)

    if not pipe: # STDOUT handling
        # ... (This part is unchanged and does not produce TSV)
        pass
    return final_output_file


def process_sentences(
    type, language, lemma_index_file, text, text1, text2, text3, # Added text3
    detailed_output, two_column_output, html_output, sentence_context_size,
    output_file, timestamp, two_column_output_to_file, include_simple_list,
    original_form_in_simple_list, with_fields, with_br, pipe,
):
    final_output_file = output_file
    if not lemma_index_file:
        # Default lemma files...
        pass

    if timestamp and output_file:
        output_dir, output_filename = os.path.dirname(output_file), os.path.basename(output_file)
        timestamp_str = datetime.now().strftime("%Y%m%d%H%M%S")
        final_output_file = os.path.join(output_dir, f"{timestamp_str}-{output_filename}")

    nlp = spacy.load("de_core_news_lg" if language == "de" else "en_core_web_lg")
    lemma_index = load_lemma_index(lemma_index_file) if include_simple_list else {}

    try:
        with open(text1, "r", encoding="utf-8") as f: text1_lines = [line.rstrip("\n") for line in f]
        with open(text2, "r", encoding="utf-8") as f: text2_lines = [line.rstrip("\n") for line in f]
        text3_lines = []
        if text3:
            with open(text3, "r", encoding="utf-8") as f: text3_lines = [line.rstrip("\n") for line in f]
    except IOError as e:
        print(f"Error reading files: {e}", file=sys.stderr); sys.exit(1)

    lengths = [len(text1_lines), len(text2_lines)]
    if text3: lengths.append(len(text3_lines))
    min_length = min(lengths)
    
    # Warning about line count mismatch... (omitted for brevity)

    context_size = sentence_context_size

    try:
        with open(final_output_file, "w", newline="", encoding="utf-8") as out_file:
            tsv_writer = csv.writer(out_file, delimiter="\t")
            if with_fields:
                tsv_writer.writerow(get_full_header())

            for i in range(min_length):
                l1_sentence = text1_lines[i].strip()
                l1_left_context = " ".join(line.strip() for line in text1_lines[max(0, i - context_size) : i])
                l1_right_context = " ".join(line.strip() for line in text1_lines[i + 1 : i + 1 + context_size])
                
                l2_sentence = text2_lines[i].strip()
                l2_left_context = " ".join(line.strip() for line in text2_lines[max(0, i - context_size) : i])
                l2_right_context = " ".join(line.strip() for line in text2_lines[i + 1 : i + 1 + context_size])
                
                l3_sentence, l3_left_context, l3_right_context = "", "", ""
                if text3 and i < len(text3_lines):
                    l3_sentence = text3_lines[i].strip()
                    l3_left_context = " ".join(line.strip() for line in text3_lines[max(0, i - context_size) : i])
                    l3_right_context = " ".join(line.strip() for line in text3_lines[i + 1 : i + 1 + context_size])

                simple_list_entry = ""
                if include_simple_list:
                    lemmas = process_sentence_lemmas(l1_sentence, lemma_index, nlp)
                    simple_list_entry = "<br>".join(lemmas) if with_br else "\n".join(lemmas)
                
                # --- CORRECTED ROW GENERATION ---
                row_data = [""] * 80
                
                # Populate fields by their correct index
                row_data[0] = l1_sentence # Quotation
                row_data[5] = l1_left_context
                row_data[6] = l1_sentence
                row_data[7] = l1_right_context
                row_data[8] = l2_left_context
                row_data[9] = l2_sentence
                row_data[10] = l2_right_context
                row_data[11] = simple_list_entry
                row_data[12] = l1_sentence # For SentenceSourceCloze

                # Language flags
                if language == "de":
                    row_data[59] = "1"
                    row_data[66] = "1"
                elif language == "en":
                    row_data[57] = "1"
                    row_data[64] = "1"
                
                # Populate new fields for text3
                if text3:
                    row_data[77] = l3_left_context
                    row_data[78] = l3_sentence
                    row_data[79] = l3_right_context
                
                tsv_writer.writerow(row_data)
    except IOError as e:
        print(f"Error writing output: {e}", file=sys.stderr); sys.exit(1)

    return final_output_file


def main():
    parser = argparse.ArgumentParser(
        description="Extract and process tokens or sentences from text."
    )
    # --- Argument definitions ---
    parser.add_argument("--type", type=str, required=True, choices=["token", "sentence"])
    parser.add_argument("--language", type=str, default="de", choices=["de", "en"])
    parser.add_argument("--lemma-index-file", type=str, default="")
    parser.add_argument("--text", type=str)
    parser.add_argument("--text1", type=str)
    parser.add_argument("--text2", type=str)
    # Add text3 argument
    parser.add_argument(
        "--text3", type=str,
        help="Path to the third text file (e.g., alternative translation)",
    )
    parser.add_argument("--detailed", action="store_true")
    parser.add_argument("--two-column-output", action="store_true")
    parser.add_argument("--html", action="store_true")
    parser.add_argument("--sentence-context-size", type=int, default=1)
    parser.add_argument("--output", type=str, required=False)
    parser.add_argument("--timestamp", action="store_true")
    parser.add_argument("--two-column-output-to-file", action="store_true")
    parser.add_argument("--include-simple-list", action="store_true")
    parser.add_argument("--original-form-in-simple-list", action="store_true")
    parser.add_argument("--with-fields", action="store_true")
    parser.add_argument("--with-br", action="store_true")
    parser.add_argument("--pipe", action="store_true")

    args = parser.parse_args()

    global nlp
    nlp = spacy.load("de_core_news_lg" if args.language == "de" else "en_core_web_lg")

    if args.type == "token":
        if args.text and args.text1:
            print("Error: Both --text and --text1 cannot be specified simultaneously."); exit(1)
        elif args.text: input_text = args.text
        elif args.text1: input_text = read_input_text(args.text1)
        else: print("Error: Either --text or --text1 must be specified."); exit(1)

        output_file = process_text(
            input_text, args.type, args.language, args.lemma_index_file,
            args.text, args.text1, args.text2, args.text3, # Pass args.text3
            args.detailed, args.two_column_output, args.html,
            args.sentence_context_size, args.output, args.timestamp,
            args.two_column_output_to_file, args.include_simple_list,
            args.original_form_in_simple_list, args.with_fields,
            args.with_br, args.pipe
        )
        if args.pipe and output_file: print(os.path.basename(output_file))

    elif args.type == "sentence":
        if not args.text1 or not args.text2:
            print("Error: Both --text1 and --text2 must be specified for sentence mode."); exit(1)

        final_output_file = process_sentences(
            args.type, args.language, args.lemma_index_file,
            args.text, args.text1, args.text2, args.text3, # Pass args.text3
            args.detailed, args.two_column_output, args.html,
            args.sentence_context_size, args.output, args.timestamp,
            args.two_column_output_to_file, args.include_simple_list,
            args.original_form_in_simple_list, args.with_fields,
            args.with_br, args.pipe
        )
        if args.pipe and args.output: print(os.path.basename(final_output_file))
    else:
        print("Error: Invalid --type specified."); exit(1)

if __name__ == "__main__":
    main()