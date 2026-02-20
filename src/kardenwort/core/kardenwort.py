import sys
import spacy
import csv
import argparse
from datetime import datetime
import os
import re
from contextlib import redirect_stdout
import io
import json
import tempfile
import atexit

try:
    from german_compound_splitter import comp_split
    GCS_AVAILABLE = True
except ImportError:
    GCS_AVAILABLE = False

# List to hold the paths of temporary files to be cleaned up on exit.
TEMP_FILES_TO_CLEANUP = []

def _cleanup_temp_files():
    """Remove any temporary files created during execution."""
    for f_path in TEMP_FILES_TO_CLEANUP:
        try:
            os.remove(f_path)
        except OSError:
            pass  # Ignore errors if the file doesn't exist

# Register the cleanup function to be called upon script exit.
atexit.register(_cleanup_temp_files)




def _strip_markdown_header(line):
    """Removes Markdown header prefixes (#, ##, etc.) from a line."""
    match = re.match(r'^(#+)\s+(.*)', line.strip())
    return match.group(2).strip() if match else line

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

def get_anki_csv_header(header_override=None):
    if header_override:
        return header_override
    # This should technically never be reached in strict mode, but we keep it
    # for internal unit tests or if called without an override.
    return [
        "Quotation", "WordSource", "WordSourceInflectedForm", "WordDestination",
        "WordSourceContext", "SentenceSourceContextLeft", "SentenceSource",
        "SentenceSourceContextRight", "SentenceDestinationContextLeft",
        "SentenceDestination", "SentenceDestinationContextRight",
        "SentenceDestination2ContextLeft", "SentenceDestination2",
        "SentenceDestination2ContextRight", "SentenceSourceWordlist",
        "SentenceSourceCloze", "SentenceSourceRewriteAISentenceSource",
        "SentenceSourceRewriteAISentenceDestination", "WordSourceMorphologyAI",
        "Note", "WordRussian", "WordUkrainian", "WordEnglish", "WordGerman",
        "WordSourceMorphemeFirst", "WordSourceMorphemeFirstDefinition",
        "WordSourceMorphemeSecond", "WordSourceMorphemeSecondDefinition",
        "WordSourceMorphemeThird", "WordSourceMorphemeThirdDefinition",
        "WordSourceMorphemeFourth", "WordSourceMorphemeFourthDefinition",
        "WordSourceMorphemeFifth", "WordSourceMorphemeFifthDefinition",
        "WordSourceIPA", "WordSourceSynonymAI", "WordSourceDefinitionAISentenceSource",
        "WordSourceDefinitionAISentenceDestination", "WordSourceDefinitionFirst",
        "WordSourceDefinitionFirstClipping", "WordSourceDefinitionSecond",
        "WordDestinationDefinitionFirst", "WordDestinationDefinitionSecond",
        "WordSourceAudio", "SentenceSourceIPA", "SentenceSourceAudio", "Image",
        "WordSourceCloze", "WordSourceContextAI", "TextSource", "TextDestination",
        "TextSourceURL", "SentenceEnglish", "SentenceGerman", "SentenceUkrainian",
        "SentenceRussian", "Source", "SourceURL", "SeparatorAudio", "Source-en-GB",
        "Source-en-US", "Source-de-DE", "Source-uk-UA", "Source-ru-RU",
        "Destination-en-GB", "Destination-en-US", "Destination-de-DE",
        "Destination-uk-UA", "Destination-ru-RU", "Overlapping",
        "ToggleAlwaysEmptyField", "Note ID", "am-all-morphs", "am-all-morphs-count",
        "am-unknown-morphs", "am-unknown-morphs-count", "am-highlighted",
        "am-score", "am-score-terms", "am-study-morphs", "SentenceSourceIndex",
        "Deck", "WordDestinationInflectedForm", "WordSourceAI", "WordSourceInflectedFormAI"
    ]

def get_field_index_map(header_override=None):
    """Returns a dict mapping each header field name to its 0-based index."""
    return {name: i for i, name in enumerate(get_anki_csv_header(header_override))}

def prepare_row_data(args, **kwargs):
    """Consolidates all possibly mapped data into a single dictionary."""
    row_data = {
        'lemma': kwargs.get('lemma', ''),
        'source_word': kwargs.get('source_word', ''),
        'source_sentence': kwargs.get('source_sentence', ''),
        'source_context_left': kwargs.get('source_context_left', ''),
        'source_context_right': kwargs.get('source_context_right', ''),
        'target_sentence': kwargs.get('target_sentence', ''),
        'target_context_left': kwargs.get('target_context_left', ''),
        'target_context_right': kwargs.get('target_context_right', ''),
        'tertiary_sentence': kwargs.get('tertiary_sentence', ''),
        'tertiary_context_left': kwargs.get('tertiary_context_left', ''),
        'tertiary_context_right': kwargs.get('tertiary_context_right', ''),
        'wordlist': kwargs.get('wordlist', ''),
        'cloze': kwargs.get('cloze', ''),
        'sentence_index': kwargs.get('sentence_index', ''),
        'deck_name': kwargs.get('deck_name', ''),
    }
    
    # Dynamic TTS activation flags
    if args.language:
        row_data[f'tts_source_{args.language}'] = "1"
    if args.tts_destination_lang:
        row_data[f'tts_dest_{args.tts_destination_lang}'] = "1"
        
    return row_data

def apply_field_mapping(csv_row, row_data, field_mapping, field_index_map):
    """Applies a field mapping to override csv_row values using row_data.
    
    Args:
        csv_row: The list representing a TSV row (modified in-place).
        row_data: Dict of {internal_name: value} with all available data sources.
        field_mapping: Dict of {anki_field_name: internal_data_source_name} from config.
        field_index_map: Dict of {anki_field_name: column_index}.
    """
    if not field_mapping:
        return
    for field_name, data_source in field_mapping.items():
        if field_name in field_index_map:
            csv_row[field_index_map[field_name]] = row_data.get(data_source, "")
        else:
            print(f"Warning: Unknown field '{field_name}' in anki_field_mapping, skipping.", file=sys.stderr)

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

def parse_markdown_for_branch_headers(all_lines):
    branch_header_indices = set()
    last_header_level = 0
    last_header_index = -1
    for i, line in enumerate(all_lines):
        line = line.strip()
        if line.startswith('#'):
            match = re.match(r'^(#+)', line)
            current_level = len(match.group(1))
            if current_level > last_header_level and last_header_index != -1:
                branch_header_indices.add(last_header_index)
            last_header_level = current_level
            last_header_index = i
    return branch_header_indices

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

