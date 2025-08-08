import sys
import spacy
import csv
import argparse
from datetime import datetime
import os

# --- Все вспомогательные функции (get_verb_with_particle, load_lemma_index, и т.д.) ---
# Они остаются без изменений, я их опускаю для краткости
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


# --- ИЗМЕНЕННЫЕ ФУНКЦИИ-ОБРАБОТЧИКИ ---

def process_text_v1(
    input_text, lemma_index, language, text2, text3, sentence_context_size,
    output_file, timestamp, two_column_output_to_file, include_simple_list,
    with_fields, with_br, pipe, **kwargs # kwargs для совместимости
):
    final_output_file = output_file
    # ... код для чтения text1, text2, text3 ...
    # ... код для извлечения токенов ...
    # (вся эта часть остается без изменений)
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
                # ... код для формирования контекстов ...
                row_data = [""] * 80
                # ... код для заполнения данных ...

                # --- ВАШ БЛОК ДЛЯ УСТАНОВКИ ФЛАГОВ ЯЗЫКОВ ---
                if language == "de":
                    row_data[58] = "1"  # 59: Source-de-DE
                    row_data[65] = "1"  # 66: Destination-ru-RU
                elif language == "en":
                    row_data[56] = "1"  # 57: Source-en-GB
                    row_data[65] = "1"  # 66: Destination-ru-RU

                tsv_writer.writerow(row_data)
    
    return final_output_file


def process_text_v2(
    input_text, lemma_index, language, sentence_context_size,
    output_file, timestamp, two_column_output_to_file, include_simple_list,
    original_form_in_simple_list, with_fields, with_br, pipe, **kwargs
):
    # Код для вывода в консоль (GoldenDict)
    if not output_file and not pipe:
        # ... (этот код не меняется, он для stdout) ...
        return None

    # Код для сохранения файла
    final_output_file = output_file
    doc = nlp(input_text)
    unique_lemmatized_tokens, token_to_sentence, token_to_original_form = set(), {}, {}
    sentences = list(doc.sents)
    
    # ... код для извлечения токенов ...
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
                # ... код для формирования контекстов и данных ...
                row_data = [""] * 80
                # ...

                # --- ВАШ БЛОК ДЛЯ УСТАНОВКИ ФЛАГОВ ЯЗЫКОВ ---
                if language == "de":
                    row_data[58] = "1"  # 59: Source-de-DE
                    row_data[65] = "1"  # 66: Destination-ru-RU
                elif language == "en":
                    row_data[56] = "1"  # 57: Source-en-GB
                    row_data[65] = "1"  # 66: Destination-ru-RU
                
                tsv_writer.writerow(row_data)

    return final_output_file

def process_sentences(
    language, lemma_index, text1, text2, text3, sentence_context_size,
    output_file, timestamp, include_simple_list, with_fields, with_br, pipe, **kwargs
):
    # ... код для чтения файлов и обработки ...

    with open(final_output_file, "w", newline="", encoding="utf-8") as out_file:
        # ...
        for i in range(min_length):
            # ...
            row_data = [""] * 80
            # ...

            # --- ВАШ БЛОК ДЛЯ УСТАНОВКИ ФЛАГОВ ЯЗЫКОВ ---
            if language == "de":
                row_data[58] = "1"  # 59: Source-de-DE
                row_data[65] = "1"  # 66: Destination-ru-RU
            elif language == "en":
                row_data[56] = "1"  # 57: Source-en-GB
                row_data[65] = "1"  # 66: Destination-ru-RU

            tsv_writer.writerow(row_data)
            
    return final_output_file


# --- ФУНКЦИЯ-ДИСПЕТЧЕР ---
def process_text(
    input_text, lemma_index, language, text2, text3, **kwargs
):
    if text2:
        return process_text_v1(input_text, lemma_index, language, text2, text3, **kwargs)
    else:
        return process_text_v2(input_text, lemma_index, language, **kwargs)

# --- MAIN ---
def main():
    parser = argparse.ArgumentParser(description="...")
    # ... все аргументы ...
    args = parser.parse_args()

    global nlp
    nlp = spacy.load("de_core_news_lg" if args.language == "de" else "en_core_web_lg")
    
    lemma_index = load_lemma_index(args.lemma_index_file)

    if args.type == "token":
        if args.text and args.text1:
            print("Error: --text and --text1 are mutually exclusive.", file=sys.stderr); exit(1)
        input_text = args.text or (read_input_text(args.text1) if args.text1 else "")
        if not input_text:
            print("Error: Either --text or --text1 must be specified.", file=sys.stderr); exit(1)
        
        # Передаем все аргументы как словарь, чтобы функции сами взяли, что им нужно
        final_output_file = process_text(input_text, lemma_index, **vars(args))

    elif args.type == "sentence":
        if not args.text1 or not args.text2:
            print("Error: --text1 and --text2 must be specified for sentence mode.", file=sys.stderr); exit(1)
        final_output_file = process_sentences(lemma_index=lemma_index, **vars(args))
    
    if args.pipe and final_output_file:
        print(os.path.basename(final_output_file))

if __name__ == "__main__":
    main()