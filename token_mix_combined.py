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
            input_text,
            type,
            language,
            lemma_index_file,
            text,
            text1,
            text2,
            text3, # Pass text3
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
        )
    else:
        final_output_file = process_text_v2(
            input_text,
            type,
            language,
            lemma_index_file,
            text,
            text1,
            text2,
            text3, # Pass text3
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
        )
    return final_output_file


def process_text_v1(
    input_text,
    type,
    language,
    lemma_index_file,
    text,
    text1,
    text2,
    text3, # Added text3
    detailed_output,
    two_column_output,
    html_output,
    sentence_context_size,
    output_file,
    timestamp,
    two_column_output_to_file,
    include_simple_list,
    original_form_in_simple_list,
    with_fields,
    with_br,
    pipe,
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

    # Read text3 if provided
    text3_lines = []
    if text3:
        with open(text3, "r", encoding="utf-8") as f3:
            text3_lines = [line.rstrip("\n") for line in f3]

    # Check for mismatch in line counts and truncate to the minimum length
    lengths = [len(text1_lines), len(text2_lines)]
    if text3:
        lengths.append(len(text3_lines))
    
    min_length = min(lengths)
    
    if len(text1_lines) != len(text2_lines) or (text3 and len(text1_lines) != len(text3_lines)):
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
    not_found_tokens = [
        token for token in unique_lemmatized_tokens if token not in lemma_index
    ]

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
                header = [
                    "Quotation", "WordSource", "WordSourceInflectedForm", "WordDestination",
                    "WordSourceContext", "SentenceSourceContextLeft", "SentenceSource", "SentenceSourceContextRight",
                    "SentenceDestinationContextLeft", "SentenceDestination", "SentenceDestinationContextRight",
                    "SentenceDestination2ContextLeft", "SentenceDestination2", "SentenceDestination2ContextRight", # New fields for text3
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
                tsv_writer.writerow(header)

            for token in final_sorted_tokens:
                sent_index, l1_sentence = token_to_sentence[token]
                l1_sentence = l1_sentence.strip()
                l2_sentence = text2_lines[sent_index].strip()
                
                # Get sentence and context for text3
                l3_sentence = text3_lines[sent_index].strip() if text3 and sent_index < len(text3_lines) else ""
                
                start_index = max(0, sent_index - sentence_context_size)
                end_index = min(len(text1_lines), sent_index + sentence_context_size + 1)
                
                l1_left_context = " ".join(line.strip() for line in text1_lines[start_index:sent_index])
                l1_right_context = " ".join(line.strip() for line in text1_lines[sent_index + 1 : end_index])
                
                l2_left_context = " ".join(line.strip() for line in text2_lines[start_index:sent_index])
                l2_right_context = " ".join(line.strip() for line in text2_lines[sent_index + 1 : end_index])

                # Get context for text3
                l3_left_context = ""
                l3_right_context = ""
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
                
                row_data = [
                    token,
                    token,
                    original_form if two_column_output_to_file else "",
                    "",
                    "",
                    l1_left_context, l1_sentence, l1_right_context,
                    l2_left_context, l2_sentence, l2_right_context,
                    l3_left_context, l3_sentence, l3_right_context, # Add text3 data
                    simple_list_entry,
                    l1_sentence,
                ]
                
                # Fill the rest of the row with placeholders
                num_remaining_fields = len(header) - len(row_data) if with_fields else 68 - len(row_data)
                row_data.extend([""] * num_remaining_fields)

                # Overwrite specific language fields
                if language == "de":
                    row_data[59] = "1" # Source-de-DE
                    row_data[66] = "1" # Destination-de-DE
                elif language == "en":
                    row_data[57] = "1" # Source-en-US (example)
                    row_data[64] = "1" # Destination-en-US (example)

                tsv_writer.writerow(row_data)


    if not pipe:
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
                sent_index, l1_sentence = token_to_sentence[token]
                l1_sentence = l1_sentence.strip()
                start_index = max(0, sent_index - sentence_context_size)
                end_index = min(
                    len(text1_lines), sent_index + sentence_context_size + 1
                )
                l1_left_context = " ".join(
                    line.strip() for line in text1_lines[start_index:sent_index]
                )
                l1_right_context = " ".join(
                    line.strip() for line in text1_lines[sent_index + 1 : end_index]
                )
                print(token)
                if l1_left_context: print(l1_left_context)
                print(l1_sentence)
                if l1_right_context: print(l1_right_context)
                print()

    return final_output_file


def process_text_v2(
    input_text,
    type,
    language,
    lemma_index_file,
    text,
    text1,
    text2,
    text3, # Added text3 for signature consistency
    detailed_output,
    two_column_output,
    html_output,
    sentence_context_size,
    output_file,
    timestamp,
    two_column_output_to_file,
    include_simple_list,
    original_form_in_simple_list,
    with_fields,
    with_br,
    pipe,
):
    # This function remains largely the same as it doesn't handle text2 or text3
    final_output_file = output_file
    lemma_index = load_lemma_index(lemma_index_file)
    doc = nlp(input_text)
    unique_lemmatized_tokens = set()
    token_to_sentence = {}
    token_to_original_form = {}
    sentences = list(doc.sents)

    for sent_index, sent in enumerate(sentences):
        for token in sent:
            if token.is_alpha:
                if token.pos_ == "VERB":
                    if language == "de":
                        verb_form = get_verb_with_particle(token)
                    else:
                        verb_form = token.lemma_
                    unique_lemmatized_tokens.add(verb_form)
                    token_to_sentence[verb_form] = (sent_index, sent.text)
                    if language == "de":
                        token_to_original_form[verb_form] = (
                            get_original_form_with_particle(token)
                        )
                    else:
                        token_to_original_form[verb_form] = token.text
                elif (
                    token.dep_ != "svp"
                ):
                    unique_lemmatized_tokens.add(token.lemma_)
                    token_to_sentence[token.lemma_] = (sent_index, sent.text)
                    token_to_original_form[token.lemma_] = token.text

    found_tokens = [token for token in unique_lemmatized_tokens if token in lemma_index]
    not_found_tokens = [
        token for token in unique_lemmatized_tokens if token not in lemma_index
    ]

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
                header = [
                    "Quotation", "WordSource", "WordSourceInflectedForm", "WordDestination",
                    "WordSourceContext", "SentenceSourceContextLeft", "SentenceSource", "SentenceSourceContextRight",
                    "SentenceDestinationContextLeft", "SentenceDestination", "SentenceDestinationContextRight",
                    # Added for consistency, will be empty
                    "SentenceDestination2ContextLeft", "SentenceDestination2", "SentenceDestination2ContextRight", 
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
                tsv_writer.writerow(header)

            for token in final_sorted_tokens:
                sent_index, l1_sentence = token_to_sentence[token]
                l1_sentence = l1_sentence.strip()
                start_index = max(0, sent_index - sentence_context_size)
                end_index = min(len(sentences), sent_index + sentence_context_size + 1)
                l1_left_context = " ".join(
                    sent.text.strip() for sent in sentences[start_index:sent_index]
                )
                l1_right_context = " ".join(
                    sent.text.strip() for sent in sentences[sent_index + 1 : end_index]
                )

                sent_doc = nlp(l1_sentence)
                sentence_tokens_set = {
                    (
                        get_verb_with_particle(token)
                        if token.pos_ == "VERB" and language == "de"
                        else token.lemma_
                    )
                    for token in sent_doc
                    if token.is_alpha and token.dep_ != "svp"
                }
                sentence_tokens_sorted = sorted(
                    sentence_tokens_set, key=lambda x: lemma_index.get(x, float("inf"))
                )

                simple_list_entry = ""
                if include_simple_list:
                    if original_form_in_simple_list:
                        entries = [
                            f"{stoken}<br>{token_to_original_form.get(stoken, '')}" if with_br
                            else f"{stoken}\t{token_to_original_form.get(stoken, '')}"
                            for stoken in sentence_tokens_sorted
                        ]
                        simple_list_entry = "<br>".join(entries) if with_br else "\n".join(entries)
                    else:
                        simple_list_entry = "<br>".join(sentence_tokens_sorted) if with_br else "\n".join(sentence_tokens_sorted)

                original_form = token_to_original_form[token]
                
                row_data = [
                    token,
                    token,
                    original_form if two_column_output_to_file else "",
                    "", "",
                    l1_left_context, l1_sentence, l1_right_context,
                    "", "", "", # Placeholders for text2
                    "", "", "", # Placeholders for text3
                    simple_list_entry,
                    l1_sentence,
                ]
                num_remaining_fields = len(header) - len(row_data) if with_fields else 68 - len(row_data)
                row_data.extend([""] * num_remaining_fields)

                if language == "de":
                    row_data[59] = "1"
                    row_data[66] = "1"
                elif language == "en":
                    row_data[57] = "1"
                    row_data[64] = "1"
                
                tsv_writer.writerow(row_data)


    if not pipe:
        if html_output:
            print("<table>")
            for token in final_sorted_tokens:
                print(f"<tr><td>{token}</td><td>{token_to_original_form[token]}</td></tr>")
            print("</table>")
        elif two_column_output:
            for token in final_sorted_tokens:
                print(f"{token}\t{token_to_original_form[token]}")
        else:
            for token in final_sorted_tokens:
                print(token)
            print()

        if detailed_output:
            for token in final_sorted_tokens:
                sent_index, l1_sentence = token_to_sentence[token]
                start_index = max(0, sent_index - sentence_context_size)
                end_index = min(len(sentences), sent_index + sentence_context_size + 1)
                l1_left_context = " ".join(
                    sent.text.strip() for sent in sentences[start_index:sent_index]
                )
                l1_right_context = " ".join(
                    sent.text.strip() for sent in sentences[sent_index + 1 : end_index]
                )
                print(token)
                if l1_left_context: print(l1_left_context)
                print(l1_sentence)
                if l1_right_context: print(l1_right_context)
                print()

    return final_output_file


def process_sentences(
    type,
    language,
    lemma_index_file,
    text,
    text1,
    text2,
    text3, # Added text3
    detailed_output,
    two_column_output,
    html_output,
    sentence_context_size,
    output_file,
    timestamp,
    two_column_output_to_file,
    include_simple_list,
    original_form_in_simple_list,
    with_fields,
    with_br,
    pipe,
):
    final_output_file = output_file
    if not lemma_index_file:
        if language == "de":
            lemma_index_file = "U:\\voothi\\20241223170748-token-extraction\\de-default.csv"
        elif language == "en":
            lemma_index_file = "U:\\voothi\\20241223170748-token-extraction\\en-default.csv"

    if timestamp and output_file:
        output_dir = os.path.dirname(output_file)
        output_filename = os.path.basename(output_file)
        timestamp_str = datetime.now().strftime("%Y%m%d%H%M%S")
        new_output_filename = f"{timestamp_str}-{output_filename}"
        final_output_file = os.path.join(output_dir, new_output_filename)

    language_model_map = {"de": "de_core_news_lg", "en": "en_core_web_lg"}
    nlp = spacy.load(language_model_map[language])

    lemma_index = {}
    if include_simple_list:
        lemma_index = load_lemma_index(lemma_index_file)

    try:
        with open(text1, "r", encoding="utf-8") as f:
            text1_lines = [line.rstrip("\n") for line in f]
        with open(text2, "r", encoding="utf-8") as f:
            text2_lines = [line.rstrip("\n") for line in f]
        # Read text3 lines if provided
        text3_lines = []
        if text3:
            with open(text3, "r", encoding="utf-8") as f:
                text3_lines = [line.rstrip("\n") for line in f]
    except IOError as e:
        print(f"Error reading files: {e}", file=sys.stderr)
        sys.exit(1)

    # Validate line counts and find min length
    lengths = [len(text1_lines), len(text2_lines)]
    if text3:
        lengths.append(len(text3_lines))
    min_length = min(lengths)
    
    if len(text1_lines) != len(text2_lines) or (text3 and len(text1_lines) != len(text3_lines)):
        print(
            f"Warning: Line count mismatch. text1: {len(text1_lines)}, text2: {len(text2_lines)}" +
            (f", text3: {len(text3_lines)}" if text3 else "") +
            f". Processing {min_length} lines.",
            file=sys.stderr
        )


    context_size = sentence_context_size

    try:
        with open(final_output_file, "w", newline="", encoding="utf-8") as out_file:
            tsv_writer = csv.writer(out_file, delimiter="\t")
            header = []
            if with_fields:
                header = [
                    "Quotation", "WordSource", "WordSourceInflectedForm", "WordDestination",
                    "WordSourceContext", "SentenceSourceContextLeft", "SentenceSource", "SentenceSourceContextRight",
                    "SentenceDestinationContextLeft", "SentenceDestination", "SentenceDestinationContextRight",
                    "SentenceDestination2ContextLeft", "SentenceDestination2", "SentenceDestination2ContextRight", # New fields
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
                tsv_writer.writerow(header)

            for i in range(min_length):
                l1_sentence = text1_lines[i].strip()
                l1_left = text1_lines[max(0, i - context_size) : i]
                l1_right = text1_lines[i + 1 : i + 1 + context_size]
                l1_left_context = " ".join(line.strip() for line in l1_left)
                l1_right_context = " ".join(line.strip() for line in l1_right)

                l2_sentence = text2_lines[i].strip()
                l2_left = text2_lines[max(0, i - context_size) : i]
                l2_right = text2_lines[i + 1 : i + 1 + context_size]
                l2_left_context = " ".join(line.strip() for line in l2_left)
                l2_right_context = " ".join(line.strip() for line in l2_right)
                
                # Process text3 data
                l3_sentence = ""
                l3_left_context = ""
                l3_right_context = ""
                if text3 and i < len(text3_lines):
                    l3_sentence = text3_lines[i].strip()
                    l3_left = text3_lines[max(0, i - context_size) : i]
                    l3_right = text3_lines[i + 1 : i + 1 + context_size]
                    l3_left_context = " ".join(line.strip() for line in l3_left)
                    l3_right_context = " ".join(line.strip() for line in l3_right)

                simple_list_entry = ""
                if include_simple_list:
                    lemmas = process_sentence_lemmas(l1_sentence, lemma_index, nlp)
                    simple_list_entry = "<br>".join(lemmas) if with_br else "\n".join(lemmas)
                
                row_data = [
                    l1_sentence, "", "", "", "",
                    l1_left_context, l1_sentence, l1_right_context,
                    l2_left_context, l2_sentence, l2_right_context,
                    l3_left_context, l3_sentence, l3_right_context, # Add text3 data
                    simple_list_entry, l1_sentence,
                ]
                num_remaining_fields = len(header) - len(row_data) if with_fields else 68 - len(row_data)
                row_data.extend([""] * num_remaining_fields)

                if language == "de":
                    row_data[59] = "1"
                    row_data[66] = "1"
                elif language == "en":
                    row_data[57] = "1"
                    row_data[64] = "1"

                tsv_writer.writerow(row_data)

    except IOError as e:
        print(f"Error writing output: {e}", file=sys.stderr)
        sys.exit(1)

    return final_output_file


def main():
    parser = argparse.ArgumentParser(
        description="Extract and process tokens or sentences from text."
    )
    parser.add_argument(
        "--type", type=str, required=True, choices=["token", "sentence"],
        help="Type of processing: token or sentence",
    )
    parser.add_argument(
        "--language", type=str, default="de", choices=["de", "en"],
        help="Language for processing (default: de)",
    )
    parser.add_argument(
        "--lemma-index-file", type=str, default="",
        help="Path to the lemma index CSV file",
    )
    parser.add_argument("--text", type=str, help="Input text to process")
    parser.add_argument("--text1", type=str, help="Path to input text file to process")
    parser.add_argument(
        "--text2", type=str,
        help="Path to the second text file (e.g., translations)",
    )
    # Add text3 argument
    parser.add_argument(
        "--text3", type=str,
        help="Path to the third text file (e.g., alternative translation)",
    )
    parser.add_argument(
        "--detailed", action="store_true",
        help="STDOUT: Enable detailed output in console with sentence and context",
    )
    parser.add_argument(
        "--two-column-output", action="store_true",
        help="STDOUT: Output tokens in two columns: token and original form",
    )
    parser.add_argument(
        "--html", action="store_true", help="STDOUT: Output tokens in an HTML table"
    )
    parser.add_argument(
        "--sentence-context-size", type=int, default=1,
        help="CSV: Number of sentences to include before and after the target sentence (default: 1)",
    )
    parser.add_argument(
        "--output", type=str, required=False,
        help="CSV: Output TSV file path for saving results",
    )
    parser.add_argument(
        "--timestamp", action="store_true",
        help="CSV: Prepend timestamp to the output file name",
    )
    parser.add_argument(
        "--two-column-output-to-file", action="store_true",
        help="CSV: Include original forms in the TSV output file when writing to file",
    )
    parser.add_argument(
        "--include-simple-list", action="store_true",
        help="CSV: Include a simple list of tokens in the output file",
    )
    parser.add_argument(
        "--original-form-in-simple-list", action="store_true",
        help="CSV: Include original forms in the simple list entry in the TSV file",
    )
    parser.add_argument(
        "--with-fields", action="store_true",
        help="CSV: Include field names as the first row in the output TSV file",
    )
    parser.add_argument(
        "--with-br", action="store_true",
        help="Replace newlines with <br> in the simple list entry",
    )
    parser.add_argument(
        "--pipe", action="store_true",
        help="Enable pipeline mode - outputs TSV filename to stdout when using --output",
    )

    args = parser.parse_args()

    global nlp
    if args.language == "de":
        nlp = spacy.load("de_core_news_lg")
    else:
        nlp = spacy.load("en_core_web_lg")

    if args.type == "token":
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

        output_file = process_text(
            input_text, args.type, args.language, args.lemma_index_file,
            args.text, args.text1, args.text2, args.text3, # Pass args.text3
            args.detailed, args.two_column_output, args.html,
            args.sentence_context_size, args.output, args.timestamp,
            args.two_column_output_to_file, args.include_simple_list,
            args.original_form_in_simple_list, args.with_fields,
            args.with_br, args.pipe
        )

        if args.pipe and output_file:
            print(os.path.basename(output_file))

    elif args.type == "sentence":
        if not args.text1 or not args.text2:
            print("Error: Both --text1 and --text2 must be specified for sentence mode.")
            exit(1)

        final_output_file = process_sentences(
            args.type, args.language, args.lemma_index_file,
            args.text, args.text1, args.text2, args.text3, # Pass args.text3
            args.detailed, args.two_column_output, args.html,
            args.sentence_context_size, args.output, args.timestamp,
            args.two_column_output_to_file, args.include_simple_list,
            args.original_form_in_simple_list, args.with_fields,
            args.with_br, args.pipe
        )

        if args.pipe and args.output:
            print(os.path.basename(final_output_file))
    else:
        print("Error: Invalid --type specified.")
        exit(1)

if __name__ == "__main__":
    main()