def _write_deck_metadata(args, output_file_path, source_text_content, target_text_content=None, tertiary_text_content=None, subdeck_content_map=None):
    if not args.anki_deck_content:
        return

    deck_descriptions = {}
    parent_deck_name = ""
    root_deck_prefix = ""

    if args.anki_markdown_decks:
        if args.anki_create_subdecks:
            if args.anki_parent_deck:
                root_deck_prefix = args.anki_parent_deck
            elif output_file_path:
                base_name = os.path.splitext(os.path.basename(output_file_path))[0]
                root_deck_prefix = re.sub(r'\.(word|sentence)', '', base_name)
        parent_deck_name = root_deck_prefix
    else:
        if args.anki_create_subdecks:
            sub_deck_name = os.path.splitext(os.path.basename(output_file_path))[0]
            if args.anki_parent_deck:
                parent_deck_name = args.anki_parent_deck
            else:
                parent_deck_name = re.sub(r'\.(word|sentence)', '', sub_deck_name)
        else:
            parent_deck_name = os.path.splitext(os.path.basename(output_file_path))[0]
    
    if parent_deck_name:
        description_parts = []
        
        if 'parent-source' in args.anki_deck_content and source_text_content:
            normalized_source = source_text_content.replace('\r\n', '\n')
            description_parts.append(normalized_source.strip())

        if 'parent-translations' in args.anki_deck_content:
            if target_text_content and target_text_content.strip():
                normalized_target = target_text_content.replace('\r\n', '\n')
                description_parts.append(normalized_target.strip())
            if tertiary_text_content and tertiary_text_content.strip():
                normalized_tertiary = tertiary_text_content.replace('\r\n', '\n')
                description_parts.append(normalized_tertiary.strip())
        
        if description_parts:
            deck_descriptions[parent_deck_name] = "\n\n---\n\n".join(description_parts)

    if subdeck_content_map and ('subdeck-source' in args.anki_deck_content or 'subdeck-translations' in args.anki_deck_content):
        for deck_name, content_data in subdeck_content_map.items():
            if not deck_name: continue

            if deck_name == parent_deck_name and parent_deck_name in deck_descriptions:
                            continue

            subdeck_description_parts = []
            if 'subdeck-source' in args.anki_deck_content:
                source_part = "\n".join(content_data.get('source_lines', []))
                if source_part: subdeck_description_parts.append(source_part)

            if 'subdeck-translations' in args.anki_deck_content:
                translation1_part = "\n".join(content_data.get('translation1_lines', []))
                if translation1_part: subdeck_description_parts.append(translation1_part)
                
                translation2_part = "\n".join(content_data.get('translation2_lines', []))
                if translation2_part: subdeck_description_parts.append(translation2_part)

            if subdeck_description_parts:
                deck_descriptions[deck_name] = "\n\n---\n\n".join(subdeck_description_parts)

    if not deck_descriptions:
        return

    metadata = {"deck_descriptions": deck_descriptions}
    
    metadata_path = os.path.splitext(output_file_path)[0] + '.json'
    try:
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
    except IOError as e:
        print(f"Warning: Could not write metadata file to {metadata_path}: {e}", file=sys.stderr)

