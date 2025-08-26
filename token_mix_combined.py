import sys
import spacy
import csv
import argparse
from datetime import datetime
import os
import re
from contextlib import redirect_stdout
import io

# --- ИМПОРТ для GCS ---
try:
    from german_compound_splitter import comp_split
    GCS_AVAILABLE = True
except ImportError:
    GCS_AVAILABLE = False
# --- КОНЕЦ ИМПОРТА ---


# --- Вспомогательные функции ---

def load_dictionary_to_set(file_path):
    """Загружает словарь в set для быстрого поиска."""
    dictionary = set()
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                dictionary.add(line.strip())
    except FileNotFoundError:
        print(f"Файл словаря не найден: {file_path}", file=sys.stderr)
    except Exception as e:
        print(f"Ошибка при чтении файла словаря {file_path}: {e}", file=sys.stderr)
    return dictionary

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

def generate_autoname_prefix(text, num_words):
    if not text:
        return ""
    processed_text = text.lower()
    processed_text = processed_text.replace('ä', 'ae').replace('ö', 'oe').replace('ü', 'ue').replace('ß', 'ss')
    words = re.findall(r'[a-z0-9]+', processed_text)
    selected_words = words[:num_words]
    if not selected_words:
        return ""
    return "-".join(selected_words)

def process_sentence_lemmas(sentence, lemma_index, nlp, german_dict, gcs=False, ahocs=None, gcs_in_wordlist=False):
    doc = nlp(sentence)
    final_tokens = set()

    for token in doc:
        if token.is_alpha and token.dep_ != "svp":
            # Блок основной лемматизации токена
            token_text = token.text
            spacy_lemma = token.lemma_
            form_to_check = token_text if token_text.isupper() else token_text.capitalize()
            lemma_to_check = spacy_lemma if spacy_lemma.isupper() else spacy_lemma.capitalize()
            if token.pos_ in ["NOUN", "PROPN"] and spacy_lemma.isupper():
                base_lemma = spacy_lemma
            elif nlp.lang == "de" and token.pos_ in ["NOUN", "PROPN"]:
                base_lemma = spacy_lemma.capitalize()
            else:
                base_lemma = get_verb_with_particle(token) if token.pos_ == "VERB" else token.lemma_
            
            lemma_to_add = ""
            if form_to_check in german_dict:
                if lemma_to_check in german_dict:
                    lemma_to_add = base_lemma
                else:
                    lemma_to_add = form_to_check
            else:
                lemma_to_add = base_lemma

            # Финальная коррекция сингуляризации через GCS
            if gcs and ahocs and nlp.lang == 'de' and token.pos_ in ['NOUN', 'PROPN']:
                try:
                    with redirect_stdout(io.StringIO()):
                        dissection_result = comp_split.dissect(lemma_to_add, ahocs, make_singular=True)
                    final_components = comp_split.merge_fractions(dissection_result)
                    singular_form = "".join(final_components)
                    singular_form_to_check = singular_form if singular_form.isupper() else singular_form.capitalize()
                    if singular_form_to_check != lemma_to_add and singular_form_to_check in german_dict:
                        lemma_to_add = singular_form_to_check
                except Exception:
                    pass
            
            final_tokens.add(lemma_to_add)

            # Блок разбора сложных слов
            if gcs and ahocs and gcs_in_wordlist and nlp.lang == 'de' and len(token.text) > 7:
                try:
                    word_to_split = token.text
                    should_make_singular = (token.pos_ in ['NOUN', 'PROPN'])
                    with redirect_stdout(io.StringIO()):
                        dissection = comp_split.dissect(word_to_split, ahocs, make_singular=should_make_singular)
                    final_components = comp_split.merge_fractions(dissection)
                    if len(final_components) > 1:
                        for part in final_components:
                            part_to_check = part if part.isupper() else part.capitalize()
                            corrected_part = part_to_check
                            if part_to_check in german_dict and not part_to_check.endswith('e') and f"{part_to_check}e" in german_dict:
                                corrected_part = f"{part_to_check}e"
                            if corrected_part in german_dict:
                                final_tokens.add(corrected_part)
                            else:
                                part_doc = nlp(part)
                                if len(part_doc) > 0:
                                    lemmatized_part_str = part_doc[0].lemma_
                                    lemma_part_to_check = lemmatized_part_str if lemmatized_part_str.isupper() else lemmatized_part_str.capitalize()
                                    if lemma_part_to_check in german_dict:
                                        final_tokens.add(lemma_part_to_check)
                except Exception:
                    pass
    
    return sorted(list(final_tokens), key=lambda x: lemma_index.get(x, float("inf")))


