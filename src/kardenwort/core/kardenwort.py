import sys
import spacy
import csv
import argparse
from datetime import datetime
import os
import re
from contextlib import redirect_stdout
import io

try:
    from german_compound_splitter import comp_split
    GCS_AVAILABLE = True
except ImportError:
    GCS_AVAILABLE = False

def _format_gcs_component_case(component):
    if not component or len(component) < 2:
        return component
    return component[0] + component[1:].lower()

def load_dictionary(file_path):
    dictionary = set()
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                dictionary.add(line.strip())
    except FileNotFoundError:
        print(f"Dictionary file not found: {file_path}", file=sys.stderr)
    except Exception as e:
        print(f"Error reading dictionary file {file_path}: {e}", file=sys.stderr)
    return dictionary

def load_lemma_override_rules(file_path):
    override_rules = {
        'priority1': {},
        'priority1_regex': [],
        'priority2': {},
        'priority2_regex': [],
        'priority3': {}
    }
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter="\t")
            for i, row in enumerate(reader):
                if not row or row[0].startswith('#'):
                    continue

                if len(row) < 3:
                    print(f"Warning: Skipping malformed line {i+1} in {file_path}: expected at least 3 columns.", file=sys.stderr)
                    continue
                
                spacy_lemma_to_match = row[0].strip()
                source_word_to_match_raw = row[1]
                target_lemma = row[2].strip()

                context_condition = None
                if len(row) > 3 and row[3]:
                    context_condition_raw = row[3]
                    if context_condition_raw.startswith('regex:'):
                        context_condition = context_condition_raw
                    else:
                        context_condition = context_condition_raw.strip()

                if not target_lemma or (not spacy_lemma_to_match and not source_word_to_match_raw.strip()):
                    print(f"Warning: Skipping invalid rule on line {i+1} in {file_path}: Target_Lemma (col 3) and at least one of Result_Lemma (col 1) or Original_Word (col 2) must be set.", file=sys.stderr)
                    continue

                override_rule = (target_lemma, context_condition)

                is_source_word_regex = source_word_to_match_raw.startswith('regex:')
                source_word_to_match = source_word_to_match_raw.strip()

                if spacy_lemma_to_match and source_word_to_match:
                    if is_source_word_regex:
                        pattern = source_word_to_match_raw[6:]
                        override_rules['priority1_regex'].append((spacy_lemma_to_match, pattern, override_rule))
                    else:
                        key = (spacy_lemma_to_match, source_word_to_match)
                        if key not in override_rules['priority1']:
                            override_rules['priority1'][key] = []
                        override_rules['priority1'][key].append(override_rule)
                
                elif source_word_to_match:
                    if is_source_word_regex:
                        pattern = source_word_to_match_raw[6:]
                        override_rules['priority2_regex'].append((pattern, override_rule))
                    else:
                        key = source_word_to_match
                        if key not in override_rules['priority2']:
                            override_rules['priority2'][key] = []
                        override_rules['priority2'][key].append(override_rule)
                
                elif spacy_lemma_to_match:
                    key = spacy_lemma_to_match
                    if key not in override_rules['priority3']:
                        override_rules['priority3'][key] = []
                    override_rules['priority3'][key].append(override_rule)

    except FileNotFoundError:
        print(f"Lemma override file not found: {file_path}", file=sys.stderr)
    except Exception as e:
        print(f"Error reading lemma override file {file_path}: {e}", file=sys.stderr)
    return override_rules

def find_matching_override_in_context(rules, context_sentence):
    if not rules:
        return None
    rules_with_context = [r for r in rules if r[1]]
    rule_without_context = next((r for r in rules if not r[1]), None)
    
    for overridden_lemma, context_condition in rules_with_context:
        if context_condition:
            if context_condition.startswith('regex:'):
                context_regex_pattern = context_condition[6:]
                try:
                    if re.search(context_regex_pattern, context_sentence):
                        return overridden_lemma
                except re.error as e:
                    print(f"Warning: Invalid regex in override rule: '{context_regex_pattern}'. Error: {e}", file=sys.stderr)
            else:
                if context_condition in context_sentence:
                    return overridden_lemma
            
    if rule_without_context:
        return rule_without_context[0]
        
    return None

def get_overridden_lemma_for_word(initial_lemma, original_word, override_rules, context_sentence):
    priority1_rules = override_rules.get('priority1', {}).get((initial_lemma, original_word))
    matched_lemma1 = find_matching_override_in_context(priority1_rules, context_sentence)
    if matched_lemma1 is not None:
        return matched_lemma1

    for spacy_lemma_condition, source_word_regex, override_rule in override_rules.get('priority1_regex', []):
        if spacy_lemma_condition == initial_lemma:
            try:
                if re.fullmatch(source_word_regex, original_word):
                    matched_lemma_from_regex1 = find_matching_override_in_context([override_rule], context_sentence)
                    if matched_lemma_from_regex1 is not None:
                        return matched_lemma_from_regex1
            except re.error as e:
                print(f"Warning: Invalid regex original word pattern: '{source_word_regex}'. Error: {e}", file=sys.stderr)

    priority2_rules = override_rules.get('priority2', {}).get(original_word)
    matched_lemma2 = find_matching_override_in_context(priority2_rules, context_sentence)
    if matched_lemma2 is not None:
        return matched_lemma2

    for source_word_regex, override_rule in override_rules.get('priority2_regex', []):
        try:
            if re.fullmatch(source_word_regex, original_word):
                matched_lemma_from_regex2 = find_matching_override_in_context([override_rule], context_sentence)
                if matched_lemma_from_regex2 is not None:
                    return matched_lemma_from_regex2
        except re.error as e:
            print(f"Warning: Invalid regex original word pattern: '{source_word_regex}'. Error: {e}", file=sys.stderr)

    priority3_rules = override_rules.get('priority3', {}).get(initial_lemma)
    matched_lemma3 = find_matching_override_in_context(priority3_rules, context_sentence)
    if matched_lemma3 is not None:
        return matched_lemma3
            
    return initial_lemma