def process_parallel_text_files(
    source_text, lemma_sort_index, language, target_text_path, tertiary_text_path,
    sentence_context_size, output_file_path, add_source_word_col, add_wordlist_col,
    add_sentence_index_col, add_header, wordlist_use_br, stdout_print_output_basename,
    de_gcs, gcs_automaton, de_gcs_add_parts_to_wordlist, de_dictionary,
    lemma_override_rules, de_gcs_pos_tags, field_mapping, anki_header, args, **kwargs
):
    de_gcs_only_nouns = kwargs.get('de_gcs_only_nouns', True)
    de_gcs_combine_noun_modes = kwargs.get('de_gcs_combine_noun_modes', False)
    de_fix_genitive = kwargs.get('de_fix_genitive', False)
    de_gcs_mask_unknown_parts = kwargs.get('de_gcs_mask_unknown_parts', False)
    de_gcs_preserve_compound_word = kwargs.get('de_gcs_preserve_compound_word', False)
    de_gcs_skip_merge_fractions = kwargs.get('de_gcs_skip_merge_fractions', False)
    sentence_lemmas_cache = {}
    doc_cache = {}

    source_text_lines_all = [line.rstrip("\n") for line in source_text.splitlines()]

    target_content_lines_all = []
    if target_text_path:
        with open(target_text_path, "r", encoding="utf-8") as f2:
            target_content_lines_all = [line.rstrip("\n") for line in f2]
    
    tertiary_content_lines_all = []
    if tertiary_text_path:
        with open(tertiary_text_path, "r", encoding="utf-8") as f3:
            tertiary_content_lines_all = [line.rstrip("\n") for line in f3]

    strip_config = {'source': False, 'translations': False}
    if args.strip_headers is not None:
        targets = args.strip_headers if args.strip_headers else ['all']
        if 'all' in targets or 'source' in targets:
            strip_config['source'] = True
        if 'all' in targets or 'translations' in targets:
            strip_config['translations'] = True

    display_source_lines_all = [_strip_markdown_header(line) for line in source_text_lines_all] if strip_config['source'] else source_text_lines_all
    display_target_lines_all = [_strip_markdown_header(line) for line in target_content_lines_all] if strip_config['translations'] else target_content_lines_all
    display_tertiary_lines_all = [_strip_markdown_header(line) for line in tertiary_content_lines_all] if strip_config['translations'] else tertiary_content_lines_all
    
    display_source_content_lines = [line for line in display_source_lines_all if line.strip()]
    display_target_content_lines = [line for line in display_target_lines_all if line.strip()]
    display_tertiary_content_lines = [line for line in display_tertiary_lines_all if line.strip()]

    lemma_data = {}
    if args.deduplication_scope == 'global':
        lemma_data = {'lemmas': {}, 'info': {}}
    else:
        lemma_data = []

    subdeck_content_map = {}
    deck_stack = []
    level_stack = []
    header_counter = 1
    sentence_lemmas_cache = {}
    
    branch_header_lines = set()
    if args.anki_markdown_decks:
        branch_header_lines = parse_markdown_for_branch_headers(source_text_lines_all)
        root_deck_prefix = ""
        if args.anki_create_subdecks:
            if args.anki_parent_deck:
                root_deck_prefix = args.anki_parent_deck
            elif output_file_path:
                base_name = os.path.splitext(os.path.basename(output_file_path))[0]
                root_deck_prefix = re.sub(r'\.(word|sentence)', '', base_name)
        if root_deck_prefix:
            deck_stack.append(root_deck_prefix)
            level_stack.append(0)

    text_has_headers = any(re.match(r'^(#+)\s+', line.strip()) for line in source_text_lines_all)
    
    first_real_header_level = 2 
    if text_has_headers:
        for line in source_text_lines_all:
            match = re.match(r'^(#+)', line.strip())
            if match:
                first_real_header_level = len(match.group(1))
                break

    content_line_idx = -1
    active_header_line_index = -1
    first_header_encountered = False
    placeholder_deck_created = False

    for line_index, source_line_raw in enumerate(source_text_lines_all):
        if not source_line_raw.strip(): continue

        lemmas_in_sentence = {}
        source_line_for_analysis = source_line_raw.strip()
        
        if args.anki_markdown_decks:
            header_match = re.match(r'^(#+)\s+(.*)', source_line_for_analysis)
            if header_match:
                first_header_encountered = True
                active_header_line_index = line_index
                level = len(header_match.group(1))
                title = header_match.group(2).strip()
                sanitized_title = generate_filename_prefix_from_text(title, 5)

                while level_stack and level_stack[-1] >= level:
                    level_stack.pop()
                    deck_stack.pop()
                
                if sanitized_title:
                    deck_stack.append(f"{100000 + header_counter}-{sanitized_title}")
                    level_stack.append(level)
                    header_counter += 1
                source_line_for_analysis = title
            elif not first_header_encountered and not placeholder_deck_created and text_has_headers:
                level = first_real_header_level
                
                while level_stack and level_stack[-1] >= level:
                    level_stack.pop()
                    deck_stack.pop()

                title = source_line_for_analysis
                sanitized_title = generate_filename_prefix_from_text(title, 5)
                
                if sanitized_title:
                    deck_stack.append(f"{100000 + header_counter}-{sanitized_title}")
                    level_stack.append(level)
                    header_counter += 1
                
                placeholder_deck_created = True
        
        content_line_idx += 1
        source_sentence = source_line_for_analysis
        
        base_deck = "::".join(deck_stack)
        final_deck = base_deck
        if args.anki_markdown_decks and active_header_line_index in branch_header_lines:
            final_deck = f"{base_deck}::{deck_stack[-1]}"
        
        if args.anki_deck_content and final_deck:
            if final_deck not in subdeck_content_map:
                subdeck_content_map[final_deck] = {'source_lines': [], 'translation1_lines': [], 'translation2_lines': []}
            subdeck_content_map[final_deck]['source_lines'].append(source_line_raw)
            if line_index < len(target_content_lines_all):
                subdeck_content_map[final_deck]['translation1_lines'].append(target_content_lines_all[line_index])
            if line_index < len(tertiary_content_lines_all):
                subdeck_content_map[final_deck]['translation2_lines'].append(tertiary_content_lines_all[line_index])

        if args.anki_sentence_subdecks:
            sentence_prefix = str(content_line_idx + 1).zfill(6)
            sentence_slug = generate_filename_prefix_from_text(source_sentence, 4)
            if sentence_slug:
                sentence_deck_name = f"{final_deck}::{sentence_prefix}-{sentence_slug}"
                final_deck = sentence_deck_name

        if source_sentence not in doc_cache:
            doc_cache[source_sentence] = nlp(source_sentence)
        doc = doc_cache[source_sentence]
        
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
                    if not lemma:
                        continue
                    
                    data_entry = {
                        'lemma': lemma,
                        'source_word': source_word_form,
                        'sentence_index': content_line_idx,
                        'source_sentence': source_sentence,
                        'deck_name': final_deck
                    }

                    if args.deduplication_scope == 'global':
                        is_new = lemma not in lemma_data['lemmas']
                        if is_new:
                            lemma_data['lemmas'][lemma] = source_word_form
                            lemma_data['info'][lemma] = (content_line_idx, source_sentence, final_deck)
                        elif args.prefer_shortest_form and len(source_word_form) < len(lemma_data['lemmas'][lemma]):
                            lemma_data['lemmas'][lemma] = source_word_form
                            lemma_data['info'][lemma] = (content_line_idx, source_sentence, final_deck)

                    elif args.deduplication_scope == 'sentence':
                        if lemma not in lemmas_in_sentence or len(source_word_form) < len(lemmas_in_sentence[lemma]['source_word']):
                            lemmas_in_sentence[lemma] = data_entry
                    elif args.deduplication_scope == 'none':
                        lemma_data.append(data_entry)

        if args.deduplication_scope == 'sentence':
            lemma_data.extend(lemmas_in_sentence.values())

    sorted_items = []
    if args.deduplication_scope == 'global':
        sorted_items = sorted(list(lemma_data['lemmas'].keys()), key=lambda word: (word not in lemma_sort_index, lemma_sort_index.get(word, 0), word.lower()))
    else:
        sorted_items = sorted(lemma_data, key=lambda x: (x['lemma'] not in lemma_sort_index, lemma_sort_index.get(x['lemma'], 0), x['lemma'].lower()))

    if output_file_path:
        full_deck_name = ""
        if args.anki_create_subdecks and not args.anki_markdown_decks:
            sub_deck_name = os.path.splitext(os.path.basename(output_file_path))[0]
            if args.anki_parent_deck:
                parent_deck_name = args.anki_parent_deck
            else:
                parent_deck_name = re.sub(r'\.(word|sentence)', '', sub_deck_name)
            
            if parent_deck_name != sub_deck_name:
                full_deck_name = f"{parent_deck_name}::{sub_deck_name}"
            else:
                full_deck_name = parent_deck_name

        with open(output_file_path, "w", newline="", encoding="utf-8") as tsvfile:
            tsv_writer = csv.writer(tsvfile, delimiter="\t")
            if add_header:
                tsv_writer.writerow(anki_header)

            F = get_field_index_map(anki_header)
            for item in sorted_items:
                csv_row = [""] * len(anki_header)
                
                word, source_word_col_val, sentence_index, source_sentence_for_lemmas, deck_name = "", "", -1, "", ""

                if args.deduplication_scope == 'global':
                    word = item
                    sentence_index, source_sentence_for_lemmas, deck_name = lemma_data['info'].get(word, (-1, "", ""))
                    if sentence_index == -1: continue
                    source_word_col_val = lemma_data['lemmas'].get(word, '')
                else: # sentence or none
                    word = item['lemma']
                    sentence_index = item['sentence_index']
                    source_sentence_for_lemmas = item['source_sentence']
                    deck_name = item['deck_name']
                    source_word_col_val = item['source_word']

                context_start_index, context_end_index = max(0, sentence_index - sentence_context_size), sentence_index + sentence_context_size + 1
                
                source_sentence_for_tsv = display_source_content_lines[sentence_index].strip() if sentence_index < len(display_source_content_lines) else ""
                target_sentence_for_tsv = display_target_content_lines[sentence_index].strip() if sentence_index < len(display_target_content_lines) else ""
                tertiary_sentence_for_tsv = display_tertiary_content_lines[sentence_index].strip() if sentence_index < len(display_tertiary_content_lines) else ""

                current_wordlist = ""
                if add_wordlist_col:
                    if source_sentence_for_lemmas not in sentence_lemmas_cache:
                        wordlist_generation_args = {**kwargs, 'de_gcs': de_gcs, 'gcs_automaton': gcs_automaton, 'de_gcs_add_parts_to_wordlist': de_gcs_add_parts_to_wordlist}
                        lemmas = extract_lemmas_from_sentence(source_sentence_for_lemmas, lemma_sort_index, nlp, de_dictionary, lemma_override_rules, de_gcs_pos_tags, args, **wordlist_generation_args)
                        sentence_lemmas_cache[source_sentence_for_lemmas] = lemmas
                    current_wordlist = "<br>".join(sentence_lemmas_cache[source_sentence_for_lemmas]) if wordlist_use_br else "\n".join(sentence_lemmas_cache[source_sentence_for_lemmas])
                
                CSV_ROW_DECK_VAL = ""
                if args.anki_markdown_decks:
                    CSV_ROW_DECK_VAL = deck_name
                elif full_deck_name:
                    CSV_ROW_DECK_VAL = full_deck_name

                row_data = prepare_row_data(
                    args,
                    lemma=word,
                    source_word=source_word_col_val,
                    sentence_index=str(sentence_index + 1).zfill(6),
                    source_sentence=source_sentence_for_tsv,
                    source_context_left=" ".join(line.strip() for line in display_source_content_lines[context_start_index:sentence_index]),
                    source_context_right=" ".join(line.strip() for line in display_source_content_lines[sentence_index + 1:context_end_index]),
                    target_sentence=target_sentence_for_tsv,
                    target_context_left=" ".join(line.strip() for line in display_target_content_lines[context_start_index:sentence_index]),
                    target_context_right=" ".join(line.strip() for line in display_target_content_lines[sentence_index + 1:context_end_index]),
                    tertiary_sentence=tertiary_sentence_for_tsv,
                    tertiary_context_left=" ".join(line.strip() for line in display_tertiary_content_lines[context_start_index:sentence_index]),
                    tertiary_context_right=" ".join(line.strip() for line in display_tertiary_content_lines[sentence_index + 1:context_end_index]),
                    wordlist=current_wordlist,
                    cloze=source_sentence_for_tsv,
                    deck_name=CSV_ROW_DECK_VAL
                )
                apply_field_mapping(csv_row, row_data, field_mapping, F)
                tsv_writer.writerow(csv_row)
        
        target_text_content = None
        if target_text_path and os.path.exists(target_text_path):
            with open(target_text_path, "r", encoding="utf-8") as f:
                target_text_content = f.read()

        tertiary_text_content = None
        if tertiary_text_path and os.path.exists(tertiary_text_path):
            with open(tertiary_text_path, "r", encoding="utf-8") as f:
                tertiary_text_content = f.read()
        
        _write_deck_metadata(args, output_file_path, source_text, target_text_content, tertiary_text_content, subdeck_content_map)

    return output_file_path