def process_text_v1(
    input_text, lemma_index, language, text2, text3, sentence_context_size,
    output_file, two_column_output_to_file, include_simple_list,
    with_fields, with_br, pipe, gcs, ahocs, gcs_in_wordlist, german_dict
):
    if "\n" in input_text or not os.path.exists(input_text):
        text1_lines = input_text.splitlines()
    else:
        with open(input_text, "r", encoding="utf-8") as f1: text1_lines = [line.rstrip("\n") for line in f1]
    if text2:
        with open(text2, "r", encoding="utf-8") as f2: text2_lines = [line.rstrip("\n") for line in f2]
    text3_lines = []
    if text3:
        with open(text3, "r", encoding="utf-8") as f3: text3_lines = [line.rstrip("\n") for line in f3]
    unique_lemmatized_tokens, token_to_sentence, token_to_original_form = set(), {}, {}
    for i, line1 in enumerate(text1_lines):
        doc = nlp(line1)
        for token in doc:
            if token.is_alpha and token.dep_ != "svp":
                token_text = token.text
                spacy_lemma = token.lemma_
                form_to_check = token_text if token_text.isupper() else token_text.capitalize()
                lemma_to_check = spacy_lemma if spacy_lemma.isupper() else spacy_lemma.capitalize()
                if token.pos_ in ["NOUN", "PROPN"] and spacy_lemma.isupper():
                    base_lemma = spacy_lemma
                elif language == "de" and token.pos_ in ["NOUN", "PROPN"]:
                    base_lemma = spacy_lemma.capitalize()
                else:
                    base_lemma = get_verb_with_particle(token) if token.pos_ == "VERB" else token.lemma_
                if form_to_check in german_dict:
                    if lemma_to_check in german_dict:
                        primary_token = base_lemma
                    else:
                        primary_token = form_to_check
                else:
                    primary_token = base_lemma
                
                # --- ИСПРАВЛЕННЫЙ БЛОК: ФИНАЛЬНАЯ КОРРЕКЦИЯ СИНГУЛЯРИЗАЦИИ ---
                if gcs and ahocs and language == 'de' and token.pos_ in ['NOUN', 'PROPN']:
                    try:
                        with redirect_stdout(io.StringIO()):
                             dissection_result = comp_split.dissect(primary_token, ahocs, make_singular=True)
                        final_components = comp_split.merge_fractions(dissection_result)
                        singular_form = "".join(final_components)
                        singular_form_to_check = singular_form if singular_form.isupper() else singular_form.capitalize()
                        if singular_form_to_check != primary_token and singular_form_to_check in german_dict:
                            primary_token = singular_form_to_check
                    except Exception:
                        pass
                # --- КОНЕЦ ИСПРАВЛЕННОГО БЛОКА ---
                
                original_form = get_original_form_with_particle(token)
                tokens_to_add = {primary_token}
                if gcs and ahocs and language == 'de' and len(token.text) > 7:
                    try:
                        word_to_split = token.text
                        should_make_singular = (token.pos_ in ['NOUN', 'PROPN'])
                        with redirect_stdout(io.StringIO()):
                            dissection = comp_split.dissect(word_to_split, ahocs, make_singular=should_make_singular)
                        final_components = comp_split.merge_fractions(dissection)
                        if len(final_components) > 1:
                            for part in final_components:
                                part_to_check = part if part.isupper() else part.capitalize()
                                corrected_part = part_to_check
                                if part_to_check in german_dict and not part_to_check.endswith('e') and f"{part_to_check}e" in german_dict:
                                    corrected_part = f"{part_to_check}e"
                                if corrected_part in german_dict:
                                    tokens_to_add.add(corrected_part)
                                else:
                                    part_doc = nlp(part)
                                    if len(part_doc) > 0:
                                        lemmatized_part_str = part_doc[0].lemma_
                                        lemma_part_to_check = lemmatized_part_str if lemmatized_part_str.isupper() else lemmatized_part_str.capitalize()
                                        if lemma_part_to_check in german_dict:
                                            tokens_to_add.add(lemma_part_to_check)
                    except Exception:
                        pass
                for t in tokens_to_add:
                    unique_lemmatized_tokens.add(t)
                    if t not in token_to_sentence:
                        token_to_sentence[t] = (i, line1)
                        token_to_original_form[t] = original_form if t == primary_token else t
    sorted_tokens = sorted(unique_lemmatized_tokens, key=lambda token: (token not in lemma_index, lemma_index.get(token, 0), token))
    if output_file:
        with open(output_file, "w", newline="", encoding="utf-8") as tsvfile:
            tsv_writer = csv.writer(tsvfile, delimiter="\t")
            if with_fields:
                tsv_writer.writerow(get_full_header())
            for token in sorted_tokens:
                row_data = [""] * 80
                sent_index, l1_sentence = token_to_sentence.get(token, (-1, ""))
                if sent_index == -1: continue
                l1_sentence = l1_sentence.strip()
                l2_sentence = text2_lines[sent_index].strip() if text2 and sent_index < len(text2_lines) else ""
                start_idx, end_idx = max(0, sent_index - sentence_context_size), sent_index + sentence_context_size + 1
                row_data[5] = " ".join(line.strip() for line in text1_lines[start_idx:sent_index])
                row_data[6] = l1_sentence
                row_data[7] = " ".join(line.strip() for line in text1_lines[sent_index + 1:end_idx])
                if text2:
                    row_data[8] = " ".join(line.strip() for line in text2_lines[start_idx:sent_index])
                    row_data[9] = l2_sentence
                    row_data[10] = " ".join(line.strip() for line in text2_lines[sent_index + 1:end_idx])
                if text3:
                    row_data[77] = " ".join(line.strip() for line in text3_lines[start_idx:sent_index])
                    row_data[78] = text3_lines[sent_index].strip() if sent_index < len(text3_lines) else ""
                    row_data[79] = " ".join(line.strip() for line in text3_lines[sent_index + 1:end_idx])
                row_data[0] = token
                row_data[1] = token
                if two_column_output_to_file:
                    row_data[2] = token_to_original_form.get(token, '')
                row_data[12] = l1_sentence
                if include_simple_list:
                    lemmas = process_sentence_lemmas(l1_sentence, lemma_index, nlp, german_dict, gcs, ahocs, gcs_in_wordlist)
                    row_data[11] = "<br>".join(lemmas) if with_br else "\n".join(lemmas)
                if language == "de":
                    row_data[58] = "1"; row_data[65] = "1"
                elif language == "en":
                    row_data[56] = "1"; row_data[65] = "1"
                tsv_writer.writerow(row_data)
    return output_file