def get_overridden_lemma_for_compound_part(initial_lemma, part, original_word, override_rules, context_sentence):
    priority1_rules = override_rules.get('priority1', {}).get((initial_lemma, original_word))
    matched_lemma1 = find_matching_override_in_context(priority1_rules, context_sentence)
    if matched_lemma1 is not None:
        return matched_lemma1

    for spacy_lemma_condition, source_word_regex, override_rule in override_rules.get('priority1_regex', []):
        if spacy_lemma_condition == initial_lemma:
            try:
                if re.fullmatch(source_word_regex, original_word):
                    matched_lemma_from_regex1 = find_matching_override_in_context([override_rule], context_sentence)
                    if matched_lemma_from_regex1 is not None:
                        return matched_lemma_from_regex1
            except re.error as e:
                print(f"Warning: Invalid regex original word pattern: '{source_word_regex}'. Error: {e}", file=sys.stderr)

    priority2_rules = override_rules.get('priority2', {}).get(part)
    matched_lemma2 = find_matching_override_in_context(priority2_rules, context_sentence)
    if matched_lemma2 is not None:
        return matched_lemma2

    for source_word_regex, override_rule in override_rules.get('priority2_regex', []):
        try:
            if re.fullmatch(source_word_regex, part):
                matched_lemma_from_regex2 = find_matching_override_in_context([override_rule], context_sentence)
                if matched_lemma_from_regex2 is not None:
                    return matched_lemma_from_regex2
        except re.error as e:
            print(f"Warning: Invalid regex original word pattern: '{source_word_regex}'. Error: {e}", file=sys.stderr)

    priority3_rules = override_rules.get('priority3', {}).get(initial_lemma)
    matched_lemma3 = find_matching_override_in_context(priority3_rules, context_sentence)
    if matched_lemma3 is not None:
        return matched_lemma3
            
    return initial_lemma

def lemmatize_compound_part(part, nlp_model, de_dictionary):
    if not part:
        return ""

    is_all_caps = part.isupper() and len(part) > 1
    has_internal_caps = any(c.isupper() for c in part[1:])

    if is_all_caps or has_internal_caps:
        return part

    part_document = nlp_model(part)
    if not part_document or len(part_document) == 0:
        return ""

    token = part_document[0]
    
    if token.pos_ not in ["NOUN", "PROPN"]:
        return token.lemma_
    
    spacy_lemma = token.lemma_.capitalize()
    capitalized_part = part.capitalize()

    if spacy_lemma in de_dictionary:
        return spacy_lemma

    if capitalized_part in de_dictionary:
        return capitalized_part

    return spacy_lemma

def correct_spacy_lemma(token, de_dictionary, fix_genitive=False):
    spacy_lemma = token.lemma_
    if (fix_genitive and
        nlp.lang == 'de' and
        token.pos_ in ["NOUN", "PROPN"] and
        'Gen' in token.morph.get("Case", [])):

        if spacy_lemma.endswith('s') and len(spacy_lemma) > 1:
            lemma_without_genitive_s = spacy_lemma[:-1]
            if lemma_without_genitive_s.capitalize() in de_dictionary:
                return lemma_without_genitive_s

    return spacy_lemma

def find_separable_verb_particle_pairs(document):
    particle_map = {}
    for token in document:
        if token.dep_ == "svp":
            particle_map[token.head.i] = token
    return particle_map

def load_lemma_frequency_index(file_path):
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