def process_single_text(
    source_text, lemma_sort_index, language, sentence_context_size,
    output_file_path, add_source_word_col, add_wordlist_col, add_sentence_index_col,
    add_header, wordlist_use_br, stdout_print_output_basename, de_gcs, gcs_automaton, de_gcs_add_parts_to_wordlist, de_dictionary, lemma_override_rules, 
    de_gcs_pos_tags, field_mapping, anki_header, args, **kwargs
):
    de_gcs_only_nouns = kwargs.get('de_gcs_only_nouns', True)
    de_gcs_combine_noun_modes = kwargs.get('de_gcs_combine_noun_modes', False)
    de_fix_genitive = kwargs.get('de_fix_genitive', False)
    de_gcs_mask_unknown_parts = kwargs.get('de_gcs_mask_unknown_parts', False)
    de_gcs_preserve_compound_word = kwargs.get('de_gcs_preserve_compound_word', False)
    de_gcs_skip_merge_fractions = kwargs.get('de_gcs_skip_merge_fractions', False)

    is_multiline_from_file = '\n' in source_text.strip()
    source_lines = source_text.splitlines() if is_multiline_from_file else []

    text_units = []
    deck_map = {}
    subdeck_content_map = {}
    header_counter = 1
    branch_header_lines = set()
    active_header_line_index = -1

    if args.anki_markdown_decks and is_multiline_from_file:
        branch_header_lines = parse_markdown_for_branch_headers(source_lines)
        deck_stack = []
        level_stack = []
        root_deck_prefix = ""
        if args.anki_create_subdecks:
            if args.anki_parent_deck:
                root_deck_prefix = args.anki_parent_deck
            elif output_file_path:
                base_name = os.path.splitext(os.path.basename(output_file_path))[0]
                root_deck_prefix = re.sub(r'\.(word|sentence)', '', base_name)
        if root_deck_prefix:
            deck_stack.append(root_deck_prefix)
            level_stack.append(0)

        text_has_headers = any(re.match(r'^(#+)\s+', line.strip()) for line in source_lines)
        
        first_real_header_level = 2 
        if text_has_headers:
            for line in source_lines:
                match = re.match(r'^(#+)', line.strip())
                if match:
                    first_real_header_level = len(match.group(1))
                    break

        first_header_encountered = False
        placeholder_deck_created = False

        for line_index, line_raw in enumerate(source_lines):
            line = line_raw.strip()
            if not line: continue
            
            header_match = re.match(r'^(#+)\s+(.*)', line)
            if header_match:
                first_header_encountered = True
                active_header_line_index = line_index
                level = len(header_match.group(1))
                title = header_match.group(2).strip()
                sanitized_title = generate_filename_prefix_from_text(title, 5)

                while level_stack and level_stack[-1] >= level:
                    level_stack.pop()
                    deck_stack.pop()

                if sanitized_title:
                    deck_stack.append(f"{100000 + header_counter}-{sanitized_title}")
                    level_stack.append(level)
                    header_counter += 1
                line = title
            elif not first_header_encountered and not placeholder_deck_created and text_has_headers:
                level = first_real_header_level
                
                while level_stack and level_stack[-1] >= level:
                    level_stack.pop()
                    deck_stack.pop()

                title = line
                sanitized_title = generate_filename_prefix_from_text(title, 5)

                if sanitized_title:
                    deck_stack.append(f"{100000 + header_counter}-{sanitized_title}")
                    level_stack.append(level)
                    header_counter += 1
                placeholder_deck_created = True

            base_deck = "::".join(deck_stack)
            final_deck = base_deck
            if active_header_line_index in branch_header_lines:
                final_deck = f"{base_deck}::{deck_stack[-1]}"

            if args.anki_deck_content and final_deck:
                if final_deck not in subdeck_content_map:
                    subdeck_content_map[final_deck] = {'source_lines': []}
                subdeck_content_map[final_deck]['source_lines'].append(line_raw)

            if args.anki_sentence_subdecks:
                sentence_prefix = str(len(text_units) + 1).zfill(6)
                sentence_slug = generate_filename_prefix_from_text(line, 4)
                if sentence_slug:
                    sentence_deck_name = f"{final_deck}::{sentence_prefix}-{sentence_slug}"
                    final_deck = sentence_deck_name

            deck_map[len(text_units)] = final_deck
            text_units.append(line)
    else:
        if is_multiline_from_file:
            text_units = [line.strip() for line in source_lines if line.strip()]
        else:
            doc = nlp(source_text)
            text_units = [sent.text for sent in doc.sents]

    strip_config = {'source': False, 'translations': False}
    if args.strip_headers is not None:
        targets = args.strip_headers if args.strip_headers else ['all']
        if 'all' in targets or 'source' in targets:
            strip_config['source'] = True

    display_text_units = [_strip_markdown_header(unit) for unit in text_units] if strip_config['source'] else text_units

    lemma_data = {}
    if args.deduplication_scope == 'global':
        lemma_data = {'lemmas': {}, 'info': {}}
    else:
        lemma_data = []

    doc_cache = {}

    for unit_index, unit_text in enumerate(text_units):
        lemmas_in_sentence = {}
        if unit_text not in doc_cache:
            doc_cache[unit_text] = nlp(unit_text)
        unit_doc = doc_cache[unit_text]

        current_deck = deck_map.get(unit_index, "")

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
                    if not lemma:
                        continue
                        
                    data_entry = {
                        'lemma': lemma,
                        'source_word': source_word_form,
                        'sentence_index': unit_index,
                        'source_sentence': unit_text,
                        'deck_name': current_deck
                    }

                    if args.deduplication_scope == 'global':
                        is_new = lemma not in lemma_data['lemmas']
                        if is_new:
                            lemma_data['lemmas'][lemma] = source_word_form
                            lemma_data['info'][lemma] = (unit_index, unit_text, current_deck)
                        elif args.prefer_shortest_form and len(source_word_form) < len(lemma_data['lemmas'][lemma]):
                            lemma_data['lemmas'][lemma] = source_word_form
                            lemma_data['info'][lemma] = (unit_index, unit_text, current_deck)
                            
                    elif args.deduplication_scope == 'sentence':
                        if lemma not in lemmas_in_sentence or len(source_word_form) < len(lemmas_in_sentence[lemma]['source_word']):
                            lemmas_in_sentence[lemma] = data_entry
                    elif args.deduplication_scope == 'none':
                        lemma_data.append(data_entry)

        if args.deduplication_scope == 'sentence':
            lemma_data.extend(lemmas_in_sentence.values())

    sorted_items = []
    if args.deduplication_scope == 'global':
        sorted_items = sorted(list(lemma_data['lemmas'].keys()), key=lambda word: (word not in lemma_sort_index, lemma_sort_index.get(word, 0), word.lower()))
    else:
        sorted_items = sorted(lemma_data, key=lambda x: (x['lemma'] not in lemma_sort_index, lemma_sort_index.get(x['lemma'], 0), x['lemma'].lower()))
    
    sentence_lemmas_cache = {}

    if not output_file_path:
        if args.stdout_format == 'html':
            print("<table>", file=sys.stdout)
            for item in sorted_items:
                word = item if args.deduplication_scope == 'global' else item['lemma']
                source_word = lemma_data['lemmas'].get(word, '') if args.deduplication_scope == 'global' else item['source_word']
                print(f"<tr><td>{word}</td><td>{source_word}</td></tr>", file=sys.stdout)
            print("</table>", file=sys.stdout)
        elif args.stdout_format == 'tsv':
            for item in sorted_items:
                word = item if args.deduplication_scope == 'global' else item['lemma']
                source_word = lemma_data['lemmas'].get(word, '') if args.deduplication_scope == 'global' else item['source_word']
                print(f"{word}\t{source_word}", file=sys.stdout)
        elif args.stdout_format == 'context':
             for item in sorted_items:
                word, unit_index = "", -1
                if args.deduplication_scope == 'global':
                    word = item
                    unit_index, _, _ = lemma_data['info'].get(word, (-1, "", ""))
                else:
                    word = item['lemma']
                    unit_index = item['sentence_index']

                if unit_index == -1: continue
                
                source_sentence = display_text_units[unit_index].strip()
                context_start_index = max(0, unit_index - sentence_context_size)
                context_end_index = min(len(display_text_units), unit_index + sentence_context_size + 1)
                
                source_context_left = " ".join(u.strip() for u in display_text_units[context_start_index:unit_index])
                source_context_right = " ".join(u.strip() for u in display_text_units[unit_index + 1:context_end_index])
                
                print(word, file=sys.stdout)
                if source_context_left: print(source_context_left, file=sys.stdout)
                print(source_sentence, file=sys.stdout)
                if source_context_right: print(source_context_right, file=sys.stdout)
                print(file=sys.stdout)
        else:
            for item in sorted_items:
                word = item if args.deduplication_scope == 'global' else item['lemma']
                print(word, file=sys.stdout)
        return None

    full_deck_name = ""
    if args.anki_create_subdecks and not args.anki_markdown_decks:
        sub_deck_name = os.path.splitext(os.path.basename(output_file_path))[0]
        if args.anki_parent_deck:
            parent_deck_name = args.anki_parent_deck
        else:
            parent_deck_name = re.sub(r'\.(word|sentence)', '', sub_deck_name)

        if parent_deck_name != sub_deck_name:
            full_deck_name = f"{parent_deck_name}::{sub_deck_name}"
        else:
            full_deck_name = parent_deck_name

    with open(output_file_path, "w", newline="", encoding="utf-8") as tsvfile:
        tsv_writer = csv.writer(tsvfile, delimiter="\t")
        if add_header:
            tsv_writer.writerow(anki_header)

        F = get_field_index_map(anki_header)
        for item in sorted_items:
            csv_row = [""] * len(anki_header)
            
            word, source_word_col_val, unit_index, source_sentence_for_lemmas, deck_name = "", "", -1, "", ""

            if args.deduplication_scope == 'global':
                word = item
                unit_index, source_sentence_for_lemmas, deck_name = lemma_data['info'].get(word, (-1, "", ""))
                if unit_index == -1: continue
                source_word_col_val = lemma_data['lemmas'].get(word, '')
            else: # sentence or none
                word = item['lemma']
                unit_index = item['sentence_index']
                source_sentence_for_lemmas = item['source_sentence']
                deck_name = item['deck_name']
                source_word_col_val = item['source_word']
            
            source_sentence_for_tsv = display_text_units[unit_index].strip()
            context_start_index = max(0, unit_index - sentence_context_size)
            context_end_index = min(len(display_text_units), unit_index + sentence_context_size + 1)
            
            current_wordlist = ""
            if add_wordlist_col:
                if source_sentence_for_lemmas not in sentence_lemmas_cache:
                    wordlist_generation_args = {**kwargs, 'de_gcs': de_gcs, 'gcs_automaton': gcs_automaton, 'de_gcs_add_parts_to_wordlist': de_gcs_add_parts_to_wordlist}
                    lemmas = extract_lemmas_from_sentence(source_sentence_for_lemmas, lemma_sort_index, nlp, de_dictionary, lemma_override_rules, de_gcs_pos_tags, args, **wordlist_generation_args)
                    sentence_lemmas_cache[source_sentence_for_lemmas] = lemmas
                current_wordlist = "<br>".join(sentence_lemmas_cache[source_sentence_for_lemmas]) if wordlist_use_br else "\n".join(sentence_lemmas_cache[source_sentence_for_lemmas])

            CSV_ROW_DECK_VAL = ""
            if args.anki_markdown_decks:
                CSV_ROW_DECK_VAL = deck_name
            elif full_deck_name:
                CSV_ROW_DECK_VAL = full_deck_name

            row_data = prepare_row_data(
                args,
                lemma=word,
                source_word=source_word_col_val,
                source_sentence=source_sentence_for_tsv,
                source_context_left=" ".join(u.strip() for u in display_text_units[context_start_index:unit_index]),
                source_context_right=" ".join(u.strip() for u in display_text_units[unit_index + 1:context_end_index]),
                wordlist=current_wordlist,
                cloze=source_sentence_for_tsv,
                sentence_index=str(unit_index + 1).zfill(6),
                deck_name=CSV_ROW_DECK_VAL
            )
            
            apply_field_mapping(csv_row, row_data, field_mapping, F)
            tsv_writer.writerow(csv_row)

    _write_deck_metadata(args, output_file_path, source_text, subdeck_content_map=subdeck_content_map)
    return output_file_path

