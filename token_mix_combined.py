import sys
import spacy
import csv
import argparse
from datetime import datetime
import os

# ... (все функции get_verb_with_particle, load_lemma_index, и т.д. остаются без изменений) ...
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
    # Эта функция остается без изменений
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


# --- ИСПРАВЛЕННАЯ ФУНКЦИЯ-ДИСПЕТЧЕР ---
def process_text(
    input_text, language, lemma_index_file, text2, text3, detailed,
    two_column_output, html, sentence_context_size, output, timestamp,
    two_column_output_to_file, include_simple_list, original_form_in_simple_list,
    with_fields, with_br, pipe
):
    """
    Dispatcher function that calls the correct processing function (v1 or v2)
    based on whether parallel text (--text2) is provided.
    """
    # Загружаем индекс лемм один раз здесь
    lemma_index = load_lemma_index(lemma_index_file)

    if text2:
        # Если есть --text2, используем функцию для параллельных текстов
        return process_text_v1(
            input_text, lemma_index, language, text2, text3, sentence_context_size,
            output, timestamp, two_column_output_to_file, include_simple_list,
            with_fields, with_br, pipe, detailed, two_column_output, html
        )
    else:
        # Если --text2 нет, используем функцию для одиночного текста
        return process_text_v2(
            input_text, lemma_index, language, sentence_context_size,
            output, timestamp, two_column_output_to_file, include_simple_list,
            original_form_in_simple_list, with_fields, with_br, pipe,
            detailed, two_column_output, html
        )

# --- process_text_v1 остается почти без изменений ---
def process_text_v1(
    input_text, lemma_index, language, text2, text3, sentence_context_size,
    output_file, timestamp, two_column_output_to_file, include_simple_list,
    with_fields, with_br, pipe, detailed_output, two_column_output, html_output
):
    # ... код функции process_text_v1 остается прежним ...
    final_output_file = output_file
    if "\n" in input_text or not os.path.exists(input_text):
        text1_lines = input_text.splitlines()
    else:
        with open(input_text, "r", encoding="utf-8") as f1: text1_lines = [line.rstrip("\n") for line in f1]
    with open(text2, "r", encoding="utf-8") as f2: text2_lines = [line.rstrip("\n") for line in f2]
    text3_lines = []
    if text3:
        with open(text3, "r", encoding="utf-8") as f3: text3_lines = [line.rstrip("\n") for line in f3]
    # ... остальной код функции ...
    # (Я опускаю его для краткости, он не менялся)
    return final_output_file


# --- Новая, более чистая версия process_text_v2 для одного текста ---
def process_text_v2(
    input_text, lemma_index, language, sentence_context_size,
    output_file, timestamp, two_column_output_to_file, include_simple_list,
    original_form_in_simple_list, with_fields, with_br, pipe,
    detailed_output, two_column_output, html_output
):
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

    sorted_tokens = sorted(
        unique_lemmatized_tokens,
        key=lambda token: (token not in lemma_index, lemma_index.get(token, 0), token)
    )

    # --- ВЫВОД В КОНСОЛЬ (STDOUT) - ваш случай с GoldenDict ---
    # Если файл для вывода не указан, выводим в консоль
    if not output_file and not pipe:
        if html_output:
            print("<table>")
            for token in sorted_tokens:
                print(f"<tr><td>{token}</td><td>{token_to_original_form[token]}</td></tr>")
            print("</table>")
        elif two_column_output:
            for token in sorted_tokens:
                print(f"{token}\t{token_to_original_form[token]}")
        elif detailed_output:
             for token in sorted_tokens:
                sent_index, l1_sentence = token_to_sentence[token]
                start_idx, end_idx = max(0, sent_index - sentence_context_size), min(len(sentences), sent_index + sentence_context_size + 1)
                l1_left = " ".join(sent.text.strip() for sent in sentences[start_idx:sent_index])
                l1_right = " ".join(sent.text.strip() for sent in sentences[sent_index + 1:end_idx])
                print(token)
                if l1_left: print(l1_left)
                print(l1_sentence)
                if l1_right: print(l1_right)
                print()
        else:
            for token in sorted_tokens:
                print(token)
        return None # Завершаем выполнение, так как вывод в файл не требуется

    # --- ВЫВОД В ФАЙЛ (если --output указан) ---
    # (этот код остается на случай, если вы захотите сохранить результат v2 в файл)
    # ...
    return output_file


# ... (process_sentences остается без изменений) ...


# --- ИСПРАВЛЕННАЯ ФУНКЦИЯ MAIN ---
def main():
    parser = argparse.ArgumentParser(description="Extract and process tokens or sentences from text.")
    # Аргументы остаются те же
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
    parser.add_argument("--original-form-in-simple-list", action="store_true")
    parser.add_argument("--with-fields", action="store_true")
    parser.add_argument("--with-br", action="store_true")
    parser.add_argument("--pipe", action="store_true")
    parser.add_argument("--detailed", action="store_true")
    parser.add_argument("--two-column-output", action="store_true")
    parser.add_argument("--html", action="store_true")
    args = parser.parse_args()

    global nlp
    nlp = spacy.load("de_core_news_lg" if args.language == "de" else "en_core_web_lg")

    final_output_file = None

    if args.type == "token":
        # 1. Проверяем на недопустимую комбинацию
        if args.text and args.text1:
            print("Error: --text and --text1 are mutually exclusive.", file=sys.stderr); exit(1)

        # 2. Определяем входной текст
        input_text = ""
        if args.text:
            input_text = args.text
        elif args.text1:
            input_text = read_input_text(args.text1)

        # 3. Убеждаемся, что текст есть
        if not input_text:
            print("Error: Either --text or --text1 must be specified.", file=sys.stderr); exit(1)
        
        # 4. Вызываем диспетчер, который сам выберет v1 или v2
        final_output_file = process_text(
            input_text, args.language, args.lemma_index_file, args.text2, args.text3,
            args.detailed, args.two_column_output, args.html,
            args.sentence_context_size, args.output, args.timestamp,
            args.two_column_output_to_file, args.include_simple_list,
            args.original_form_in_simple_list, args.with_fields,
            args.with_br, args.pipe
        )

    elif args.type == "sentence":
        # Логика для sentence остается прежней, так как она всегда требует файлы
        if not args.text1 or not args.text2:
            print("Error: --text1 and --text2 must be specified for sentence mode.", file=sys.stderr); exit(1)
        # final_output_file = process_sentences(...) # вызов process_sentences
    
    if args.pipe and final_output_file:
        print(os.path.basename(final_output_file))

if __name__ == "__main__":
    main()