def process_text_v2(
    input_text, lemma_index, language, sentence_context_size,
    output_file, two_column_output_to_file, include_simple_list,
    with_fields, with_br, pipe, gcs, ahocs, gcs_in_wordlist, german_dict, **kwargs
):
    if '\n' in input_text.strip():
        processing_units = input_text.splitlines()
        is_line_based = True
    else:
        doc = nlp(input_text)
        processing_units = list(doc.sents)
        is_line_based = False
    unique_lemmatized_tokens, token_to_sentence, token_to_original_form = set(), {}, {}
    for unit_index, unit in enumerate(processing_units):
        unit_text = unit if is_line_based else unit.text
        doc_unit = nlp(unit_text)
        for token in doc_unit:
            if token.is_alpha and token.dep_ != "svp":
                token_text = token.text
                spacy_lemma = token.lemma_
                form_to_check = token_text if token_text.isupper() else token_text.capitalize()
                lemma_to_check = spacy_lemma if spacy_lemma.isupper() else spacy_lemma.capitalize()
                if token.pos_ in ["NOUN", "PROPN"] and spacy_lemma.isupper():
                    base_lemma = spacy_lemma
                elif language == "de" and token.pos_ in ["NOUN", "PROPN"]:
                    base_lemma = spacy_lemma.capitalize()
                else:
                    base_lemma = get_verb_with_particle(token) if token.pos_ == "VERB" else token.lemma_
                if form_to_check in german_dict:
                    if lemma_to_check in german_dict:
                        primary_token = base_lemma
                    else:
                        primary_token = form_to_check
                else:
                    primary_token = base_lemma

                # --- ИСПРАВЛЕННЫЙ БЛОК: ФИНАЛЬНАЯ КОРРЕКЦИЯ СИНГУЛЯРИЗАЦИИ ---
                if gcs and ahocs and language == 'de' and token.pos_ in ['NOUN', 'PROPN']:
                    try:
                        with redirect_stdout(io.StringIO()):
                             dissection_result = comp_split.dissect(primary_token, ahocs, make_singular=True)
                        final_components = comp_split.merge_fractions(dissection_result)
                        singular_form = "".join(final_components)
                        singular_form_to_check = singular_form if singular_form.isupper() else singular_form.capitalize()
                        if singular_form_to_check != primary_token and singular_form_to_check in german_dict:
                            primary_token = singular_form_to_check
                    except Exception:
                        pass
                # --- КОНЕЦ ИСПРАВЛЕННОГО БЛОКА ---

                original_form = get_original_form_with_particle(token)
                tokens_to_add = {primary_token}
                if gcs and ahocs and language == 'de' and len(token.text) > 7:
                    try:
                        word_to_split = token.text
                        should_make_singular = (token.pos_ in ['NOUN', 'PROPN'])
                        with redirect_stdout(io.StringIO()):
                            dissection = comp_split.dissect(word_to_split, ahocs, make_singular=should_make_singular)
                        final_components = comp_split.merge_fractions(dissection)
                        if len(final_components) > 1:
                            for part in final_components:
                                part_to_check = part if part.isupper() else part.capitalize()
                                corrected_part = part_to_check
                                if part_to_check in german_dict and not part_to_check.endswith('e') and f"{part_to_check}e" in german_dict:
                                    corrected_part = f"{part_to_check}e"
                                if corrected_part in german_dict:
                                    tokens_to_add.add(corrected_part)
                                else:
                                    part_doc = nlp(part)
                                    if len(part_doc) > 0:
                                        lemmatized_part_str = part_doc[0].lemma_
                                        lemma_part_to_check = lemmatized_part_str if lemmatized_part_str.isupper() else lemmatized_part_str.capitalize()
                                        if lemma_part_to_check in german_dict:
                                            tokens_to_add.add(lemma_part_to_check)
                    except Exception:
                        pass
                for t in tokens_to_add:
                    unique_lemmatized_tokens.add(t)
                    if t not in token_to_sentence:
                        token_to_sentence[t] = (unit_index, unit_text)
                        token_to_original_form[t] = original_form if t == primary_token else t
    sorted_tokens = sorted(unique_lemmatized_tokens, key=lambda token: (token not in lemma_index, lemma_index.get(token, 0), token))
    def get_unit_text(u):
        return u if is_line_based else u.text
    if not output_file:
        detailed = kwargs.get('detailed', False)
        two_column_output = kwargs.get('two_column_output', False)
        html = kwargs.get('html', False)
        if html:
            print("<table>")
            for token in sorted_tokens:
                print(f"<tr><td>{token}</td><td>{token_to_original_form.get(token, '')}</td></tr>")
            print("</table>")
        elif two_column_output:
            for token in sorted_tokens:
                print(f"{token}\t{token_to_original_form.get(token, '')}")
        elif detailed:
             for token in sorted_tokens:
                unit_index, l1_sentence = token_to_sentence[token]
                start_idx = max(0, unit_index - sentence_context_size)
                end_idx = min(len(processing_units), unit_index + sentence_context_size + 1)
                l1_left = " ".join(get_unit_text(u).strip() for u in processing_units[start_idx:unit_index])
                l1_right = " ".join(get_unit_text(u).strip() for u in processing_units[unit_index + 1:end_idx])
                print(token)
                if l1_left: print(l1_left)
                print(l1_sentence.strip())
                if l1_right: print(l1_right)
                print()
        else:
            for token in sorted_tokens:
                print(token)
        return None
    with open(output_file, "w", newline="", encoding="utf-8") as tsvfile:
        tsv_writer = csv.writer(tsvfile, delimiter="\t")
        if with_fields:
            tsv_writer.writerow(get_full_header())
        for token in sorted_tokens:
            row_data = [""] * 80
            unit_index, l1_sentence = token_to_sentence.get(token, (-1, ""))
            if unit_index == -1: continue
            l1_sentence = l1_sentence.strip()
            start_idx = max(0, unit_index - sentence_context_size)
            end_idx = min(len(processing_units), unit_index + sentence_context_size + 1)
            row_data[5] = " ".join(get_unit_text(u).strip() for u in processing_units[start_idx:unit_index])
            row_data[6] = l1_sentence
            row_data[7] = " ".join(get_unit_text(u).strip() for u in processing_units[unit_index + 1:end_idx])
            row_data[0] = token
            row_data[1] = token
            if two_column_output_to_file:
                row_data[2] = token_to_original_form.get(token, '')
            row_data[12] = l1_sentence
            if include_simple_list:
                lemmas = process_sentence_lemmas(l1_sentence, lemma_index, nlp, german_dict, gcs, ahocs, gcs_in_wordlist)
                row_data[11] = "<br>".join(lemmas) if with_br else "\n".join(lemmas)
            if language == "de":
                row_data[58] = "1"; row_data[65] = "1"
            elif language == "en":
                row_data[56] = "1"; row_data[65] = "1"
            tsv_writer.writerow(row_data)
    return output_file