def read_text_from_file(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError:
        print(f"File not found: {file_path}", file=sys.stderr); exit(1)
    except Exception as e:
        print(f"Error reading file {file_path}: {e}", file=sys.stderr); exit(1)

def get_anki_csv_header():
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

def generate_filename_prefix_from_text(text, word_count):
    if not text:
        return ""
    normalized_text = text.lower()
    normalized_text = normalized_text.replace('ä', 'ae').replace('ö', 'oe').replace('ü', 'ue').replace('ß', 'ss')
    words = re.findall(r'[a-z0-9]+', normalized_text)
    prefix_words = words[:word_count]
    if not prefix_words:
        return ""
    return "-".join(prefix_words)

def format_lemma_capitalization(token, initial_lemma, args):
    if token.like_url or token.like_email:
        return initial_lemma.lower()

    source_token_text = token.text
    is_all_caps = source_token_text.isupper() and len(source_token_text) > 1
    has_internal_caps = any(c.isupper() for c in source_token_text[1:])

    if is_all_caps or has_internal_caps:
        return source_token_text
    
    if args.de_force_noun_capitalization and nlp.lang == 'de':
        if token.pos_ in ["NOUN", "PROPN"]:
            return initial_lemma.capitalize()
    
    if args.force_proper_noun_capitalization:
        if token.pos_ == "PROPN":
            return initial_lemma.capitalize()

    if token.is_sent_start and token.pos_ not in ["NOUN", "PROPN"]:
        return initial_lemma

    return initial_lemma

def deduplicate_lemmas(candidate_lemmas):
    lemmas_grouped_by_lowercase = {}
    for lemma in candidate_lemmas:
        if not lemma: continue
        lower_lemma = lemma.lower()
        if lower_lemma not in lemmas_grouped_by_lowercase:
            lemmas_grouped_by_lowercase[lower_lemma] = set()
        lemmas_grouped_by_lowercase[lower_lemma].add(lemma)
    
    final_lemmas = []
    for _, capitalization_variants in lemmas_grouped_by_lowercase.items():
        capitalized_variant = next((v for v in capitalization_variants if v[0].isupper()), None)
        
        if capitalized_variant:
            final_lemmas.append(capitalized_variant)
        elif capitalization_variants:
            final_lemmas.append(list(capitalization_variants)[0])
            
    return final_lemmas

def extract_lemmas_from_sentence(sentence_text, lemma_sort_index, nlp_model, de_dictionary, lemma_override_rules, de_gcs_pos_tags, args, **kwargs):
    de_gcs = kwargs.get('de_gcs', False)
    gcs_automaton = kwargs.get('gcs_automaton', None)
    de_gcs_add_parts_to_wordlist = kwargs.get('de_gcs_add_parts_to_wordlist', False)
    de_gcs_only_nouns = kwargs.get('de_gcs_only_nouns', True)
    de_gcs_combine_noun_modes = kwargs.get('de_gcs_combine_noun_modes', False)
    de_fix_genitive = kwargs.get('de_fix_genitive', False)
    de_gcs_mask_unknown_parts = kwargs.get('de_gcs_mask_unknown_parts', False)
    de_gcs_preserve_compound_word = kwargs.get('de_gcs_preserve_compound_word', False)
    de_gcs_skip_merge_fractions = kwargs.get('de_gcs_skip_merge_fractions', False)

    sentence_doc = nlp_model(sentence_text)
    final_lemmas = set()

    separable_verb_map = find_separable_verb_particle_pairs(sentence_doc)
    processed_particle_indices = {p.i for p in separable_verb_map.values()}

    for token in sentence_doc:
        if token.i in processed_particle_indices:
            continue

        if not (token.is_alpha or '-' in token.text):
            continue

        lemmas_for_current_token = []
        
        source_word_form = token.text
        base_lemma = ""
        if token.i in separable_verb_map:
            particle = separable_verb_map[token.i]
            default_lemma = f"{particle.text.lower()}{token.lemma_}".lower()
            source_word_form = f"{token.text} {particle.text}"
        else:
            spacy_lemma = correct_spacy_lemma(token, de_dictionary, de_fix_genitive)
            default_lemma = format_lemma_capitalization(token, spacy_lemma, args)
        base_lemma = get_overridden_lemma_for_word(default_lemma, source_word_form, lemma_override_rules, sentence_text)
        
        was_split = False
        is_special_token = token.like_url or token.like_email

        if de_gcs and '-' in token.text and not is_special_token:
            was_split = True
            hyphenated_parts = token.text.split('-')
            
            if de_gcs_preserve_compound_word:
                lemmas_for_current_token.append(base_lemma)

            for part in hyphenated_parts:
                part = part.strip()
                if not part or len(part) <= 1: continue

                initial_part_lemma = lemmatize_compound_part(part, nlp_model, de_dictionary)
                processed_part_lemma = get_overridden_lemma_for_compound_part(initial_part_lemma, part, token.text, lemma_override_rules, sentence_text)
                if processed_part_lemma:
                    lemmas_for_current_token.append(processed_part_lemma)

        elif de_gcs and gcs_automaton and nlp.lang == 'de' and not is_special_token and len(token.text) > 3 and (token.pos_ in de_gcs_pos_tags):
            try:
                word_to_split = token.text
                if args.de_gcs_part_singularization == 'none':
                    make_singular_flag = False
                elif args.de_gcs_part_singularization == 'all':
                    make_singular_flag = True
                else: 
                    make_singular_flag = (token.pos_ in ['NOUN', 'PROPN'])

                split_components = []
                if de_gcs_combine_noun_modes:
                    with redirect_stdout(io.StringIO()):
                        dissection1 = comp_split.dissect(word_to_split, gcs_automaton, make_singular=make_singular_flag, only_nouns=True, mask_unknown=de_gcs_mask_unknown_parts)
                    split_components.extend(comp_split.merge_fractions(dissection1))
                    with redirect_stdout(io.StringIO()):
                        dissection2 = comp_split.dissect(word_to_split, gcs_automaton, make_singular=make_singular_flag, only_nouns=False, mask_unknown=de_gcs_mask_unknown_parts)
                    split_components.extend(comp_split.merge_fractions(dissection2))

                    if de_gcs_skip_merge_fractions:
                        split_components.extend(dissection1)
                        split_components.extend(dissection2)
                    else:
                        split_components.extend(comp_split.merge_fractions(dissection1))
                        split_components.extend(comp_split.merge_fractions(dissection2))

                else:
                    with redirect_stdout(io.StringIO()):
                        dissection = comp_split.dissect(word_to_split, gcs_automaton, make_singular=make_singular_flag, only_nouns=de_gcs_only_nouns, mask_unknown=de_gcs_mask_unknown_parts)
                    
                    if de_gcs_skip_merge_fractions:
                        split_components = dissection
                    else:
                        split_components = comp_split.merge_fractions(dissection)

                if len(split_components) > 1:
                    was_split = True
                    if de_gcs_preserve_compound_word:
                        lemmas_for_current_token.append(base_lemma)
                        
                    for raw_component in set(split_components):
                        component = raw_component.strip('-')
                        if not component or len(component) < 3: continue
                        
                        initial_part_lemma = lemmatize_compound_part(component, nlp_model, de_dictionary)
                        overridden_part_lemma = get_overridden_lemma_for_compound_part(initial_part_lemma, component, token.text, lemma_override_rules, sentence_text)
                        processed_part_lemma = _format_gcs_component_case(overridden_part_lemma)

                        if processed_part_lemma:
                            lemmas_for_current_token.append(processed_part_lemma)
            except Exception:
                was_split = False
        
        if not was_split:
            lemmas_for_current_token.append(base_lemma)

        deduplicated_lemmas = deduplicate_lemmas(lemmas_for_current_token)
        for lemma in deduplicated_lemmas:
            final_lemmas.add(lemma)

    return sorted(list(final_lemmas), key=lambda x: (x not in lemma_sort_index, lemma_sort_index.get(x, 0), x.lower()))

def process_parallel_text_files(
    source_text_path, lemma_sort_index, language, target_text_path, tertiary_text_path, sentence_context_size,
    output_file_path, add_source_word_col, add_wordlist_col,
    add_header, wordlist_use_br, stdout_print_output_basename, de_gcs, gcs_automaton, de_gcs_add_parts_to_wordlist, de_dictionary, lemma_override_rules,
    de_gcs_pos_tags, args, **kwargs
):
    de_gcs_only_nouns = kwargs.get('de_gcs_only_nouns', True)
    de_gcs_combine_noun_modes = kwargs.get('de_gcs_combine_noun_modes', False)
    de_fix_genitive = kwargs.get('de_fix_genitive', False)
    de_gcs_mask_unknown_parts = kwargs.get('de_gcs_mask_unknown_parts', False)
    de_gcs_preserve_compound_word = kwargs.get('de_gcs_preserve_compound_word', False)
    de_gcs_skip_merge_fractions = kwargs.get('de_gcs_skip_merge_fractions', False)

    if "\n" in source_text_path or not os.path.exists(source_text_path):
        source_text_lines = source_text_path.splitlines()
    else:
        with open(source_text_path, "r", encoding="utf-8") as f1: source_text_lines = [line.rstrip("\n") for line in f1]

    if target_text_path:
        with open(target_text_path, "r", encoding="utf-8") as f2: target_text_lines = [line.rstrip("\n") for line in f2]

    tertiary_text_lines = []
    if tertiary_text_path:
        with open(tertiary_text_path, "r", encoding="utf-8") as f3: tertiary_text_lines = [line.rstrip("\n") for line in f3]

    lemma_to_shortest_form, lemma_to_sentence_info = {}, {}
    for i, source_sentence in enumerate(source_text_lines):
        doc = nlp(source_sentence)
        separable_verb_map = find_separable_verb_particle_pairs(doc)
        processed_particle_indices = {p.i for p in separable_verb_map.values()}

        for token in doc:
            if token.i in processed_particle_indices:
                continue

            if (token.is_alpha or '-' in token.text):
                lemmas_for_current_token = []
                
                source_word_form = token.text
                base_lemma = ""
                if token.i in separable_verb_map:
                    particle = separable_verb_map[token.i]
                    default_lemma = f"{particle.text.lower()}{token.lemma_}".lower()
                    source_word_form = f"{token.text} {particle.text}"
                else:
                    spacy_lemma = correct_spacy_lemma(token, de_dictionary, de_fix_genitive)
                    default_lemma = format_lemma_capitalization(token, spacy_lemma, args)
                base_lemma = get_overridden_lemma_for_word(default_lemma, source_word_form, lemma_override_rules, source_sentence)

                was_split = False
                is_special_token = token.like_url or token.like_email

                if de_gcs and '-' in token.text and not is_special_token:
                    was_split = True
                    hyphenated_parts = token.text.split('-')
                    
                    if de_gcs_preserve_compound_word:
                        lemmas_for_current_token.append(base_lemma)

                    for part in hyphenated_parts:
                        part = part.strip()
                        if not part or len(part) <= 1: continue

                        initial_part_lemma = lemmatize_compound_part(part, nlp, de_dictionary)
                        processed_part_lemma = get_overridden_lemma_for_compound_part(initial_part_lemma, part, token.text, lemma_override_rules, source_sentence)
                        if processed_part_lemma:
                            lemmas_for_current_token.append(processed_part_lemma)
                
                elif de_gcs and gcs_automaton and language == 'de' and not is_special_token and len(token.text) > 3 and (token.pos_ in de_gcs_pos_tags):
                    try:
                        word_to_split = token.text
                        if args.de_gcs_part_singularization == 'none':
                            make_singular_flag = False
                        elif args.de_gcs_part_singularization == 'all':
                            make_singular_flag = True
                        else:
                            make_singular_flag = (token.pos_ in ['NOUN', 'PROPN'])

                        split_components = []
                        if de_gcs_combine_noun_modes:
                            with redirect_stdout(io.StringIO()):
                                dissection1 = comp_split.dissect(word_to_split, gcs_automaton, make_singular=make_singular_flag, only_nouns=True, mask_unknown=de_gcs_mask_unknown_parts)
                            split_components.extend(comp_split.merge_fractions(dissection1))
                            with redirect_stdout(io.StringIO()):
                                dissection2 = comp_split.dissect(word_to_split, gcs_automaton, make_singular=make_singular_flag, only_nouns=False, mask_unknown=de_gcs_mask_unknown_parts)
                            split_components.extend(comp_split.merge_fractions(dissection2))

                            if de_gcs_skip_merge_fractions:
                                split_components.extend(dissection1)
                                split_components.extend(dissection2)
                            else:
                                split_components.extend(comp_split.merge_fractions(dissection1))
                                split_components.extend(comp_split.merge_fractions(dissection2))

                        else:
                            with redirect_stdout(io.StringIO()):
                                dissection = comp_split.dissect(word_to_split, gcs_automaton, make_singular=make_singular_flag, only_nouns=de_gcs_only_nouns, mask_unknown=de_gcs_mask_unknown_parts)
                            
                            if de_gcs_skip_merge_fractions:
                                split_components = dissection
                            else:
                                split_components = comp_split.merge_fractions(dissection)

                        if len(split_components) > 1:
                            was_split = True
                            if de_gcs_preserve_compound_word:
                                lemmas_for_current_token.append(base_lemma)

                            for raw_component in set(split_components):
                                component = raw_component.strip('-')
                                if not component: continue
                                if len(component) < 3: continue

                                initial_part_lemma = lemmatize_compound_part(component, nlp, de_dictionary)
                                overridden_part_lemma = get_overridden_lemma_for_compound_part(initial_part_lemma, component, token.text, lemma_override_rules, source_sentence)
                                processed_part_lemma = _format_gcs_component_case(overridden_part_lemma)
                                
                                if processed_part_lemma:
                                    lemmas_for_current_token.append(processed_part_lemma)
                    except Exception:
                        was_split = False
                
                if not was_split:
                    lemmas_for_current_token.append(base_lemma)

                deduplicated_lemmas = deduplicate_lemmas(lemmas_for_current_token)

                for lemma in deduplicated_lemmas:
                    if lemma:
                        if lemma not in lemma_to_shortest_form:
                            lemma_to_shortest_form[lemma] = source_word_form
                            lemma_to_sentence_info[lemma] = (i, source_sentence)
                        elif len(source_word_form) < len(lemma_to_shortest_form[lemma]):
                             lemma_to_shortest_form[lemma] = source_word_form

    sorted_words = sorted(list(lemma_to_shortest_form.keys()), key=lambda word: (word not in lemma_sort_index, lemma_sort_index.get(word, 0), word.lower()))
    if output_file_path:
        with open(output_file_path, "w", newline="", encoding="utf-8") as tsvfile:
            tsv_writer = csv.writer(tsvfile, delimiter="\t")
            if add_header:
                tsv_writer.writerow(get_anki_csv_header())

            for word in sorted_words:
                csv_row = [""] * 80
                sentence_index, source_sentence = lemma_to_sentence_info.get(word, (-1, ""))
                if sentence_index == -1: continue
                source_sentence = source_sentence.strip()
                target_sentence = target_text_lines[sentence_index].strip() if target_text_path and sentence_index < len(target_text_lines) else ""
                context_start_index, context_end_index = max(0, sentence_index - sentence_context_size), sentence_index + sentence_context_size + 1
                csv_row[5] = " ".join(line.strip() for line in source_text_lines[context_start_index:sentence_index])
                csv_row[6] = source_sentence
                csv_row[7] = " ".join(line.strip() for line in source_text_lines[sentence_index + 1:context_end_index])
                if target_text_path:
                    csv_row[8] = " ".join(line.strip() for line in target_text_lines[context_start_index:sentence_index])
                    csv_row[9] = target_sentence
                    csv_row[10] = " ".join(line.strip() for line in target_text_lines[sentence_index + 1:context_end_index])
                if tertiary_text_path:
                    csv_row[77] = " ".join(line.strip() for line in tertiary_text_lines[context_start_index:sentence_index])
                    csv_row[78] = tertiary_text_lines[sentence_index].strip() if sentence_index < len(tertiary_text_lines) else ""
                    csv_row[79] = " ".join(line.strip() for line in tertiary_text_lines[sentence_index + 1:context_end_index])
                csv_row[0] = word
                csv_row[1] = word
                if add_source_word_col:
                    csv_row[2] = lemma_to_shortest_form.get(word, '')
                csv_row[12] = source_sentence
                if add_wordlist_col:
                    wordlist_generation_args = {**kwargs, 'de_gcs': de_gcs, 'gcs_automaton': gcs_automaton, 'de_gcs_add_parts_to_wordlist': de_gcs_add_parts_to_wordlist}
                    lemmas = extract_lemmas_from_sentence(source_sentence, lemma_sort_index, nlp, de_dictionary, lemma_override_rules, de_gcs_pos_tags, args, **wordlist_generation_args)
                    csv_row[11] = "<br>".join(lemmas) if wordlist_use_br else "\n".join(lemmas)
                if language == "de":
                    csv_row[58] = "1"; csv_row[65] = "1"
                elif language == "en":
                    csv_row[56] = "1"; csv_row[65] = "1"
                tsv_writer.writerow(csv_row)
    return output_file_path

def process_single_text(
    source_text, lemma_sort_index, language, sentence_context_size,
    output_file_path, add_source_word_col, add_wordlist_col,
    add_header, wordlist_use_br, stdout_print_output_basename, de_gcs, gcs_automaton, de_gcs_add_parts_to_wordlist, de_dictionary, lemma_override_rules, 
    de_gcs_pos_tags, args, **kwargs
):
    de_gcs_only_nouns = kwargs.get('de_gcs_only_nouns', True)
    de_gcs_combine_noun_modes = kwargs.get('de_gcs_combine_noun_modes', False)
    de_fix_genitive = kwargs.get('de_fix_genitive', False)
    de_gcs_mask_unknown_parts = kwargs.get('de_gcs_mask_unknown_parts', False)
    de_gcs_preserve_compound_word = kwargs.get('de_gcs_preserve_compound_word', False)
    de_gcs_skip_merge_fractions = kwargs.get('de_gcs_skip_merge_fractions', False)

    if '\n' in source_text.strip():
        text_units = source_text.splitlines()
        is_processing_by_line = True
    else:
        doc = nlp(source_text)
        text_units = list(doc.sents)
        is_processing_by_line = False

    lemma_to_shortest_form, lemma_to_sentence_info = {}, {}

    for unit_index, text_unit in enumerate(text_units):
        unit_text = text_unit if is_processing_by_line else text_unit.text
        unit_doc = nlp(unit_text)

        separable_verb_map = find_separable_verb_particle_pairs(unit_doc)
        processed_particle_indices = {p.i for p in separable_verb_map.values()}

        for token in unit_doc:
            if token.i in processed_particle_indices:
                continue

            if (token.is_alpha or '-' in token.text):
                lemmas_for_current_token = []

                source_word_form = token.text
                base_lemma = ""
                if token.i in separable_verb_map:
                    particle = separable_verb_map[token.i]
                    default_lemma = f"{particle.text.lower()}{token.lemma_}".lower()
                    source_word_form = f"{token.text} {particle.text}"
                else:
                    spacy_lemma = correct_spacy_lemma(token, de_dictionary, de_fix_genitive)
                    default_lemma = format_lemma_capitalization(token, spacy_lemma, args)
                base_lemma = get_overridden_lemma_for_word(default_lemma, source_word_form, lemma_override_rules, unit_text)
                
                was_split = False
                is_special_token = token.like_url or token.like_email

                if de_gcs and '-' in token.text and not is_special_token:
                    was_split = True
                    hyphenated_parts = token.text.split('-')
                    
                    if de_gcs_preserve_compound_word:
                        lemmas_for_current_token.append(base_lemma)

                    for part in hyphenated_parts:
                        part = part.strip()
                        if not part or len(part) <= 1: continue

                        initial_part_lemma = lemmatize_compound_part(part, nlp, de_dictionary)
                        processed_part_lemma = get_overridden_lemma_for_compound_part(initial_part_lemma, part, token.text, lemma_override_rules, unit_text)
                        if processed_part_lemma:
                            lemmas_for_current_token.append(processed_part_lemma)
                
                elif de_gcs and gcs_automaton and language == 'de' and not is_special_token and len(token.text) > 3 and (token.pos_ in de_gcs_pos_tags):
                    try:
                        word_to_split = token.text
                        if args.de_gcs_part_singularization == 'none':
                            make_singular_flag = False
                        elif args.de_gcs_part_singularization == 'all':
                            make_singular_flag = True
                        else:
                            make_singular_flag = (token.pos_ in ['NOUN', 'PROPN'])
                            
                        split_components = []
                        if de_gcs_combine_noun_modes:
                            with redirect_stdout(io.StringIO()):
                                dissection1 = comp_split.dissect(word_to_split, gcs_automaton, make_singular=make_singular_flag, only_nouns=True, mask_unknown=de_gcs_mask_unknown_parts)
                            split_components.extend(comp_split.merge_fractions(dissection1))
                            with redirect_stdout(io.StringIO()):
                                dissection2 = comp_split.dissect(word_to_split, gcs_automaton, make_singular=make_singular_flag, only_nouns=False, mask_unknown=de_gcs_mask_unknown_parts)
                            split_components.extend(comp_split.merge_fractions(dissection2))

                            if de_gcs_skip_merge_fractions:
                                split_components.extend(dissection1)
                                split_components.extend(dissection2)
                            else:
                                split_components.extend(comp_split.merge_fractions(dissection1))
                                split_components.extend(comp_split.merge_fractions(dissection2))

                        else:
                            with redirect_stdout(io.StringIO()):
                                dissection = comp_split.dissect(word_to_split, gcs_automaton, make_singular=make_singular_flag, only_nouns=de_gcs_only_nouns, mask_unknown=de_gcs_mask_unknown_parts)
                            
                            if de_gcs_skip_merge_fractions:
                                split_components = dissection
                            else:
                                split_components = comp_split.merge_fractions(dissection)

                        if len(split_components) > 1:
                            was_split = True
                            if de_gcs_preserve_compound_word:
                                lemmas_for_current_token.append(base_lemma)
                            
                            for raw_component in set(split_components):
                                component = raw_component.strip('-')
                                if not component: continue
                                if len(component) < 3: continue

                                initial_part_lemma = lemmatize_compound_part(component, nlp, de_dictionary)
                                overridden_part_lemma = get_overridden_lemma_for_compound_part(initial_part_lemma, component, token.text, lemma_override_rules, unit_text)
                                processed_part_lemma = _format_gcs_component_case(overridden_part_lemma)

                                if processed_part_lemma:
                                    lemmas_for_current_token.append(processed_part_lemma)
                    except Exception:
                        was_split = False

                if not was_split:
                    lemmas_for_current_token.append(base_lemma)

                deduplicated_lemmas = deduplicate_lemmas(lemmas_for_current_token)

                for lemma in deduplicated_lemmas:
                    if lemma:
                        if lemma not in lemma_to_shortest_form:
                            lemma_to_shortest_form[lemma] = source_word_form
                            lemma_to_sentence_info[lemma] = (unit_index, text_unit)
                        elif len(source_word_form) < len(lemma_to_shortest_form[lemma]):
                             lemma_to_shortest_form[lemma] = source_word_form

    sorted_words = sorted(list(lemma_to_shortest_form.keys()), key=lambda word: (word not in lemma_sort_index, lemma_sort_index.get(word, 0), word.lower()))
    def get_unit_text(u):
        return u if is_processing_by_line else u.text

    if not output_file_path:
        if args.stdout_format == 'html':
            print("<table>", file=sys.stdout)
            for word in sorted_words:
                print(f"<tr><td>{word}</td><td>{lemma_to_shortest_form.get(word, '')}</td></tr>", file=sys.stdout)
            print("</table>", file=sys.stdout)
        elif args.stdout_format == 'tsv':
            for word in sorted_words:
                print(f"{word}\t{lemma_to_shortest_form.get(word, '')}", file=sys.stdout)
        elif args.stdout_format == 'context':
             for word in sorted_words:
                unit_index, source_sentence_unit = lemma_to_sentence_info[word]
                source_sentence = get_unit_text(source_sentence_unit)
                context_start_index = max(0, unit_index - sentence_context_size)
                context_end_index = min(len(text_units), unit_index + sentence_context_size + 1)
                source_context_left = " ".join(get_unit_text(u).strip() for u in text_units[context_start_index:unit_index])
                source_context_right = " ".join(get_unit_text(u).strip() for u in text_units[unit_index + 1:context_end_index])
                print(word, file=sys.stdout)
                if source_context_left: print(source_context_left, file=sys.stdout)
                print(source_sentence.strip(), file=sys.stdout)
                if source_context_right: print(source_context_right, file=sys.stdout)
                print(file=sys.stdout)
        else:
            for word in sorted_words:
                print(word, file=sys.stdout)
        return None

    with open(output_file_path, "w", newline="", encoding="utf-8") as tsvfile:
        tsv_writer = csv.writer(tsvfile, delimiter="\t")
        if add_header:
            tsv_writer.writerow(get_anki_csv_header())

        for word in sorted_words:
            csv_row = [""] * 80
            unit_index, source_sentence_unit = lemma_to_sentence_info.get(word, (-1, ""))
            if unit_index == -1: continue
            
            source_sentence = get_unit_text(source_sentence_unit).strip()
            context_start_index = max(0, unit_index - sentence_context_size)
            context_end_index = min(len(text_units), unit_index + sentence_context_size + 1)
            csv_row[5] = " ".join(get_unit_text(u).strip() for u in text_units[context_start_index:unit_index])
            csv_row[6] = source_sentence
            csv_row[7] = " ".join(get_unit_text(u).strip() for u in text_units[unit_index + 1:context_end_index])
            csv_row[0] = word
            csv_row[1] = word
            if add_source_word_col:
                csv_row[2] = lemma_to_shortest_form.get(word, '')
            csv_row[12] = source_sentence
            if add_wordlist_col:
                wordlist_generation_args = {**kwargs, 'de_gcs': de_gcs, 'gcs_automaton': gcs_automaton, 'de_gcs_add_parts_to_wordlist': de_gcs_add_parts_to_wordlist}
                lemmas = extract_lemmas_from_sentence(source_sentence, lemma_sort_index, nlp, de_dictionary, lemma_override_rules, de_gcs_pos_tags, args, **wordlist_generation_args)
                csv_row[11] = "<br>".join(lemmas) if wordlist_use_br else "\n".join(lemmas)
            if language == "de":
                csv_row[58] = "1"; csv_row[65] = "1"
            elif language == "en":
                csv_row[56] = "1"; csv_row[65] = "1"
            tsv_writer.writerow(csv_row)

    return output_file_path

def process_parallel_sentences_to_csv(
    language, lemma_sort_index, source_text_path, target_text_path, tertiary_text_path, sentence_context_size,
    output_file_path, add_wordlist_col, add_header, wordlist_use_br, stdout_print_output_basename, de_gcs_pos_tags, args, **kwargs
):
    lemma_override_rules = kwargs.pop('lemma_override_rules', {})
    
    try:
        with open(source_text_path, "r", encoding="utf-8") as f: source_text_lines = [line.rstrip("\n") for line in f]
        with open(target_text_path, "r", encoding="utf-8") as f: target_text_lines = [line.rstrip("\n") for line in f]
        tertiary_text_lines = []
        if tertiary_text_path:
            with open(tertiary_text_path, "r", encoding="utf-8") as f: tertiary_text_lines = [line.rstrip("\n") for line in f]
    except IOError as e:
        print(f"Error reading files: {e}", file=sys.stderr); sys.exit(1)

    lengths = [len(source_text_lines), len(target_text_lines)]
    if tertiary_text_path: lengths.append(len(tertiary_text_lines))
    min_length = min(lengths)

    with open(output_file_path, "w", newline="", encoding="utf-8") as output_csv_file:
        tsv_writer = csv.writer(output_csv_file, delimiter="\t")
        if add_header:
            tsv_writer.writerow(get_anki_csv_header())

        for i in range(min_length):
            csv_row = [""] * 80
            source_sentence = source_text_lines[i].strip()
            target_sentence = target_text_lines[i].strip()
            context_start_index, context_end_index = max(0, i - sentence_context_size), i + sentence_context_size + 1
            csv_row[0] = source_sentence
            csv_row[5] = " ".join(line.strip() for line in source_text_lines[context_start_index:i])
            csv_row[6] = source_sentence
            csv_row[7] = " ".join(line.strip() for line in source_text_lines[i + 1:context_end_index])
            csv_row[8] = " ".join(line.strip() for line in target_text_lines[context_start_index:i])
            csv_row[9] = target_sentence
            csv_row[10] = " ".join(line.strip() for line in target_text_lines[i + 1:context_end_index])
            if add_wordlist_col:
                lemmas = extract_lemmas_from_sentence(source_sentence, lemma_sort_index, nlp, de_dictionary, lemma_override_rules, de_gcs_pos_tags, args, **kwargs)
                csv_row[11] = "<br>".join(lemmas) if wordlist_use_br else "\n".join(lemmas)
            csv_row[12] = source_sentence
            if tertiary_text_path:
                csv_row[77] = " ".join(line.strip() for line in tertiary_text_lines[context_start_index:i])
                csv_row[78] = tertiary_text_lines[i].strip()
                csv_row[79] = " ".join(line.strip() for line in tertiary_text_lines[i + 1:context_end_index])
            if language == "de":
                csv_row[58] = "1"; csv_row[65] = "1"
            elif language == "en":
                csv_row[56] = "1"; csv_row[65] = "1"
            tsv_writer.writerow(csv_row)
    return output_file_path

def main():
    parser = argparse.ArgumentParser(
        description="Extract and process words or sentences from text.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    input_output_group = parser.add_argument_group('Input & Output')
    input_output_group.add_argument("--type", required=True, choices=["word", "sentence"], help="Specify the processing type: 'word' for word extraction, 'sentence' for parallel sentence processing.")
    input_output_group.add_argument("--language", default="de", choices=["de", "en"], help="The language of the text to be processed.")
    input_output_group.add_argument("--text", help="A single string of input text to process. Mutually exclusive with --text1-file.")
    input_output_group.add_argument("--text1-file", help="Path to the primary input text file.")
    input_output_group.add_argument("--text2-file", help="Path to a parallel (translated) text file.")
    input_output_group.add_argument("--text3-file", help="Path to a third parallel text file.")
    input_output_group.add_argument("--output-file", help="Path to the output file. If not provided, results are printed to standard output.")

    data_files_group = parser.add_argument_group('Data Files')
    data_files_group.add_argument("--lemma-index-file", default="", help="Path to a CSV file with lemmas, used for frequency-based sorting of the output.")
    data_files_group.add_argument("--lemma-override-file", help="Path to a TSV file that defines rules for correcting specific lemma results.")
    data_files_group.add_argument("--de-dictionary-file", default="german.dic", help="Path to the dictionary file for German-specific operations.")

    filename_group = parser.add_argument_group('Output Filename Generation')
    filename_group.add_argument("--basename-add-timestamp", action="store_true", help="Prepend the output filename with a 'YYYYMMDDHHMMSS' timestamp.")
    filename_group.add_argument("--basename-add-first-words", nargs='?', type=int, const=4, default=None, help="Automatically generate part of the filename from the first N words of the text. Defaults to 4 words if no number is given.")
    filename_group.add_argument("--stdout-print-output-basename", action="store_true", help="Print the basename of the generated output file to stdout. Useful for scripting.")

    output_format_group = parser.add_argument_group('Output Content & Formatting')
    output_format_group.add_argument("--add-source-word-col", action="store_true", help="In the output file, add a column with the original, inflected source word for each lemma.")
    output_format_group.add_argument("--add-wordlist-col", action="store_true", help="For each entry, add a field containing all unique lemmas from the source sentence.")
    output_format_group.add_argument("--wordlist-use-br", action="store_true", help="Use HTML <br> tags instead of newlines as separators in the wordlist column. Requires --add-wordlist-col.")
    output_format_group.add_argument("--add-header", action="store_true", help="Prepend the output file with the full Anki CSV header.")
    output_format_group.add_argument("--sentence-context-size", type=int, default=1, help="The number of sentences to include before and after the source sentence as context.")
    stdout_group = parser.add_argument_group('Standard Output (STDOUT) Arguments (used only if --output is not specified)')
    output_format_group.add_argument("--stdout-format", choices=['list', 'context', 'tsv', 'html'], default='list', 
                               help="Select the output format for STDOUT if --output-file is not specified.\n"
                                    "'list' (default): A simple, one-lemma-per-line list.\n"
                                    "'context': Lemmas with full sentence context.\n"
                                    "'tsv': A two-column list (lemma, source word) separated by a tab.\n"
                                    "'html': The two-column list formatted as an HTML table.")

    lemmatization_group = parser.add_argument_group('Lemmatization Control')
    lemmatization_group.add_argument("--force-proper-noun-capitalization", action="store_true", help="Force capitalization of proper noun lemmas (PROPN).")
    de_group = parser.add_argument_group('German Language Specific Arguments')
    de_group.add_argument("--de-fix-genitive", action="store_true", help="[German] Corrects genitive noun lemmas (e.g., 'Hauses' -> 'Haus') by checking against the dictionary.")
    de_group.add_argument("--de-force-noun-capitalization", action="store_true", help="[German only] Force capitalization of all noun lemmas (NOUN, PROPN) as per German orthography rules. Overrides --force-proper-noun-capitalization for German.")

    gcs_group = parser.add_argument_group('German Compound Splitting (GCS)')
    gcs_group.add_argument("--de-gcs", action="store_true", help="Enable German Compound Splitting (GCS).")
    gcs_group.add_argument(
        "--de-gcs-pos-tags", 
        nargs='+', 
        default=['NOUN PRON ADV ADJ'],
        help='''Specify which Part-of-Speech tags to apply splitting to.

  Default: NOUN PROPN ADV ADJ

  This argument operates in two main modes:

  1. INCLUSION MODE (default behavior):
     List the specific tags you want to process.
     Example: --de-gcs-pos-tags NOUN PROPN ADJ

  2. EXCLUSION MODE:
     Prefix tags with '!' to process all tags except the ones specified.
     Example: --de-gcs-pos-tags !VERB !AUX
     (This splits everything except verbs and auxiliary verbs)

  PRECEDENCE RULE:
     If even one tag is prefixed with '!', the mode switches to exclusion.
     Any tags listed without '!' in the same command will be ignored.
     For instance, '--de-gcs-pos-tags NOUN !VERB' is treated as just '!VERB'.

  SPECIAL KEYWORD:
     ALL - A shortcut to process all available tags.

  Available Tags (Universal Dependencies):
    ADJ   - Adjective (Adjektiv; e.g., groß, alt, schön)
    ADP   - Adposition (Präposition; e.g., in, zu, auf, mit)
    ADV   - Adverb (Adverb; e.g., schnell, sehr, hier)
    AUX   - Auxiliary verb (Hilfsverb; e.g., sein, haben, werden, können)
    CCONJ - Coordinating Conjunction (Konjunktion; e.g., und, aber, oder)
    DET   - Determiner (Artikel/Demonstrativpronomen; e.g., der, eine, dieser)
    INTJ  - Interjection (Interjektion; e.g., ach, hallo, oje)
    NOUN  - Noun (Nomen/Substantiv; e.g., Haus, Tisch, Buch)
    NUM   - Numeral (Numerale; e.g., eins, zwei, 100)
    PART  - Particle (Partikel; e.g., nicht, zu bei Infinitiv, ja)
    PRON  - Pronoun (Pronomen; e.g., ich, du, er, sie)
    PROPN - Proper Noun (Eigenname; e.g., Peter, Berlin, Google)
    PUNCT - Punctuation (Interpunktion; e.g., ., ,, ?, !)
    SCONJ - Subordinating Conjunction (Subjunktion; e.g., dass, weil, wenn)
    SYM   - Symbol (Symbol; e.g., €, %%, §)
    VERB  - Verb (Verb; e.g., gehen, sagen, machen)
    X     - Other (Sonstiges; e.g., Fremdwörter, Tippfehler)'''
    )
    gcs_group.add_argument("--de-gcs-split-mode", choices=['only-nouns', 'any', 'combined'], default='only-nouns', help="[GCS] Set the splitting mode: 'only-nouns' (safe), 'any' (aggressive), or 'combined'.")
    gcs_group.add_argument("--de-gcs-mask-unknown-parts", action="store_true", help="[GCS] Mask word parts not found in the dictionary during splitting.")
    gcs_group.add_argument("--de-gcs-part-singularization", choices=['only-nouns', 'all', 'none'], default='only-nouns', help="[GCS] Controls singularization of compound parts.")
    gcs_group.add_argument("--de-gcs-preserve-compound-word", action="store_true", help="[GCS] Keep the original compound word in the lemma list along with its parts.")
    gcs_group.add_argument("--de-gcs-add-parts-to-wordlist", action="store_true", help="[GCS] Add split compound parts to the sentence wordlist. Requires --add-wordlist-col.")
    gcs_group.add_argument("--de-gcs-skip-merge-fractions", action="store_true", help="[GCS] Disable merging of components, outputting raw parts from dissection.")

    args = parser.parse_args()

    ALL_POS_TAGS = {'ADJ', 'ADP', 'ADV', 'AUX', 'CCONJ', 'DET', 'INTJ', 'NOUN', 
                    'NUM', 'PART', 'PRON', 'PROPN', 'PUNCT', 'SCONJ', 'SYM', 'VERB', 'X'}

    user_tags = args.de_gcs_pos_tags
    has_negation = any(tag.startswith('!') for tag in user_tags)
    gcs_target_pos_tags = set()

    if has_negation:
        excluded_tags = {tag[1:] for tag in user_tags if tag.startswith('!')}
        gcs_target_pos_tags = ALL_POS_TAGS - excluded_tags
    elif 'ALL' in user_tags:
        gcs_target_pos_tags = ALL_POS_TAGS
    else:
        gcs_target_pos_tags = set(user_tags)

    args.de_gcs_pos_tags = list(gcs_target_pos_tags)

    if args.de_gcs and args.language != 'de':
        print("Warning: GCS is designed for German language (--language de). The --de-gcs flag will be ignored.", file=sys.stderr)
        args.de_gcs = False
    if args.de_gcs_add_parts_to_wordlist and not args.de_gcs:
        print("Error: --de-gcs-add-parts-to-wordlist requires --de-gcs to be enabled.", file=sys.stderr); exit(1)
    if args.de_gcs_preserve_compound_word and not args.de_gcs:
        print("Error: --de-gcs-preserve-compound-word requires --de-gcs to be enabled.", file=sys.stderr); exit(1)

    global nlp
    nlp = spacy.load("de_core_news_lg" if args.language == "de" else "en_core_web_lg")

    lemma_override_rules = load_lemma_override_rules(args.lemma_override_file) if args.lemma_override_file else {}

    gcs_automaton = None
    global de_dictionary
    de_dictionary = set()
    if args.language == 'de':
        de_dictionary = load_dictionary(args.de_dictionary_file)
        if not de_dictionary:
             print("Warning: German dictionary for validation is empty or not loaded.", file=sys.stderr)

        if args.de_gcs:
            if not GCS_AVAILABLE:
                print("Error: 'german-compound-splitter' library not installed. Please run 'pip install german-compound-splitter'.", file=sys.stderr); exit(1)
            if not os.path.exists(args.de_dictionary_file):
                print(f"Error: GCS dictionary file '{args.de_dictionary_file}' not found!", file=sys.stderr); exit(1)
            try:
                with redirect_stdout(io.StringIO()):
                    gcs_automaton = comp_split.read_dictionary_from_file(args.de_dictionary_file)
            except Exception as e:
                print(f"Error loading GCS dictionary: {e}", file=sys.stderr); exit(1)

    lemma_index = load_lemma_frequency_index(args.lemma_index_file)
    processed_output_file = None
    final_output_path = args.output_file
    
    if args.output_file and (args.basename_add_timestamp or args.basename_add_first_words is not None):
        timestamp_id = datetime.now().strftime('%Y%m%d%H%M%S')
        output_directory, filename = os.path.dirname(args.output_file) or '.', os.path.basename(args.output_file)

        if args.basename_add_first_words is not None:
            text_for_filename_prefix = ""
            if args.text:
                text_for_filename_prefix = args.text
            elif args.text1_file:
                try:
                    with open(args.text1_file, 'r', encoding='utf-8') as f:
                        text_for_filename_prefix = f.read(1024)
                except Exception as e:
                    print(f"Warning: Could not read {args.text1_file} for autonaming: {e}", file=sys.stderr)
            filename_prefix = generate_filename_prefix_from_text(text_for_filename_prefix, args.basename_add_first_words)
            if filename_prefix:
                extension_dot_position = filename.find('.')
                file_extension = filename[extension_dot_position:] if extension_dot_position != -1 else ""
                new_filename = f"{timestamp_id}-{filename_prefix}{file_extension}"
            else:
                 new_filename = f"{timestamp_id}-{filename}"
            final_output_path = os.path.join(output_directory, new_filename)
        elif args.basename_add_timestamp:
            new_filename = f"{timestamp_id}-{filename}"
            final_output_path = os.path.join(output_directory, new_filename)
            
    if args.type == "word":
        if args.text and args.text1_file:
            print("Error: --text and --text1-file are mutually exclusive.", file=sys.stderr); exit(1)

        input_text = ""
        if args.text:
            input_text = args.text
        elif args.text1_file:
            input_text = read_text_from_file(args.text1_file)
        elif 'KARDENWORT_INPUT_TEXT' in os.environ:
            input_text = os.environ['KARDENWORT_INPUT_TEXT']
        elif not sys.stdin.isatty():
            input_text = sys.stdin.read()

        if not input_text:
            print("Error: No input provided. Use --text, --text1-file, environment variable, or pipe data via stdin.", file=sys.stderr); exit(1)
        processing_options = {
            'de_gcs_only_nouns': (args.de_gcs_split_mode == 'only-nouns'),
            'de_gcs_combine_noun_modes': (args.de_gcs_split_mode == 'combined'),
            'de_fix_genitive': args.de_fix_genitive,
            'de_gcs_mask_unknown_parts': args.de_gcs_mask_unknown_parts,
            'de_gcs_preserve_compound_word': args.de_gcs_preserve_compound_word,
            'de_gcs_skip_merge_fractions': args.de_gcs_skip_merge_fractions,
        }

        if args.text2_file:
            processed_output_file = process_parallel_text_files(
                input_text, lemma_index, args.language, args.text2_file, args.text3_file,
                args.sentence_context_size, final_output_path,
                args.add_source_word_col, args.add_wordlist_col,
                args.add_header, args.wordlist_use_br, args.stdout_print_output_basename,
                args.de_gcs, gcs_automaton, args.de_gcs_add_parts_to_wordlist, de_dictionary, lemma_override_rules,
                args.de_gcs_pos_tags, args, **processing_options
            )
        else:
             processed_output_file = process_single_text(
                input_text, lemma_index, args.language, args.sentence_context_size,
                final_output_path, args.add_source_word_col, args.add_wordlist_col,
                args.add_header, args.wordlist_use_br, args.stdout_print_output_basename,
                args.de_gcs, gcs_automaton, args.de_gcs_add_parts_to_wordlist, de_dictionary, lemma_override_rules,
                args.de_gcs_pos_tags, args, **processing_options
            )

    elif args.type == "sentence":
        if any([args.de_gcs, args.de_gcs_mask_unknown_parts]):
            print("Warning: GCS-related flags are only applicable for --type word and will be ignored.", file=sys.stderr)
        if not args.text1_file or not args.text2_file:
            print("Error: --text1-file and --text2-file must be specified for sentence mode.", file=sys.stderr); exit(1)
        
        processing_options = {
            'lemma_override_rules': lemma_override_rules,
            'de_gcs': args.de_gcs,
            'gcs_automaton': gcs_automaton,
            'de_gcs_add_parts_to_wordlist': args.de_gcs_add_parts_to_wordlist,
            'de_gcs_only_nouns': (args.de_gcs_split_mode == 'only-nouns'),
            'de_gcs_combine_noun_modes': (args.de_gcs_split_mode == 'combined'),
            'de_fix_genitive': args.de_fix_genitive,
            'de_gcs_mask_unknown_parts': args.de_gcs_mask_unknown_parts,
            'de_gcs_preserve_compound_word': args.de_gcs_preserve_compound_word,
            'de_gcs_skip_merge_fractions': args.de_gcs_skip_merge_fractions,
        }
        processed_output_file = process_parallel_sentences_to_csv(
            args.language, lemma_index, args.text1_file, args.text2_file, args.text3_file,
            args.sentence_context_size, final_output_path,
            args.add_wordlist_col, args.add_header, args.wordlist_use_br, args.stdout_print_output_basename,
            args.de_gcs_pos_tags, args, **processing_options
        )

    if args.stdout_print_output_basename and processed_output_file:
        print(os.path.basename(processed_output_file), file=sys.stdout)

if __name__ == "__main__":
    main()