def process_parallel_sentences_to_csv(
    language, lemma_sort_index, source_text_path, target_text_path, tertiary_text_path, sentence_context_size,
    output_file_path, add_wordlist_col, add_sentence_index_col, add_header, wordlist_use_br, stdout_print_output_basename, de_gcs_pos_tags, field_mapping, anki_header, args, **kwargs
):
    lemma_override_rules = kwargs.pop('lemma_override_rules', {})
    
    source_text_content = ""
    source_text_lines_all = []
    try:
        source_text_content = read_text_from_file(source_text_path)
        source_text_lines_all = [line.rstrip("\n") for line in source_text_content.splitlines()]

        target_content_lines_all = []
        if target_text_path:
            with open(target_text_path, "r", encoding="utf-8") as f:
                target_content_lines_all = [line.rstrip("\n") for line in f]
        
        tertiary_content_lines_all = []
        if tertiary_text_path:
            with open(tertiary_text_path, "r", encoding="utf-8") as f:
                tertiary_content_lines_all = [line.rstrip("\n") for line in f]
    except IOError as e:
        print(f"Error reading files: {e}", file=sys.stderr); sys.exit(1)

    strip_config = {'source': False, 'translations': False}
    if args.strip_headers is not None:
        targets = args.strip_headers if args.strip_headers else ['all']
        if 'all' in targets or 'source' in targets:
            strip_config['source'] = True
        if 'all' in targets or 'translations' in targets:
            strip_config['translations'] = True

    display_source_lines_all = [_strip_markdown_header(line) for line in source_text_lines_all] if strip_config['source'] else source_text_lines_all
    display_target_lines_all = [_strip_markdown_header(line) for line in target_content_lines_all] if strip_config['translations'] else target_content_lines_all
    display_tertiary_lines_all = [_strip_markdown_header(line) for line in tertiary_content_lines_all] if strip_config['translations'] else tertiary_content_lines_all
    
    display_source_content_lines = [line for line in display_source_lines_all if line.strip()]
    display_target_content_lines = [line for line in display_target_lines_all if line.strip()]
    display_tertiary_content_lines = [line for line in display_tertiary_lines_all if line.strip()]

    full_deck_name = ""
    if args.anki_create_subdecks and not args.anki_markdown_decks:
        sub_deck_name = os.path.splitext(os.path.basename(output_file_path))[0]
        if args.anki_parent_deck:
            parent_deck_name = args.anki_parent_deck
        else:
            parent_deck_name = re.sub(r'\.(word|sentence)', '', sub_deck_name)

        if parent_deck_name != sub_deck_name:
            full_deck_name = f"{parent_deck_name}::{sub_deck_name}"
        else:
            full_deck_name = parent_deck_name

    with open(output_file_path, "w", newline="", encoding="utf-8") as output_csv_file:
        tsv_writer = csv.writer(output_csv_file, delimiter="\t")
        if add_header:
            tsv_writer.writerow(anki_header)

        F = get_field_index_map(anki_header)
        deck_stack = []
        level_stack = []
        subdeck_content_map = {}
        sentence_lemmas_cache = {}
        header_counter = 1
        branch_header_lines = set()
        if args.anki_markdown_decks:
            branch_header_lines = parse_markdown_for_branch_headers(source_text_lines_all)
            root_deck_prefix = ""
            if args.anki_create_subdecks:
                if args.anki_parent_deck:
                    root_deck_prefix = args.anki_parent_deck
                elif output_file_path:
                    base_name = os.path.splitext(os.path.basename(output_file_path))[0]
                    root_deck_prefix = re.sub(r'\.(word|sentence)', '', base_name)
            if root_deck_prefix:
                deck_stack.append(root_deck_prefix)
                level_stack.append(0)

        text_has_headers = any(re.match(r'^(#+)\s+', line.strip()) for line in source_text_lines_all)
        
        first_real_header_level = 2 
        if text_has_headers:
            for line in source_text_lines_all:
                match = re.match(r'^(#+)', line.strip())
                if match:
                    first_real_header_level = len(match.group(1))
                    break
        
        content_line_idx = -1
        active_header_line_index = -1
        first_header_encountered = False
        placeholder_deck_created = False

        for line_index, source_line_raw in enumerate(source_text_lines_all):
            if not source_line_raw.strip(): continue

            source_line_for_analysis = source_line_raw.strip()
            
            if args.anki_markdown_decks:
                header_match = re.match(r'^(#+)\s+(.*)', source_line_for_analysis)
                if header_match:
                    first_header_encountered = True
                    active_header_line_index = line_index
                    level = len(header_match.group(1))
                    title = header_match.group(2).strip()
                    sanitized_title = generate_filename_prefix_from_text(title, 5)

                    while level_stack and level_stack[-1] >= level:
                        level_stack.pop()
                        deck_stack.pop()

                    if sanitized_title:
                        deck_stack.append(f"{100000 + header_counter}-{sanitized_title}")
                        level_stack.append(level)
                        header_counter += 1
                    source_line_for_analysis = title
                elif not first_header_encountered and not placeholder_deck_created and text_has_headers:
                    level = first_real_header_level
                    
                    while level_stack and level_stack[-1] >= level:
                        level_stack.pop()
                        deck_stack.pop()

                    title = source_line_for_analysis
                    sanitized_title = generate_filename_prefix_from_text(title, 5)
                    
                    if sanitized_title:
                        deck_stack.append(f"{100000 + header_counter}-{sanitized_title}")
                        level_stack.append(level)
                        header_counter += 1
                    
                    placeholder_deck_created = True

            base_deck = "::".join(deck_stack)
            final_deck_for_content = base_deck
            if active_header_line_index in branch_header_lines:
                final_deck_for_content = f"{base_deck}::{deck_stack[-1]}"

            if args.anki_deck_content and final_deck_for_content:
                if final_deck_for_content not in subdeck_content_map:
                    subdeck_content_map[final_deck_for_content] = {'source_lines': [], 'translation1_lines': [], 'translation2_lines': []}
                subdeck_content_map[final_deck_for_content]['source_lines'].append(source_line_raw)
                if line_index < len(target_content_lines_all):
                    subdeck_content_map[final_deck_for_content]['translation1_lines'].append(target_content_lines_all[line_index])
                if line_index < len(tertiary_content_lines_all):
                    subdeck_content_map[final_deck_for_content]['translation2_lines'].append(tertiary_content_lines_all[line_index])

            content_line_idx += 1
            if content_line_idx >= len(display_source_content_lines): break

            csv_row = [""] * len(anki_header)
            source_sentence = display_source_content_lines[content_line_idx].strip()
            target_sentence = display_target_content_lines[content_line_idx].strip() if content_line_idx < len(display_target_content_lines) else ""
            tertiary_sentence = display_tertiary_content_lines[content_line_idx].strip() if content_line_idx < len(display_tertiary_content_lines) else ""
            
            context_start_index = max(0, content_line_idx - sentence_context_size)
            context_end_index = content_line_idx + sentence_context_size + 1

            current_wordlist = ""
            if add_wordlist_col:
                source_sentence_for_lemmas = source_text_lines_all[line_index]
                if source_sentence_for_lemmas not in sentence_lemmas_cache:
                    wordlist_generation_args = {**kwargs, 'de_gcs': args.de_gcs, 'gcs_automaton': None} # simplify for now
                    lemmas = extract_lemmas_from_sentence(source_sentence_for_lemmas, lemma_sort_index, nlp, None, lemma_override_rules, de_gcs_pos_tags, args, **wordlist_generation_args)
                    sentence_lemmas_cache[source_sentence_for_lemmas] = lemmas
                current_wordlist = "<br>".join(sentence_lemmas_cache[source_sentence_for_lemmas]) if wordlist_use_br else "\n".join(sentence_lemmas_cache[source_sentence_for_lemmas])

            final_deck_for_card = ""
            if args.anki_markdown_decks:
                final_deck_for_card = "::".join(deck_stack)
                if active_header_line_index in branch_header_lines:
                    final_deck_for_card = f"{final_deck_for_card}::{deck_stack[-1]}"
                
                if args.anki_sentence_subdecks:
                    sentence_prefix = str(content_line_idx + 1).zfill(6)
                    sentence_slug = generate_filename_prefix_from_text(source_sentence, 4)
                    if sentence_slug:
                        sentence_deck_name = f"{final_deck_for_card}::{sentence_prefix}-{sentence_slug}"
                        final_deck_for_card = sentence_deck_name
            elif full_deck_name:
                final_deck_for_card = full_deck_name

            row_data = prepare_row_data(
                args,
                source_sentence=source_sentence,
                source_context_left=" ".join(line.strip() for line in display_source_content_lines[context_start_index:content_line_idx]),
                source_context_right=" ".join(line.strip() for line in display_source_content_lines[content_line_idx + 1:context_end_index]),
                target_sentence=target_sentence,
                target_context_left=" ".join(line.strip() for line in display_target_content_lines[context_start_index:content_line_idx]),
                target_context_right=" ".join(line.strip() for line in display_target_content_lines[content_line_idx + 1:context_end_index]),
                tertiary_sentence=tertiary_sentence,
                tertiary_context_left=" ".join(line.strip() for line in display_tertiary_content_lines[context_start_index:content_line_idx]),
                tertiary_context_right=" ".join(line.strip() for line in display_tertiary_content_lines[content_line_idx + 1:context_end_index]),
                wordlist=current_wordlist,
                cloze=source_sentence,
                sentence_index=str(content_line_idx + 1).zfill(6),
                deck_name=final_deck_for_card
            )

            apply_field_mapping(csv_row, row_data, field_mapping, F)
            tsv_writer.writerow(csv_row)
            
    target_text_content = None
    if target_text_path and os.path.exists(target_text_path):
        with open(target_text_path, "r", encoding="utf-8") as f:
            target_text_content = f.read()

    tertiary_text_content = None
    if tertiary_text_path and os.path.exists(tertiary_text_path):
        with open(tertiary_text_path, "r", encoding="utf-8") as f:
            tertiary_text_content = f.read()

    _write_deck_metadata(args, output_file_path, source_text_content, target_text_content, tertiary_text_content, subdeck_content_map)
    return output_file_path