def process_sentences(
    language, lemma_index, text1, text2, text3, sentence_context_size,
    output_file, include_simple_list, with_fields, with_br, pipe, german_dict, **kwargs
):
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
    with open(output_file, "w", newline="", encoding="utf-8") as out_file:
        tsv_writer = csv.writer(out_file, delimiter="\t")
        if with_fields:
            tsv_writer.writerow(get_full_header())
        for i in range(min_length):
            row_data = [""] * 80
            l1_sentence = text1_lines[i].strip()
            l2_sentence = text2_lines[i].strip()
            start_idx, end_idx = max(0, i - sentence_context_size), i + sentence_context_size + 1
            row_data[0] = l1_sentence
            row_data[5] = " ".join(line.strip() for line in text1_lines[start_idx:i])
            row_data[6] = l1_sentence
            row_data[7] = " ".join(line.strip() for line in text1_lines[i + 1:end_idx])
            row_data[8] = " ".join(line.strip() for line in text2_lines[start_idx:i])
            row_data[9] = l2_sentence
            row_data[10] = " ".join(line.strip() for line in text2_lines[i + 1:end_idx])
            if include_simple_list:
                lemmas = process_sentence_lemmas(l1_sentence, lemma_index, nlp, german_dict)
                row_data[11] = "<br>".join(lemmas) if with_br else "\n".join(lemmas)
            row_data[12] = l1_sentence
            if text3:
                row_data[77] = " ".join(line.strip() for line in text3_lines[start_idx:i])
                row_data[78] = text3_lines[i].strip()
                row_data[79] = " ".join(line.strip() for line in text3_lines[i + 1:end_idx])
            if language == "de":
                row_data[58] = "1"; row_data[65] = "1"
            elif language == "en":
                row_data[56] = "1"; row_data[65] = "1"
            tsv_writer.writerow(row_data)
    return output_file

