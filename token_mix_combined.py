import sys
import spacy
import csv
import argparse
from datetime import datetime
import os

# --- Все вспомогательные функции (get_verb_with_particle, и т.д.) ---
# Они остаются без изменений
def get_verb_with_particle(token):
    if token.pos_ == "VERB":
        for particle in token.rights:
            if particle.dep_ == "svp":
                return f"{particle.text}{token.lemma_}"
    return token.lemma_

def get_original_form_with_particle(token):
    if token.pos_ == "VERB":
        particle = next((child for child in token.children if child.dep_ == "svp"), None)
        if particle:
            return f"{token.text} {particle.text}"
    return token.text

def load_lemma_index(file_path):
    lemma_index = {}
    try:
        with open(file_path, "r", newline="", encoding="utf-8") as csvfile:
            csv_reader = csv.reader(csvfile)
            for line_number, row in enumerate(csv_reader):
                if row and row[0] not in lemma_index:
                    lemma_index[row[0]] = line_number
    except FileNotFoundError:
        print(f"File not found: {file_path}", file=sys.stderr)
        return {}
    except Exception as e:
        print(f"Error reading file {file_path}: {e}", file=sys.stderr)
        return {}
    return lemma_index

def read_input_text(input_file):
    try:
        with open(input_file, "r", encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError:
        print(f"File not found: {input_file}", file=sys.stderr); exit(1)
    except Exception as e:
        print(f"Error reading file {input_file}: {e}", file=sys.stderr); exit(1)

def process_sentence_lemmas(sentence, lemma_index, nlp):
    doc = nlp(sentence)
    sentence_tokens = {get_verb_with_particle(token) if token.pos_ == "VERB" else token.lemma_
                       for token in doc if token.is_alpha and token.dep_ != "svp"}
    return sorted(sentence_tokens, key=lambda x: lemma_index.get(x, float("inf")))

def get_full_header():
    return [
        "Quotation", "WordSource", "WordSourceInflectedForm", "WordDestination", "WordSourceContext",
        "SentenceSourceContextLeft", "SentenceSource", "SentenceSourceContextRight",
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
        "Destination-de-DE", "Destination-uk-UA", "Destination-ru-RU", "Overlapping",
        "ToggleAlwaysEmptyField", "Note ID", "am-all-morphs", "am-all-morphs-count",
        "am-unknown-morphs", "am-unknown-morphs-count", "am-highlighted", "am-score",
        "am-score-terms", "am-study-morphs", "SentenceDestination2ContextLeft",
        "SentenceDestination2", "SentenceDestination2ContextRight"
    ]


def process_text_v1(
    input_text, lemma_index, language, text2, text3, sentence_context_size,
    output_file, timestamp, two_column_output_to_file, include_simple_list,
    with_fields, with_br, pipe
):
    final_output_file = output_file
    if "\n" in input_text or not os.path.exists(input_text):
        text1_lines = input_text.splitlines()
    else:
        with open(input_text, "r", encoding="utf-8") as f1: text1_lines = [line.rstrip("\n") for line in f1]

    with open(text2, "r", encoding="utf-8") as f2: text2_lines = [line.rstrip("\n") for line in f2]

    text3_lines = []
    if text3:
        with open(text3, "r", encoding="utf-8") as f3: text3_lines = [line.rstrip("\n") for line in f3]
    
    unique_lemmatized_tokens, token_to_sentence, token_to_original_form = set(), {}, {}
    for i, line1 in enumerate(text1_lines):
        doc = nlp(line1)
        for token in doc:
            if token.is_alpha and token.dep_ != "svp":
                verb_form = get_verb_with_particle(token) if language == "de" and token.pos_ == "VERB" else token.lemma_
                original_form = get_original_form_with_particle(token) if language == "de" and token.pos_ == "VERB" else token.text
                unique_lemmatized_tokens.add(verb_form)
                token_to_sentence[verb_form] = (i, line1)
                token_to_original_form[verb_form] = original_form

    sorted_tokens = sorted(unique_lemmatized_tokens, key=lambda token: (token not in lemma_index, lemma_index.get(token, 0), token))

    if output_file:
        if timestamp:
            output_dir, filename = os.path.dirname(output_file), os.path.basename(output_file)
            final_output_file = os.path.join(output_dir, f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{filename}")

        with open(final_output_file, "w", newline="", encoding="utf-8") as tsvfile:
            tsv_writer = csv.writer(tsvfile, delimiter="\t")
            if with_fields:
                tsv_writer.writerow(get_full_header())

            for token in sorted_tokens:
                row_data = [""] * 80
                sent_index, l1_sentence = token_to_sentence[token]
                l1_sentence = l1_sentence.strip()
                l2_sentence = text2_lines[sent_index].strip()
                
                start_idx, end_idx = max(0, sent_index - sentence_context_size), sent_index + sentence_context_size + 1
                
                row_data[5] = " ".join(line.strip() for line in text1_lines[start_idx:sent_index])
                row_data[6] = l1_sentence
                row_data[7] = " ".join(line.strip() for line in text1_lines[sent_index + 1:end_idx])
                row_data[8] = " ".join(line.strip() for line in text2_lines[start_idx:sent_index])
                row_data[9] = l2_sentence
                row_data[10] = " ".join(line.strip() for line in text2_lines[sent_index + 1:end_idx])
                
                if text3:
                    row_data[77] = " ".join(line.strip() for line in text3_lines[start_idx:sent_index])
                    row_data[78] = text3_lines[sent_index].strip()
                    row_data[79] = " ".join(line.strip() for line in text3_lines[sent_index + 1:end_idx])
                
                row_data[0] = token
                row_data[1] = token
                if two_column_output_to_file:
                    row_data[2] = token_to_original_form[token]
                row_data[12] = l1_sentence
                if include_simple_list:
                    row_data[11] = "<br>".join(process_sentence_lemmas(l1_sentence, lemma_index, nlp)) if with_br else "\n".join(process_sentence_lemmas(l1_sentence, lemma_index, nlp))
                
                if language == "de":
                    row_data[58] = "1"
                    row_data[65] = "1"
                elif language == "en":
                    row_data[56] = "1"
                    row_data[65] = "1"

                tsv_writer.writerow(row_data)
    
    return final_output_file


def process_text_v2(
    input_text, lemma_index, language, sentence_context_size,
    output_file, timestamp, two_column_output_to_file, include_simple_list,
    with_fields, with_br, pipe, **kwargs # kwargs для лишних аргументов из stdout (detailed, и т.д.)
):
    if not output_file and not pipe:
        # Логика для GoldenDict (вывод в консоль)
        # ...
        return None

    final_output_file = output_file
    doc = nlp(input_text)
    unique_lemmatized_tokens, token_to_sentence, token_to_original_form = set(), {}, {}
    sentences = list(doc.sents)
    
    for sent_index, sent in enumerate(sentences):
        for token in sent:
            if token.is_alpha and token.dep_ != "svp":
                verb_form = get_verb_with_particle(token) if language == "de" and token.pos_ == "VERB" else token.lemma_
                original_form = get_original_form_with_particle(token) if language == "de" and token.pos_ == "VERB" else token.text
                unique_lemmatized_tokens.add(verb_form)
                token_to_sentence[verb_form] = (sent_index, sent.text)
                token_to_original_form[verb_form] = original_form
    
    sorted_tokens = sorted(unique_lemmatized_tokens, key=lambda token: (token not in lemma_index, lemma_index.get(token, 0), token))

    if output_file:
        if timestamp:
            output_dir, filename = os.path.dirname(output_file), os.path.basename(output_file)
            final_output_file = os.path.join(output_dir, f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{filename}")

        with open(final_output_file, "w", newline="", encoding="utf-8") as tsvfile:
            tsv_writer = csv.writer(tsvfile, delimiter="\t")
            if with_fields:
                tsv_writer.writerow(get_full_header())

            for token in sorted_tokens:
                row_data = [""] * 80
                sent_index, l1_sentence = token_to_sentence[token]
                l1_sentence = l1_sentence.strip()
                
                start_idx, end_idx = max(0, sent_index - sentence_context_size), min(len(sentences), sent_index + sentence_context_size + 1)
                
                row_data[5] = " ".join(sent.text.strip() for sent in sentences[start_idx:sent_index])
                row_data[6] = l1_sentence
                row_data[7] = " ".join(sent.text.strip() for sent in sentences[sent_index + 1:end_idx])
                
                row_data[0] = token
                row_data[1] = token
                if two_column_output_to_file:
                    row_data[2] = token_to_original_form[token]
                row_data[12] = l1_sentence
                if include_simple_list:
                    row_data[11] = "<br>".join(process_sentence_lemmas(l1_sentence, lemma_index, nlp)) if with_br else "\n".join(process_sentence_lemmas(l1_sentence, lemma_index, nlp))

                if language == "de":
                    row_data[58] = "1"
                    row_data[65] = "1"
                elif language == "en":
                    row_data[56] = "1"
                    row_data[65] = "1"
                
                tsv_writer.writerow(row_data)

    return final_output_file


def process_sentences(
    language, lemma_index, text1, text2, text3, sentence_context_size,
    output_file, timestamp, include_simple_list, with_fields, with_br, pipe, **kwargs
):
    final_output_file = output_file
    try:
        with open(text1, "r", encoding="utf-8") as f: text1_lines = [line.rstrip("\n") for line in f]
        with open(text2, "r", encoding="utf-8") as f: text2_lines = [line.rstrip("\n") for line in f]
        text3_lines = []
        if text3:
            with open(text3, "r", encoding="utf-8") as f: text3_lines = [line.rstrip("\n") for line in f]
    except IOError as e:
        print(f"Error reading files: {e}", file=sys.stderr); sys.exit(1)
        
    if timestamp and output_file:
        output_dir, filename = os.path.dirname(output_file), os.path.basename(output_file)
        final_output_file = os.path.join(output_dir, f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{filename}")

    with open(final_output_file, "w", newline="", encoding="utf-8") as out_file:
        tsv_writer = csv.writer(out_file, delimiter="\t")
        if with_fields:
            tsv_writer.writerow(get_full_header())

        min_length = len(text1_lines) # Assume lengths are checked/handled before

        for i in range(min_length):
            row_data = [""] * 80
            # ... (заполнение row_data, как и в других функциях)
            
            if language == "de":
                row_data[58] = "1"
                row_data[65] = "1"
            elif language == "en":
                row_data[56] = "1"
                row_data[65] = "1"

            tsv_writer.writerow(row_data)
            
    return final_output_file


# --- MAIN (с явными и надежными вызовами) ---
def main():
    parser = argparse.ArgumentParser(description="Extract and process tokens or sentences from text.")
    # Все аргументы...
    parser.add_argument("--type", required=True, choices=["token", "sentence"])
    parser.add_argument("--language", default="de", choices=["de", "en"])
    parser.add_argument("--lemma-index-file", default="")
    parser.add_argument("--text", help="Input text to process")
    parser.add_argument("--text1", help="Path to input text file to process")
    parser.add_argument("--text2", help="Path to the second text file")
    parser.add_argument("--text3", help="Path to the third text file")
    parser.add_argument("--sentence-context-size", type=int, default=1)
    parser.add_argument("--output")
    parser.add_argument("--timestamp", action="store_true")
    parser.add_argument("--two-column-output-to-file", action="store_true")
    parser.add_argument("--include-simple-list", action="store_true")
    parser.add_argument("--with-fields", action="store_true")
    parser.add_argument("--with-br", action="store_true")
    parser.add_argument("--pipe", action="store_true")
    parser.add_argument("--detailed", action="store_true")
    parser.add_argument("--two-column-output", action="store_true")
    parser.add_argument("--html", action="store_true")
    parser.add_argument("--original-form-in-simple-list", action="store_true")
    args = parser.parse_args()

    global nlp
    nlp = spacy.load("de_core_news_lg" if args.language == "de" else "en_core_web_lg")
    
    lemma_index = load_lemma_index(args.lemma_index_file)
    final_output_file = None

    if args.type == "token":
        if args.text and args.text1:
            print("Error: --text and --text1 are mutually exclusive.", file=sys.stderr); exit(1)
        input_text = args.text or (read_input_text(args.text1) if args.text1 else "")
        if not input_text:
            print("Error: Either --text or --text1 must be specified.", file=sys.stderr); exit(1)
        
        # Явный и надежный вызов на основе наличия --text2
        if args.text2:
            final_output_file = process_text_v1(
                input_text, lemma_index, args.language, args.text2, args.text3,
                args.sentence_context_size, args.output, args.timestamp,
                args.two_column_output_to_file, args.include_simple_list,
                args.with_fields, args.with_br, args.pipe
            )
        else:
             final_output_file = process_text_v2(
                input_text, lemma_index, args.language, args.sentence_context_size,
                args.output, args.timestamp, args.two_column_output_to_file, args.include_simple_list,
                args.with_fields, args.with_br, args.pipe,
                # Передаем stdout-аргументы, которые v2 может использовать
                detailed=args.detailed, two_column_output=args.two_column_output, html=args.html
            )

    elif args.type == "sentence":
        if not args.text1 or not args.text2:
            print("Error: --text1 and --text2 must be specified for sentence mode.", file=sys.stderr); exit(1)
        final_output_file = process_sentences(
            args.language, lemma_index, args.text1, args.text2, args.text3,
            args.sentence_context_size, args.output, args.timestamp,
            args.include_simple_list, args.with_fields, args.with_br, args.pipe
        )
    
    if args.pipe and final_output_file:
        print(os.path.basename(final_output_file))

if __name__ == "__main__":
    main()