def process_lemmas_per_line(
    source_text_path, output_file_path, lemma_sort_index, 
    de_dictionary, lemma_override_rules, args
):
    try:
        with open(source_text_path, "r", encoding="utf-8") as f_in:
            source_lines = f_in.readlines()
    except IOError as e:
        print(f"Error reading input file {source_text_path}: {e}", file=sys.stderr)
        sys.exit(1)

    with open(output_file_path, "w", encoding="utf-8") as f_out:
        for line in source_lines:
            line = line.strip()
            if not line:
                f_out.write("\n")
                continue
            
            lemmas = extract_lemmas_from_sentence(
                line, lemma_sort_index, nlp, de_dictionary, 
                lemma_override_rules, [], args, de_gcs=False
            )
            
            output_line = " ".join(lemmas)
            f_out.write(output_line + "\n")
    
    return output_file_path

def main():
    parser = argparse.ArgumentParser(
        description="Extract and process words or sentences from text.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    input_output_group = parser.add_argument_group('Input & Output')
    processing_mode_group = parser.add_mutually_exclusive_group(required=True)
    processing_mode_group.add_argument("--type", choices=["word", "sentence"], help="Specify the processing type: 'word' for word extraction, 'sentence' for parallel sentence processing.")
    processing_mode_group.add_argument("--lemmas-per-line", action="store_true", help="Process each line of text1-file to output a single line of frequency-sorted lemmas.")
    input_output_group.add_argument("--language", default="de", choices=["de", "en"], help="The language of the text to be processed.")
    input_output_group.add_argument("--tts-destination-lang", default="ru", help="The destination language for TTS field activation (e.g., 'ru', 'en').")
    input_output_group.add_argument("--text", help="A single string of input text to process. Mutually exclusive with --text1-file.")
    input_output_group.add_argument("--text1-file", help="Path to the primary input text file.")
    input_output_group.add_argument("--text2-file", help="Path to a parallel (translated) text file.")
    input_output_group.add_argument("--text3-file", help="Path to a third parallel text file.")
    input_output_group.add_argument("--output-file", help="Path to the output file. If not provided, results are printed to standard output.")
    input_output_group.add_argument("--multi-text", action="store_true", help="Parse input from --text or stdin as up to three texts separated by '---'.")

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
    output_format_group.add_argument("--add-sentence-index-col", action="store_true", help="Add a column with the sentence index number, for sorting.")
    output_format_group.add_argument("--sentence-context-size", type=int, default=1, help="The number of sentences to include before and after the source sentence as context.")
    output_format_group.add_argument("--anki-create-subdecks", action="store_true", help="Automatically generate a parent deck and sub-decks for Anki based on the output filename.")
    output_format_group.add_argument("--anki-markdown-decks", action="store_true", help="Parse Markdown headers in source text to create a hierarchical deck structure in Anki.")
    output_format_group.add_argument("--anki-sentence-subdecks", action="store_true", help="Create a final subdeck level for each sentence. Requires --anki-markdown-decks.")
    output_format_group.add_argument("--anki-parent-deck", help="Manually specify the parent deck name, overriding the auto-generated one. Requires --anki-create-subdecks.")
    output_format_group.add_argument("--anki-deck-content", nargs='+', choices=['parent-source', 'parent-translations', 'subdeck-source', 'subdeck-translations'], help="Adds content to the Anki deck description. 'parent-source': adds full source text to parent deck. 'subdeck-source': adds relevant source text part to each subdeck.")
    output_format_group.add_argument(
        "--strip-headers",
        nargs='*',
        choices=['all', 'source', 'translations'],
        help="Strip Markdown headers (#) from text fields in the final TSV output. 'all': strip from source and translations. 'source': only from source. 'translations': only from translations. If the flag is present without arguments, it defaults to 'all'."
    )
    output_format_group.add_argument(
        "--anki-field-mapping",
        type=str,
        default=None,
        help="JSON string mapping Anki field names to internal data source names. "
             "Used to customize which data populates which field in the output TSV. "
             "Example: '{\"WordSourceAI\": \"source_word\", \"Quotation\": \"lemma\"}'"
    )
    output_format_group.add_argument(
        "--anki-csv-header",
        type=str,
        default=None,
        help="JSON string list of Anki field names for CSV header and order."
    )
    stdout_group = parser.add_argument_group('Standard Output (STDOUT) Arguments (used only if --output is not specified)')
    output_format_group.add_argument("--stdout-format", choices=['list', 'context', 'tsv', 'html'], default='list', 
                               help="Select the output format for STDOUT if --output-file is not specified.\n"
                                    "'list' (default): A simple, one-lemma-per-line list.\n"
                                    "'context': Lemmas with full sentence context.\n"
                                    "'tsv': A two-column list (lemma, source word) separated by a tab.\n"
                                    "'html': The two-column list formatted as an HTML table.")

    lemmatization_group = parser.add_argument_group('Lemmatization Control')
    lemmatization_group.add_argument("--force-proper-noun-capitalization", action="store_true", help="Force capitalization of proper noun lemmas (PROPN).")
    lemmatization_group.add_argument("--deduplication-scope", choices=['global', 'sentence', 'none'], default='global', help="Set the scope for lemma deduplication. 'global': unique lemmas across the entire text. 'sentence': unique lemmas within each sentence. 'none': no duplication, one entry per word occurrence.")
    lemmatization_group.add_argument("--prefer-shortest-form", action="store_true", help="When deduplicating globally, prefer the shortest word form of a lemma, even if it appears later in the text. Default is to keep the first occurrence.")
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
    
    if args.multi_text:
        if args.text1_file:
            print("Warning: --multi-text is ignored when --text1-file is provided.", file=sys.stderr)
        else:
            input_text_combined = ""
            if args.text:
                input_text_combined = args.text
            elif not sys.stdin.isatty():
                input_text_combined = sys.stdin.read()

            if input_text_combined:
                parts = re.split(r'\s*---\s*', input_text_combined.strip())
                text_blocks = parts[:3]
                file_arg_names = ['text1_file', 'text2_file', 'text3_file']

                for i, arg_name in enumerate(file_arg_names):
                    text_content = text_blocks[i] if i < len(text_blocks) else ""
                    
                    fd, path = tempfile.mkstemp(suffix='.txt', text=True)
                    with os.fdopen(fd, 'w', encoding='utf-8') as tmp:
                        tmp.write(text_content)
                    
                    setattr(args, arg_name, path)
                    TEMP_FILES_TO_CLEANUP.append(path)
                
                args.text = None
            else:
                print("Warning: --multi-text was specified but no input received from --text or stdin.", file=sys.stderr)

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
    
    source_text_for_filename = ""
    if args.text1_file:
        try:
            with open(args.text1_file, 'r', encoding='utf-8') as f:
                source_text_for_filename = f.read(1024)
        except Exception as e:
            print(f"Warning: Could not read {args.text1_file} for autonaming: {e}", file=sys.stderr)
    elif args.text:
         source_text_for_filename = args.text


    if args.output_file and (args.basename_add_timestamp or args.basename_add_first_words is not None):
        timestamp_id = datetime.now().strftime('%Y%m%d%H%M%S')
        output_directory, filename = os.path.dirname(args.output_file) or '.', os.path.basename(args.output_file)

        if args.basename_add_first_words is not None:
            filename_prefix = generate_filename_prefix_from_text(source_text_for_filename, args.basename_add_first_words)
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
    
    # --- Parse Anki Field Mapping and Header ---
    field_mapping = {}
    anki_header = []

    if args.anki_csv_header:
        try:
            anki_header = json.loads(args.anki_csv_header)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON for --anki-csv-header: {e}", file=sys.stderr)
            sys.exit(1)
    elif final_output_path:
        print("Error: --anki-csv-header is required when writing to an output file. The core engine no longer uses hardcoded defaults for unambiguousness.", file=sys.stderr)
        sys.exit(1)

    if args.anki_field_mapping:
        try:
            field_mapping = json.loads(args.anki_field_mapping)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON for --anki-field-mapping: {e}", file=sys.stderr)
            sys.exit(1)
    elif final_output_path:
        print("Error: --anki-field-mapping is required when writing to an output file. The core engine no longer uses hardcoded defaults for unambiguousness.", file=sys.stderr)
        sys.exit(1)
    # -------------------------------------------

    if args.lemmas_per_line:
        if not args.text1_file:
            print("Error: --text1-file is required for --lemmas-per-line mode.", file=sys.stderr); exit(1)
        if not final_output_path:
            print("Error: --output-file is required for --lemmas-per-line mode.", file=sys.stderr); exit(1)

        processed_output_file = process_lemmas_per_line(
            args.text1_file, final_output_path, lemma_index,
            de_dictionary, lemma_override_rules, args
        )
            
    elif args.type == "word":
        input_text = ""
        if args.text1_file:
            input_text = read_text_from_file(args.text1_file)
        elif args.text:
            input_text = args.text
        elif 'KARDENWORT_INPUT_TEXT' in os.environ:
            input_text = os.environ['KARDENWORT_INPUT_TEXT']
        elif not sys.stdin.isatty():
            input_text = sys.stdin.read()

        if not input_text and not args.text2_file:
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
             if not input_text:
                input_text = read_text_from_file(args.text1_file)

             processed_output_file = process_parallel_text_files(
                input_text, lemma_index, args.language, args.text2_file, args.text3_file,
                args.sentence_context_size, final_output_path,
                args.add_source_word_col, args.add_wordlist_col, args.add_sentence_index_col,
                args.add_header, args.wordlist_use_br, args.stdout_print_output_basename,
                args.de_gcs, gcs_automaton, args.de_gcs_add_parts_to_wordlist, de_dictionary, lemma_override_rules,
                args.de_gcs_pos_tags, field_mapping, anki_header, args, **processing_options
            )
        else:
             if not input_text:
                 print("Error: No input provided for single text processing.", file=sys.stderr); exit(1)
             processed_output_file = process_single_text(
                input_text, lemma_index, args.language, args.sentence_context_size,
                final_output_path, args.add_source_word_col, args.add_wordlist_col, args.add_sentence_index_col,
                args.add_header, args.wordlist_use_br, args.stdout_print_output_basename,
                args.de_gcs, gcs_automaton, args.de_gcs_add_parts_to_wordlist, de_dictionary, lemma_override_rules,
                args.de_gcs_pos_tags, field_mapping, anki_header, args, **processing_options
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
            args.add_wordlist_col, args.add_sentence_index_col, args.add_header, args.wordlist_use_br, args.stdout_print_output_basename,
            args.de_gcs_pos_tags, field_mapping, anki_header, args, **processing_options
        )

    if args.stdout_print_output_basename and processed_output_file:
        print(os.path.basename(processed_output_file), file=sys.stdout)

if __name__ == "__main__":
    main()