def main():
    parser = argparse.ArgumentParser(description="Extract and process tokens or sentences from text.")
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
    parser.add_argument("--autoname", nargs='?', type=int, const=4, default=None, help="Automatically generate part of the filename from the first N words of the text. Defaults to 4 words if no number is given.")
    parser.add_argument("--two-column-output-to-file", action="store_true")
    parser.add_argument("--include-simple-list", action="store_true")
    parser.add_argument("--with-fields", action="store_true")
    parser.add_argument("--with-br", action="store_true")
    parser.add_argument("--pipe", action="store_true")
    parser.add_argument("--detailed", action="store_true")
    parser.add_argument("--two-column-output", action="store_true")
    parser.add_argument("--html", action="store_true")
    parser.add_argument("--original-form-in-simple-list", action="store_true")
    parser.add_argument("--gcs", action="store_true", help="Enable German Compound Splitting. Requires --language de.")
    parser.add_argument("--gcs-dictionary", default="german.dic", help="Path to the dictionary file for GCS.")
    parser.add_argument("--gcs-in-wordlist", action="store_true", help="Also add German compound components to the SentenceSourceWordlist field. Requires --gcs.")
    args = parser.parse_args()
    if args.gcs_in_wordlist and not args.gcs:
        print("Error: --gcs-in-wordlist requires --gcs to be enabled.", file=sys.stderr); exit(1)
    global nlp
    nlp = spacy.load("de_core_news_lg" if args.language == "de" else "en_core_web_lg")
    ahocs = None
    german_dict = set()
    if args.language == 'de':
        german_dict = load_dictionary_to_set(args.gcs_dictionary)
        if not german_dict:
             print("Warning: German dictionary for validation is empty or not loaded.", file=sys.stderr)
        if args.gcs:
            if not GCS_AVAILABLE:
                print("Error: 'german-compound-splitter' library not installed. Please run 'pip install german-compound-splitter'.", file=sys.stderr); exit(1)
            if not os.path.exists(args.gcs_dictionary):
                print(f"Error: GCS dictionary file '{args.gcs_dictionary}' not found!", file=sys.stderr)
                print("Please download it and place it in the correct directory.", file=sys.stderr); exit(1)
            try:
                with redirect_stdout(io.StringIO()):
                    ahocs = comp_split.read_dictionary_from_file(args.gcs_dictionary)
            except Exception as e:
                print(f"Error loading GCS dictionary: {e}", file=sys.stderr); exit(1)
    lemma_index = load_lemma_index(args.lemma_index_file)
    processed_output_file = None
    final_output_path = args.output
    if args.output and (args.timestamp or args.autoname is not None):
        zid = datetime.now().strftime('%Y%m%d%H%M%S')
        output_dir, filename = os.path.dirname(args.output) or '.', os.path.basename(args.output)
        if args.autoname is not None:
            source_text_for_autoname = ""
            if args.text:
                source_text_for_autoname = args.text
            elif args.text1:
                try:
                    with open(args.text1, 'r', encoding='utf-8') as f:
                        source_text_for_autoname = f.read(1024) 
                except Exception as e:
                    print(f"Warning: Could not read {args.text1} for autonaming: {e}", file=sys.stderr)
            autoname_part = generate_autoname_prefix(source_text_for_autoname, args.autoname)
            if autoname_part:
                first_dot_pos = filename.find('.')
                suffix = filename[first_dot_pos:] if first_dot_pos != -1 else ""
                new_filename = f"{zid}-{autoname_part}{suffix}"
            else:
                 new_filename = f"{zid}-{filename}"
            final_output_path = os.path.join(output_dir, new_filename)
        elif args.timestamp:
            new_filename = f"{zid}-{filename}"
            final_output_path = os.path.join(output_dir, new_filename)
    if args.type == "token":
        if args.text and args.text1:
            print("Error: --text and --text1 are mutually exclusive.", file=sys.stderr); exit(1)
        input_text = args.text or (read_input_text(args.text1) if args.text1 else "")
        if not input_text:
            print("Error: Either --text or --text1 must be specified.", file=sys.stderr); exit(1)
        if args.text2:
            processed_output_file = process_text_v1(
                input_text, lemma_index, args.language, args.text2, args.text3,
                args.sentence_context_size, final_output_path,
                args.two_column_output_to_file, args.include_simple_list,
                args.with_fields, args.with_br, args.pipe,
                args.gcs, ahocs, args.gcs_in_wordlist, german_dict
            )
        else:
             processed_output_file = process_text_v2(
                input_text, lemma_index, args.language, args.sentence_context_size,
                final_output_path, args.two_column_output_to_file, args.include_simple_list,
                args.with_fields, args.with_br, args.pipe,
                args.gcs, ahocs, args.gcs_in_wordlist, german_dict,
                detailed=args.detailed, two_column_output=args.two_column_output, html=args.html
            )
    elif args.type == "sentence":
        if args.gcs:
            print("Warning: --gcs flag is only applicable for --type token and will be ignored.", file=sys.stderr)
        if not args.text1 or not args.text2:
            print("Error: --text1 and --text2 must be specified for sentence mode.", file=sys.stderr); exit(1)
        processed_output_file = process_sentences(
            args.language, lemma_index, args.text1, args.text2, args.text3,
            args.sentence_context_size, final_output_path,
            args.include_simple_list, args.with_fields, args.with_br, args.pipe,
            german_dict
        )
    if args.pipe and processed_output_file:
        print(os.path.basename(processed_output_file))

if __name__ == "__main__":
    main()