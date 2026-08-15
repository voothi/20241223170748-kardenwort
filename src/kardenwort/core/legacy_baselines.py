import os
import re
import csv
import json
import sys
from kardenwort.core.kardenwort import (
    _strip_markdown_header, parse_markdown_for_branch_headers, generate_filename_prefix_from_text,
    find_separable_verb_particle_pairs, find_token_mappings_in_text, _extract_mapped_token,
    _extract_standard_token, deduplicate_lemmas, sort_inflected_forms, get_lemma_sort_key,
    get_field_index_map, prepare_row_data, apply_field_mapping, extract_lemmas_from_sentence,
    _write_deck_metadata, read_text_from_file, is_composite_token
)

nlp = None

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

    order_cfg = getattr(args, 'combine_source_words_order', 'contractions_first')
    prefer_lowercase_cfg = getattr(args, 'combine_source_words_prefer_lowercase', True)
    apo_cfg = tuple(c.strip() for c in getattr(args, 'apostrophe_chars', "', ’, ‘, `, ´, ʼ").strip('"').split(',') if c.strip())

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
        token_mappings_matches, mapped_tokens = find_token_mappings_in_text(source_sentence, doc, kwargs.get('token_mappings', {}), args)

        for token in doc:
            if token.i in processed_particle_indices:
                continue

            mapped_lemma_sources = {}
            if token.i in mapped_tokens:
                if token.i in token_mappings_matches:
                    lemmas_for_current_token, mapped_sources = _extract_mapped_token(
                        token_mappings_matches[token.i], nlp, de_dictionary, lemma_override_rules, args, source_sentence, de_fix_genitive
                    )
                    mapped_lemma_sources.update(mapped_sources)
                else:
                    continue
            else:
                if not (token.is_alpha or ('-' in token.text and token.text.strip('-')) or is_composite_token(token.text)):
                    continue
                lemmas_for_current_token, mapped_sources = _extract_standard_token(
                    token, nlp, de_dictionary, lemma_override_rules, source_sentence, de_fix_genitive, 
                    de_gcs, gcs_automaton, de_gcs_pos_tags, args, separable_verb_map, 
                    de_gcs_only_nouns=de_gcs_only_nouns,
                    de_gcs_combine_noun_modes=de_gcs_combine_noun_modes,
                    de_gcs_mask_unknown_parts=de_gcs_mask_unknown_parts,
                    de_gcs_preserve_compound_word=de_gcs_preserve_compound_word,
                    de_gcs_skip_merge_fractions=de_gcs_skip_merge_fractions
                )
                mapped_lemma_sources.update(mapped_sources)

            deduplicated_lemmas = deduplicate_lemmas(lemmas_for_current_token)

            for lemma in deduplicated_lemmas:
                if not lemma:
                    continue
                
                cur_source_word = mapped_lemma_sources.get(lemma, token.text)
                if getattr(args, 'strip_garbage_characters', ''):
                    cur_source_word = cur_source_word.strip(args.strip_garbage_characters)
                
                data_entry = {
                    'lemma': lemma,
                    'source_word': cur_source_word,
                    'sentence_index': content_line_idx,
                    'source_sentence': source_sentence,
                    'deck_name': final_deck
                }

                if args.deduplication_scope == 'global':
                    is_new = lemma not in lemma_data['lemmas']
                    if is_new:
                        lemma_data['lemmas'][lemma] = cur_source_word
                        lemma_data['info'][lemma] = (content_line_idx, source_sentence, final_deck)
                    elif getattr(args, 'combine_source_words', False):
                        existing_forms = [s.strip() for s in lemma_data['lemmas'][lemma].split(',') if s.strip()]
                        if cur_source_word not in existing_forms:
                            existing_forms.append(cur_source_word)
                        lemma_data['lemmas'][lemma] = ", ".join(sort_inflected_forms(existing_forms, apo_cfg, order_cfg, prefer_lowercase_cfg))
                    elif args.prefer_shortest_form and len(cur_source_word) < len(lemma_data['lemmas'][lemma]):
                        lemma_data['lemmas'][lemma] = cur_source_word
                        lemma_data['info'][lemma] = (content_line_idx, source_sentence, final_deck)

                elif args.deduplication_scope == 'sentence':
                    if getattr(args, 'combine_source_words', False):
                        if lemma not in lemmas_in_sentence:
                            lemmas_in_sentence[lemma] = data_entry
                        else:
                            existing_forms = [s.strip() for s in lemmas_in_sentence[lemma]['source_word'].split(',') if s.strip()]
                            if cur_source_word not in existing_forms:
                                existing_forms.append(cur_source_word)
                            lemmas_in_sentence[lemma]['source_word'] = ", ".join(sort_inflected_forms(existing_forms, apo_cfg, order_cfg, prefer_lowercase_cfg))
                    else:
                        dedup_key = (lemma, cur_source_word.lower())
                        if dedup_key not in lemmas_in_sentence:
                            lemmas_in_sentence[dedup_key] = data_entry
                elif args.deduplication_scope == 'none':
                    lemma_data.append(data_entry)

        if args.deduplication_scope == 'sentence':
            lemma_data.extend(lemmas_in_sentence.values())

    sorted_items = []
    if args.deduplication_scope == 'global':
        sorted_items = sorted(list(lemma_data['lemmas'].keys()), key=lambda word: get_lemma_sort_key(word, lemma_sort_index, getattr(args, 'language', 'en')))
    else:
        sorted_items = sorted(lemma_data, key=lambda x: get_lemma_sort_key(x['lemma'], lemma_sort_index, getattr(args, 'language', 'en')))

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

                source_timestamps = getattr(args, 'source_timestamps', [])
                subtitle_start_time = source_timestamps[sentence_index] if sentence_index < len(source_timestamps) else ""

                context_join_str = "<br>" if args.anki_context_use_br else " "
                row_data = prepare_row_data(
                    args,
                    lemma=word,
                    source_word=source_word_col_val,
                    sentence_index=str(sentence_index + 1).zfill(6),
                    source_sentence=source_sentence_for_tsv,
                    source_context_left=context_join_str.join(line.strip() for line in display_source_content_lines[context_start_index:sentence_index]),
                    source_context_right=context_join_str.join(line.strip() for line in display_source_content_lines[sentence_index + 1:context_end_index]),
                    target_sentence=target_sentence_for_tsv,
                    target_context_left=context_join_str.join(line.strip() for line in display_target_content_lines[context_start_index:sentence_index]),
                    target_context_right=context_join_str.join(line.strip() for line in display_target_content_lines[sentence_index + 1:context_end_index]),
                    tertiary_sentence=tertiary_sentence_for_tsv,
                    tertiary_context_left=context_join_str.join(line.strip() for line in display_tertiary_content_lines[context_start_index:sentence_index]),
                    tertiary_context_right=context_join_str.join(line.strip() for line in display_tertiary_content_lines[sentence_index + 1:context_end_index]),
                    wordlist=current_wordlist,
                    cloze=source_sentence_for_tsv,
                    deck_name=CSV_ROW_DECK_VAL,
                    subtitle_start_time=subtitle_start_time,
                    classifications=kwargs.get('classifications', {})
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

    unit_texts = []
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
                sentence_prefix = str(len(unit_texts) + 1).zfill(6)
                sentence_slug = generate_filename_prefix_from_text(line, 4)
                if sentence_slug:
                    sentence_deck_name = f"{final_deck}::{sentence_prefix}-{sentence_slug}"
                    final_deck = sentence_deck_name

            deck_map[len(unit_texts)] = final_deck
            unit_texts.append(line)
    else:
        if is_multiline_from_file:
            unit_texts = [line.strip() for line in source_lines if line.strip()]
        else:
            doc = nlp(source_text)
            unit_texts = [sent.text for sent in doc.sents]

    strip_config = {'source': False, 'translations': False}
    if args.strip_headers is not None:
        targets = args.strip_headers if args.strip_headers else ['all']
        if 'all' in targets or 'source' in targets:
            strip_config['source'] = True

    display_unit_texts = [_strip_markdown_header(unit) for unit in unit_texts] if strip_config['source'] else unit_texts

    lemma_data = {}
    if args.deduplication_scope == 'global':
        lemma_data = {'lemmas': {}, 'info': {}}
    else:
        lemma_data = []

    order_cfg = getattr(args, 'combine_source_words_order', 'contractions_first')
    prefer_lowercase_cfg = getattr(args, 'combine_source_words_prefer_lowercase', True)
    apo_cfg = tuple(c.strip() for c in getattr(args, 'apostrophe_chars', "', ’, ‘, `, ´, ʼ").strip('"').split(',') if c.strip())

    doc_cache = {}

    for unit_index, unit_text in enumerate(unit_texts):
        lemmas_in_sentence = {}
        if unit_text not in doc_cache:
            doc_cache[unit_text] = nlp(unit_text)
        unit_doc = doc_cache[unit_text]

        current_deck = deck_map.get(unit_index, "")

        separable_verb_map = find_separable_verb_particle_pairs(unit_doc)
        processed_particle_indices = {p.i for p in separable_verb_map.values()}

        token_mappings_matches, mapped_tokens = find_token_mappings_in_text(unit_text, unit_doc, kwargs.get('token_mappings', {}), args)

        for token in unit_doc:
            if token.i in processed_particle_indices:
                continue

            mapped_lemma_sources = {}
            if token.i in mapped_tokens:
                if token.i in token_mappings_matches:
                    lemmas_for_current_token, mapped_sources = _extract_mapped_token(
                        token_mappings_matches[token.i], nlp, de_dictionary, lemma_override_rules, args, unit_text, de_fix_genitive
                    )
                    mapped_lemma_sources.update(mapped_sources)
                else:
                    continue
            else:
                if not (token.is_alpha or ('-' in token.text and token.text.strip('-')) or is_composite_token(token.text)):
                    continue
                lemmas_for_current_token, mapped_sources = _extract_standard_token(
                    token, nlp, de_dictionary, lemma_override_rules, unit_text, de_fix_genitive, 
                    de_gcs, gcs_automaton, de_gcs_pos_tags, args, separable_verb_map, 
                    de_gcs_only_nouns=de_gcs_only_nouns,
                    de_gcs_combine_noun_modes=de_gcs_combine_noun_modes,
                    de_gcs_mask_unknown_parts=de_gcs_mask_unknown_parts,
                    de_gcs_preserve_compound_word=de_gcs_preserve_compound_word,
                    de_gcs_skip_merge_fractions=de_gcs_skip_merge_fractions
                )
                mapped_lemma_sources.update(mapped_sources)

            deduplicated_lemmas = deduplicate_lemmas(lemmas_for_current_token)

            for lemma in deduplicated_lemmas:
                if not lemma:
                    continue

                cur_source_word = mapped_lemma_sources.get(lemma, token.text)
                if getattr(args, 'strip_garbage_characters', ''):
                    cur_source_word = cur_source_word.strip(args.strip_garbage_characters)

                data_entry = {
                    'lemma': lemma,
                    'source_word': cur_source_word,
                    'sentence_index': unit_index,
                    'source_sentence': unit_text,
                    'deck_name': current_deck
                }

                if args.deduplication_scope == 'global':
                    is_new = lemma not in lemma_data['lemmas']
                    if is_new:
                        lemma_data['lemmas'][lemma] = cur_source_word
                        lemma_data['info'][lemma] = (unit_index, unit_text, current_deck)
                    elif getattr(args, 'combine_source_words', False):
                        existing_forms = [s.strip() for s in lemma_data['lemmas'][lemma].split(',') if s.strip()]
                        if cur_source_word not in existing_forms:
                            existing_forms.append(cur_source_word)
                        lemma_data['lemmas'][lemma] = ", ".join(sort_inflected_forms(existing_forms, apo_cfg, order_cfg, prefer_lowercase_cfg))
                    elif args.prefer_shortest_form and len(cur_source_word) < len(lemma_data['lemmas'][lemma]):
                        lemma_data['lemmas'][lemma] = cur_source_word
                        lemma_data['info'][lemma] = (unit_index, unit_text, current_deck)
                        
                elif args.deduplication_scope == 'sentence':
                    if getattr(args, 'combine_source_words', False):
                        if lemma not in lemmas_in_sentence:
                            lemmas_in_sentence[lemma] = data_entry
                        else:
                            existing_forms = [s.strip() for s in lemmas_in_sentence[lemma]['source_word'].split(',') if s.strip()]
                            if cur_source_word not in existing_forms:
                                existing_forms.append(cur_source_word)
                            lemmas_in_sentence[lemma]['source_word'] = ", ".join(sort_inflected_forms(existing_forms, apo_cfg, order_cfg, prefer_lowercase_cfg))
                    else:
                        dedup_key = (lemma, cur_source_word.lower())
                        if dedup_key not in lemmas_in_sentence:
                            lemmas_in_sentence[dedup_key] = data_entry
                elif args.deduplication_scope == 'none':
                    lemma_data.append(data_entry)

        if args.deduplication_scope == 'sentence':
            lemma_data.extend(lemmas_in_sentence.values())

    sorted_items = []
    if args.deduplication_scope == 'global':
        sorted_items = sorted(list(lemma_data['lemmas'].keys()), key=lambda word: get_lemma_sort_key(word, lemma_sort_index, getattr(args, 'language', 'en')))
    else:
        sorted_items = sorted(lemma_data, key=lambda x: get_lemma_sort_key(x['lemma'], lemma_sort_index, getattr(args, 'language', 'en')))
    
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
                
                source_sentence = display_unit_texts[unit_index].strip()
                context_start_index = max(0, unit_index - sentence_context_size)
                context_end_index = min(len(display_unit_texts), unit_index + sentence_context_size + 1)
                
                source_context_left = " ".join(u.strip() for u in display_unit_texts[context_start_index:unit_index])
                source_context_right = " ".join(u.strip() for u in display_unit_texts[unit_index + 1:context_end_index])
                
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
            
            source_sentence_for_tsv = display_unit_texts[unit_index].strip()
            context_start_index = max(0, unit_index - sentence_context_size)
            context_end_index = min(len(display_unit_texts), unit_index + sentence_context_size + 1)
            
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

            source_timestamps = getattr(args, 'source_timestamps', [])
            subtitle_start_time = source_timestamps[unit_index] if unit_index < len(source_timestamps) else ""

            context_join_str = "<br>" if args.anki_context_use_br else " "
            row_data = prepare_row_data(
                args,
                lemma=word,
                source_word=source_word_col_val,
                source_sentence=source_sentence_for_tsv,
                source_context_left=context_join_str.join(u.strip() for u in display_unit_texts[context_start_index:unit_index]),
                source_context_right=context_join_str.join(u.strip() for u in display_unit_texts[unit_index + 1:context_end_index]),
                wordlist=current_wordlist,
                cloze=source_sentence_for_tsv,
                sentence_index=str(unit_index + 1).zfill(6),
                deck_name=CSV_ROW_DECK_VAL,
                subtitle_start_time=subtitle_start_time,
                classifications=kwargs.get('classifications', {})
            )
            
            apply_field_mapping(csv_row, row_data, field_mapping, F)
            if getattr(args, 'structured_output', False):
                if len(anki_header) > 0:
                    record_dict = dict(zip(anki_header, csv_row))
                else:
                    record_dict = row_data
                print(json.dumps(record_dict, ensure_ascii=False), file=sys.stdout)
                sys.stdout.flush()
            else:
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

            source_timestamps = getattr(args, 'source_timestamps', [])
            subtitle_start_time = source_timestamps[content_line_idx] if content_line_idx < len(source_timestamps) else ""

            context_join_str = "<br>" if args.anki_context_use_br else " "
            row_data = prepare_row_data(
                args,
                source_sentence=source_sentence,
                source_context_left=context_join_str.join(line.strip() for line in display_source_content_lines[context_start_index:content_line_idx]),
                source_context_right=context_join_str.join(line.strip() for line in display_source_content_lines[content_line_idx + 1:context_end_index]),
                target_sentence=target_sentence,
                target_context_left=context_join_str.join(line.strip() for line in display_target_content_lines[context_start_index:content_line_idx]),
                target_context_right=context_join_str.join(line.strip() for line in display_target_content_lines[content_line_idx + 1:context_end_index]),
                tertiary_sentence=tertiary_sentence,
                tertiary_context_left=context_join_str.join(line.strip() for line in display_tertiary_content_lines[context_start_index:content_line_idx]),
                tertiary_context_right=context_join_str.join(line.strip() for line in display_tertiary_content_lines[content_line_idx + 1:context_end_index]),
                wordlist=current_wordlist,
                cloze=source_sentence,
                sentence_index=str(content_line_idx + 1).zfill(6),
                deck_name=final_deck_for_card,
                subtitle_start_time=subtitle_start_time,
                classifications=kwargs.get('classifications', {})
            )

            apply_field_mapping(csv_row, row_data, field_mapping, F)
            if getattr(args, 'structured_output', False):
                if len(anki_header) > 0:
                    record_dict = dict(zip(anki_header, csv_row))
                else:
                    record_dict = row_data
                print(json.dumps(record_dict, ensure_ascii=False), file=sys.stdout)
                sys.stdout.flush()
            else:
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


