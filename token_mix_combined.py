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

# ==============================================================================
#  Resource Loading & Helper Functions
# ==============================================================================

def _smooth_gcs_case(lemma):
    if not lemma or len(lemma) < 2:
        return lemma
    return lemma[0] + lemma[1:].lower()

def load_dictionary_to_set(file_path):
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

def load_lemma_overrides(file_path):
    overrides = {'priority1': {}, 'priority1_regex': [], 'priority2': {}, 'priority2_regex': [], 'priority3': {}}
    if not file_path: return overrides
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter="\t")
            for i, row in enumerate(reader):
                if not row or row[0].startswith('#'): continue
                if len(row) < 3: continue

                match_spacy_lemma, raw_match_source_word, result_override_lemma = row[0].strip(), row[1], row[2].strip()
                raw_context = row[3] if len(row) > 3 and row[3] else None

                if not result_override_lemma or (not match_spacy_lemma and not raw_match_source_word.strip()): continue

                context = raw_context.strip() if raw_context and not raw_context.startswith('regex:') else raw_context
                rule = (result_override_lemma, context)
                is_regex_word = raw_match_source_word.startswith('regex:')
                match_source_word = raw_match_source_word.strip()

                if match_spacy_lemma and match_source_word:
                    if is_regex_word: overrides['priority1_regex'].append((match_spacy_lemma, raw_match_source_word[6:], rule))
                    else:
                        key = (match_spacy_lemma, match_source_word)
                        if key not in overrides['priority1']: overrides['priority1'][key] = []
                        overrides['priority1'][key].append(rule)
                elif match_source_word:
                    if is_regex_word: overrides['priority2_regex'].append((raw_match_source_word[6:], rule))
                    else:
                        key = match_source_word
                        if key not in overrides['priority2']: overrides['priority2'][key] = []
                        overrides['priority2'][key].append(rule)
                elif match_spacy_lemma:
                    key = match_spacy_lemma
                    if key not in overrides['priority3']: overrides['priority3'][key] = []
                    overrides['priority3'][key].append(rule)
    except FileNotFoundError:
        print(f"Lemma override file not found: {file_path}", file=sys.stderr)
    except Exception as e:
        print(f"Error reading lemma override file {file_path}: {e}", file=sys.stderr)
    return overrides

def load_lemma_index(file_path):
    lemma_index = {}
    if not file_path: return lemma_index
    try:
        with open(file_path, "r", newline="", encoding="utf-8") as csvfile:
            csv_reader = csv.reader(csvfile)
            for line_number, row in enumerate(csv_reader):
                if row and row[0] not in lemma_index:
                    lemma_index[row[0]] = line_number
    except FileNotFoundError:
        print(f"File not found: {file_path}", file=sys.stderr)
    except Exception as e:
        print(f"Error reading file {file_path}: {e}", file=sys.stderr)
    return lemma_index

def find_verb_particle_pairs(doc):
    pairs = {}
    for token in doc:
        if token.dep_ == "svp":
            pairs[token.head.i] = token
    return pairs

def get_full_header():
    return ["Quotation", "WordSource", "WordSourceInflectedForm", "WordDestination", "WordSourceContext", "SentenceSourceContextLeft", "SentenceSource", "SentenceSourceContextRight", "SentenceDestinationContextLeft", "SentenceDestination", "SentenceDestinationContextRight", "SentenceSourceWordlist", "SentenceSourceCloze", "SentenceSourceRewriteAISentenceSource", "SentenceSourceRewriteAISentenceDestination", "WordSourceMorphologyAI", "Note", "WordRussian", "WordUkrainian", "WordEnglish", "WordGerman", "WordSourceMorphemeFirst", "WordSourceMorphemeFirstDefinition", "WordSourceMorphemeSecond", "WordSourceMorphemeSecondDefinition", "WordSourceMorphemeThird", "WordSourceMorphemeThirdDefinition", "WordSourceMorphemeFourth", "WordSourceMorphemeFourthDefinition", "WordSourceMorphemeFifth", "WordSourceMorphemeFifthDefinition", "WordSourceIPA", "WordSourceSynonymAI", "WordSourceDefinitionAISentenceSource", "WordSourceDefinitionAISentenceDestination", "WordSourceDefinitionFirst", "WordSourceDefinitionFirstClipping", "WordSourceDefinitionSecond", "WordDestinationDefinitionFirst", "WordDestinationDefinitionSecond", "WordSourceAudio", "SentenceSourceIPA", "SentenceSourceAudio", "Image", "WordSourceCloze", "WordSourceContextAI", "TextSource", "TextDestination", "TextSourceURL", "SentenceEnglish", "SentenceGerman", "SentenceUkrainian", "SentenceRussian", "Source", "SourceURL", "SeparatorAudio", "Source-en-GB", "Source-en-US", "Source-de-DE", "Source-uk-UA", "Source-ru-RU", "Destination-en-GB", "Destination-en-US", "Destination-de-DE", "Destination-uk-UA", "Destination-ru-RU", "Overlapping", "ToggleAlwaysEmptyField", "Note ID", "am-all-morphs", "am-all-morphs-count", "am-unknown-morphs", "am-unknown-morphs-count", "am-highlighted", "am-score", "am-score-terms", "am-study-morphs", "SentenceDestination2ContextLeft", "SentenceDestination2", "SentenceDestination2ContextRight"]

# ==============================================================================
#  Core Token Processing Class
# ==============================================================================

class TokenProcessor:
    def __init__(self, args):
        self.args = args
        self.nlp = spacy.load("de_core_news_lg" if args.language == "de" else "en_core_web_lg")
        self.german_dict = set()
        self.ahocs = None

        if args.language == 'de':
            self.german_dict = load_dictionary_to_set(args.gcs_dictionary)
            if not self.german_dict:
                 print("Warning: German dictionary for validation is empty or not loaded.", file=sys.stderr)

            if args.gcs:
                if not GCS_AVAILABLE:
                    print("Error: 'german-compound-splitter' library not installed.", file=sys.stderr); sys.exit(1)
                if not os.path.exists(args.gcs_dictionary):
                    print(f"Error: GCS dictionary file '{args.gcs_dictionary}' not found!", file=sys.stderr); sys.exit(1)
                try:
                    with redirect_stdout(io.StringIO()):
                        self.ahocs = comp_split.read_dictionary_from_file(args.gcs_dictionary)
                except Exception as e:
                    print(f"Error loading GCS dictionary: {e}", file=sys.stderr); sys.exit(1)

        self.lemma_overrides = load_lemma_overrides(args.lemma_override_file)

    def get_lemmas_for_token(self, token, sentence_text):
        candidate_lemmas = []
        is_protected_token = token.like_url or token.like_email

        spacy_lemma = self._get_corrected_lemma(token)
        default_lemma = self._get_capitalized_lemma(token, spacy_lemma)
        parent_lemma = self._apply_word_override(default_lemma, token.text, sentence_text)

        was_split = False

        if self.args.gcs and '-' in token.text and not is_protected_token:
            was_split = True
            if self.args.gcs_include_compound:
                candidate_lemmas.append(parent_lemma)
            parts = token.text.split('-')
            for part in parts:
                part = part.strip()
                if part and len(part) > 1:
                    part_doc = self.nlp(part)
                    if not part_doc: continue
                    default_part_lemma = self._get_lemma_for_compound_part(part, part_doc[0])
                    final_part_lemma = self._apply_word_override(default_part_lemma, part, sentence_text)
                    if final_part_lemma: candidate_lemmas.append(final_part_lemma)

        elif self.args.gcs and self.ahocs and self.args.language == 'de' and not is_protected_token and len(token.text) > 3 and (token.pos_ in self.args.gcs_pos_tags):
            try:
                final_components = self._run_gcs_splitter(token)
                if len(final_components) > 1:
                    was_split = True
                    if self.args.gcs_include_compound:
                        candidate_lemmas.append(parent_lemma)
                    for part_raw in set(final_components):
                        part = part_raw.strip('-')
                        if part and len(part) >= 3:
                            part_doc = self.nlp(part)
                            if not part_doc: continue
                            default_part_lemma = self._get_lemma_for_compound_part(part, part_doc[0])
                            overridden_lemma = self._apply_word_override(default_part_lemma, part, sentence_text)
                            final_part_lemma = _smooth_gcs_case(overridden_lemma)
                            if final_part_lemma: candidate_lemmas.append(final_part_lemma)
            except Exception:
                was_split = False

        if not was_split:
            candidate_lemmas.append(parent_lemma)

        return self._collapse_lemmas(candidate_lemmas)

    def get_lemmas_for_sentence(self, sentence_text):
        doc = self.nlp(sentence_text)
        verb_particle_map = find_verb_particle_pairs(doc)
        processed_particles_indices = {p.i for p in verb_particle_map.values()}
        final_tokens = set()

        for token in doc:
            if token.i in processed_particles_indices or not (token.is_alpha or '-' in token.text):
                continue

            original_inflected_form = token.text
            finalized_lemmas = []
            if token.i in verb_particle_map:
                particle = verb_particle_map[token.i]
                combined_lemma = f"{particle.text.lower()}{token.lemma_}".lower()
                original_inflected_form = f"{token.text} {particle.text}"
                finalized_lemmas = [self._apply_word_override(combined_lemma, original_inflected_form, sentence_text)]
            else:
                finalized_lemmas = self.get_lemmas_for_token(token, sentence_text)

            for lemma in finalized_lemmas:
                 if lemma:
                    final_tokens.add(lemma)
        return list(final_tokens)

    def process_text_stream(self, text_stream):
        unique_lemmatized_tokens = {}
        token_to_sentence_info = {}

        for i, sentence_text in enumerate(text_stream):
            doc = self.nlp(sentence_text.strip())
            verb_particle_map = find_verb_particle_pairs(doc)
            processed_particles_indices = {p.i for p in verb_particle_map.values()}

            for token in doc:
                if token.i in processed_particles_indices or not (token.is_alpha or '-' in token.text):
                    continue

                original_inflected_form = token.text
                if token.i in verb_particle_map:
                    particle = verb_particle_map[token.i]
                    combined_lemma = f"{particle.text.lower()}{token.lemma_}".lower()
                    original_inflected_form = f"{token.text} {particle.text}"
                    finalized_lemmas = [self._apply_word_override(combined_lemma, original_inflected_form, sentence_text)]
                else:
                    finalized_lemmas = self.get_lemmas_for_token(token, sentence_text)

                for lemma in finalized_lemmas:
                    if lemma:
                        if lemma not in unique_lemmatized_tokens:
                            unique_lemmatized_tokens[lemma] = original_inflected_form
                            token_to_sentence_info[lemma] = (i, sentence_text)
                        elif len(original_inflected_form) < len(unique_lemmatized_tokens[lemma]):
                             unique_lemmatized_tokens[lemma] = original_inflected_form

        return unique_lemmatized_tokens, token_to_sentence_info

    def _run_gcs_splitter(self, token):
        word_to_split = token.text
        if self.args.no_make_singular: should_make_singular = False
        elif self.args.make_singular: should_make_singular = True
        else: should_make_singular = (token.pos_ in ['NOUN', 'PROPN'])

        final_components = []
        with redirect_stdout(io.StringIO()):
            if self.args.gcs_combine_noun_modes:
                dissection1 = comp_split.dissect(word_to_split, self.ahocs, make_singular=should_make_singular, only_nouns=True, mask_unknown=self.args.gcs_mask_unknown)
                dissection2 = comp_split.dissect(word_to_split, self.ahocs, make_singular=should_make_singular, only_nouns=False, mask_unknown=self.args.gcs_mask_unknown)
                if self.args.gcs_skip_merge_fractions:
                    final_components.extend(dissection1); final_components.extend(dissection2)
                else:
                    final_components.extend(comp_split.merge_fractions(dissection1)); final_components.extend(comp_split.merge_fractions(dissection2))
            else:
                gcs_only_nouns = not self.args.gcs_only_nouns_false
                dissection = comp_split.dissect(word_to_split, self.ahocs, make_singular=should_make_singular, only_nouns=gcs_only_nouns, mask_unknown=self.args.gcs_mask_unknown)
                final_components = dissection if self.args.gcs_skip_merge_fractions else comp_split.merge_fractions(dissection)
        return final_components

    def _get_corrected_lemma(self, token):
        spacy_lemma = token.lemma_
        if (self.args.gcs_fix_genitive and self.nlp.lang == 'de' and token.pos_ in ["NOUN", "PROPN"] and 'Gen' in token.morph.get("Case", [])):
            if spacy_lemma.endswith('s') and len(spacy_lemma) > 1:
                candidate_lemma = spacy_lemma[:-1]
                if candidate_lemma.capitalize() in self.german_dict:
                    return candidate_lemma
        return spacy_lemma

    def _get_lemma_for_compound_part(self, part_text, part_token):
        if part_text.isupper() and len(part_text) > 1 or any(c.isupper() for c in part_text[1:]): return part_text
        if part_token.pos_ not in ["NOUN", "PROPN"]: return part_token.lemma_
        spacy_lemma = part_token.lemma_.capitalize()
        original_part_capitalized = part_text.capitalize()
        if spacy_lemma in self.german_dict: return spacy_lemma
        if original_part_capitalized in self.german_dict: return original_part_capitalized
        return spacy_lemma

    def _get_capitalized_lemma(self, token, spacy_lemma):
        if token.like_url or token.like_email: return spacy_lemma.lower()
        original_text = token.text
        if (original_text.isupper() and len(original_text) > 1) or any(c.isupper() for c in original_text[1:]): return original_text
        if self.args.force_lemma_capitalization:
            if (self.nlp.lang == 'de' and token.pos_ in ["NOUN", "PROPN"]) or (self.nlp.lang != 'de' and token.pos_ == "PROPN"):
                return spacy_lemma.capitalize()
        if token.is_sent_start and token.pos_ not in ["NOUN", "PROPN"]: return spacy_lemma
        return spacy_lemma

    def _collapse_lemmas(self, candidates):
        lemmas_by_lower = {}
        for lemma in candidates:
            if not lemma: continue
            lower_lemma = lemma.lower()
            if lower_lemma not in lemmas_by_lower: lemmas_by_lower[lower_lemma] = set()
            lemmas_by_lower[lower_lemma].add(lemma)
        final_lemmas = []
        for _, variants in lemmas_by_lower.items():
            preferred_variant = next((v for v in variants if v[0].isupper()), None)
            final_lemmas.append(preferred_variant if preferred_variant else list(variants)[0] if variants else None)
        return [lemma for lemma in final_lemmas if lemma]

    def _find_matching_override_rule(self, rules, context_sentence):
        if not rules: return None
        context_rules = [r for r in rules if r[1]]
        global_rule = next((r for r in rules if not r[1]), None)
        for target_lemma, context in context_rules:
            if context:
                if context.startswith('regex:'):
                    pattern = context[6:]
                    try:
                        if re.search(pattern, context_sentence): return target_lemma
                    except re.error as e:
                        print(f"Warning: Invalid regex in override rule: '{pattern}'. Error: {e}", file=sys.stderr)
                elif context in context_sentence:
                    return target_lemma
        return global_rule[0] if global_rule else None

    def _apply_word_override(self, default_lemma, source_word, context_sentence):
        rules1 = self.lemma_overrides.get('priority1', {}).get((default_lemma, source_word))
        if (match1 := self._find_matching_override_rule(rules1, context_sentence)) is not None: return match1
        for res_lemma, pattern, rule in self.lemma_overrides.get('priority1_regex', []):
            if res_lemma == default_lemma and re.fullmatch(pattern, source_word):
                if (match_regex1 := self._find_matching_override_rule([rule], context_sentence)) is not None: return match_regex1
        rules2 = self.lemma_overrides.get('priority2', {}).get(source_word)
        if (match2 := self._find_matching_override_rule(rules2, context_sentence)) is not None: return match2
        for pattern, rule in self.lemma_overrides.get('priority2_regex', []):
            if re.fullmatch(pattern, source_word):
                if (match_regex2 := self._find_matching_override_rule([rule], context_sentence)) is not None: return match_regex2
        rules3 = self.lemma_overrides.get('priority3', {}).get(default_lemma)
        if (match3 := self._find_matching_override_rule(rules3, context_sentence)) is not None: return match3
        return default_lemma

# ==============================================================================
#  Output and File Handling
# ==============================================================================

def read_text_from_source(source):
    try:
        if '\n' in source or not os.path.exists(source):
            return [line for line in source.splitlines() if line.strip()]
        else:
            with open(source, "r", encoding="utf-8") as f:
                return [line.rstrip("\n") for line in f if line.strip()]
    except Exception as e:
        print(f"Error reading source {source}: {e}", file=sys.stderr); sys.exit(1)

def generate_autoname_prefix(text, num_words):
    if not text: return ""
    processed_text = text.lower().replace('ä', 'ae').replace('ö', 'oe').replace('ü', 'ue').replace('ß', 'ss')
    words = re.findall(r'[a-z0-9]+', processed_text)
    return "-".join(words[:num_words]) if words else ""

def get_final_output_path(args, text_source_content):
    if not args.output: return None
    final_path = args.output
    if args.timestamp or args.autoname is not None:
        zid = datetime.now().strftime('%Y%m%d%H%M%S')
        output_dir, filename = os.path.dirname(args.output) or '.', os.path.basename(args.output)
        new_filename_part = ""
        if args.autoname is not None:
            autoname_part = generate_autoname_prefix(text_source_content, args.autoname)
            if autoname_part:
                first_dot_pos = filename.find('.')
                suffix = filename[first_dot_pos:] if first_dot_pos != -1 else ""
                new_filename_part = f"{autoname_part}{suffix}"
        if new_filename_part:
            final_path = os.path.join(output_dir, f"{zid}-{new_filename_part}")
        else:
            final_path = os.path.join(output_dir, f"{zid}-{filename}")
    return final_path

# ==============================================================================
#  Execution Logic
# ==============================================================================

def run_token_mode(args, processor, lemma_index):
    input_source_content = ""
    if args.text and args.text1: print("Error: --text and --text1 are mutually exclusive.", file=sys.stderr); sys.exit(1)
    if args.text:
        input_source_content = args.text
        text_stream = [line for line in args.text.splitlines() if line.strip()]
    elif args.text1:
        text_stream = read_text_from_source(args.text1)
        input_source_content = "\n".join(text_stream)
    else:
        print("Error: Either --text or --text1 must be specified for token mode.", file=sys.stderr); sys.exit(1)

    unique_lemmas, token_info = processor.process_text_stream(text_stream)
    sorted_tokens = sorted(list(unique_lemmas.keys()), key=lambda token: (token not in lemma_index, lemma_index.get(token, 0), token.lower()))

    output_path = get_final_output_path(args, input_source_content)

    if not output_path:
        if args.html:
            print("<table>")
            for token in sorted_tokens: print(f"<tr><td>{token}</td><td>{unique_lemmas.get(token, '')}</td></tr>")
            print("</table>")
        elif args.two_column_output:
            for token in sorted_tokens: print(f"{token}\t{unique_lemmas.get(token, '')}")
        else:
            for token in sorted_tokens: print(token)
        return None

    text2_lines = read_text_from_source(args.text2) if args.text2 else None
    text3_lines = read_text_from_source(args.text3) if args.text3 else None

    with open(output_path, "w", newline="", encoding="utf-8") as tsvfile:
        tsv_writer = csv.writer(tsvfile, delimiter="\t")
        if args.with_fields: tsv_writer.writerow(get_full_header())

        for token in sorted_tokens:
            row_data = [""] * 80
            sent_index, sentence = token_info.get(token, (-1, ""))
            if sent_index == -1: continue

            start_idx = max(0, sent_index - args.sentence_context_size)
            end_idx = sent_index + args.sentence_context_size + 1

            row_data[0] = row_data[1] = token
            row_data[2] = unique_lemmas.get(token, '') if args.two_column_output_to_file else ''
            row_data[5] = " ".join(line.strip() for line in text_stream[start_idx:sent_index])
            row_data[6] = row_data[12] = sentence.strip()
            row_data[7] = " ".join(line.strip() for line in text_stream[sent_index + 1:end_idx])
            if text2_lines:
                row_data[8] = " ".join(line.strip() for line in text2_lines[start_idx:sent_index])
                row_data[9] = text2_lines[sent_index].strip() if sent_index < len(text2_lines) else ""
                row_data[10] = " ".join(line.strip() for line in text2_lines[sent_index + 1:end_idx])
            if text3_lines:
                row_data[77] = " ".join(line.strip() for line in text3_lines[start_idx:sent_index])
                row_data[78] = text3_lines[sent_index].strip() if sent_index < len(text3_lines) else ""
                row_data[79] = " ".join(line.strip() for line in text3_lines[sent_index + 1:end_idx])

            if args.include_simple_list:
                lemmas = processor.get_lemmas_for_sentence(sentence)
                sorted_lemmas = sorted(lemmas, key=lambda x: (x not in lemma_index, lemma_index.get(x, 0), x.lower()))
                row_data[11] = "<br>".join(sorted_lemmas) if args.with_br else "\n".join(sorted_lemmas)
            tsv_writer.writerow(row_data)
    return output_path

def run_sentence_mode(args, processor, lemma_index):
    if not args.text1 or not args.text2:
        print("Error: --text1 and --text2 must be specified for sentence mode.", file=sys.stderr); sys.exit(1)
    
    text1_lines = read_text_from_source(args.text1)
    text2_lines = read_text_from_source(args.text2)
    text3_lines = read_text_from_source(args.text3) if args.text3 else []
    
    output_path = get_final_output_path(args, "\n".join(text1_lines))
    if not output_path:
        print("Error: --output must be specified for sentence mode.", file=sys.stderr); sys.exit(1)

    min_length = min(len(text1_lines), len(text2_lines))

    with open(output_path, "w", newline="", encoding="utf-8") as out_file:
        tsv_writer = csv.writer(out_file, delimiter="\t")
        if args.with_fields: tsv_writer.writerow(get_full_header())

        for i in range(min_length):
            row_data = [""] * 80
            start_idx = max(0, i - args.sentence_context_size)
            end_idx = i + args.sentence_context_size + 1

            l1_sentence = text1_lines[i].strip()
            row_data[0] = l1_sentence
            row_data[5] = " ".join(line.strip() for line in text1_lines[start_idx:i])
            row_data[6] = l1_sentence
            row_data[7] = " ".join(line.strip() for line in text1_lines[i + 1:end_idx])
            row_data[8] = " ".join(line.strip() for line in text2_lines[start_idx:i])
            row_data[9] = text2_lines[i].strip()
            row_data[10] = " ".join(line.strip() for line in text2_lines[i + 1:end_idx])
            row_data[12] = l1_sentence

            if args.include_simple_list:
                lemmas = processor.get_lemmas_for_sentence(l1_sentence)
                sorted_lemmas = sorted(lemmas, key=lambda x: (x not in lemma_index, lemma_index.get(x, 0), x.lower()))
                row_data[11] = "<br>".join(sorted_lemmas) if args.with_br else "\n".join(sorted_lemmas)

            if i < len(text3_lines):
                row_data[77] = " ".join(line.strip() for line in text3_lines[start_idx:i])
                row_data[78] = text3_lines[i].strip()
                row_data[79] = " ".join(line.strip() for line in text3_lines[i + 1:end_idx])

            tsv_writer.writerow(row_data)
    return output_path

def main():
    parser = argparse.ArgumentParser(description="Extract and process tokens or sentences from text.", formatter_class=argparse.RawTextHelpFormatter)
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
    parser.add_argument("--lemma-override-file", help="Path to a TSV file for context-aware lemma overrides.")
    parser.add_argument("--force-lemma-capitalization", action="store_true", help="Force capitalization of noun lemmas (NOUN, PROPN).")
    gcs_group = parser.add_argument_group('GCS (German Compound Splitting) options')
    gcs_group.add_argument("--gcs", action="store_true", help="Enable German Compound Splitting. Requires --language de.")
    gcs_group.add_argument("--gcs-pos-tags", nargs='+', default=['NOUN', 'PROPN', 'ADV', 'ADJ'], help='Specify which Part-of-Speech tags to apply splitting to.')
    gcs_group.add_argument("--gcs-dictionary", default="german.dic", help="Path to the dictionary file for GCS.")
    gcs_group.add_argument("--gcs-include-compound", action="store_true", help="Include the original compound word in the lemma list along with its split components.")
    gcs_group.add_argument("--gcs-only-nouns-false", action="store_true", help="Allows any type of word to be used for GCS splitting. Ignored if --gcs-combine-noun-modes is used.")
    gcs_group.add_argument("--gcs-combine-noun-modes", action="store_true", help="Run GCS in both modes (only_nouns=True and False) and combine the unique resulting components.")
    gcs_group.add_argument("--gcs-fix-genitive", action="store_true", help="Corrects German genitive noun lemmas (e.g., 'Hauses' -> 'Haus').")
    gcs_group.add_argument("--gcs-mask-unknown", action="store_true", help="During GCS splitting, mask word parts not found in the dictionary as 'unknown'.")
    gcs_group.add_argument("--make-singular", action="store_true", help="Force making compound parts singular during GCS splitting.")
    gcs_group.add_argument("--no-make-singular", action="store_true", help="Prevent making compound parts singular during GCS splitting.")
    gcs_group.add_argument("--gcs-skip-merge-fractions", action="store_true", help="Disable the merging of GCS components, outputting raw parts.")

    args = parser.parse_args()

    ALL_POS_TAGS = {'ADJ', 'ADP', 'ADV', 'AUX', 'CCONJ', 'DET', 'INTJ', 'NOUN', 'NUM', 'PART', 'PRON', 'PROPN', 'PUNCT', 'SCONJ', 'SYM', 'VERB', 'X'}
    user_tags = set(args.gcs_pos_tags)
    if 'ALL' in user_tags: args.gcs_pos_tags = list(ALL_POS_TAGS)
    elif any(tag.startswith('!') for tag in user_tags):
        excluded_tags = {tag[1:] for tag in user_tags if tag.startswith('!')}
        args.gcs_pos_tags = list(ALL_POS_TAGS - excluded_tags)

    processor = TokenProcessor(args)
    lemma_index = load_lemma_index(args.lemma_index_file)
    processed_output_file = None

    if args.type == "token":
        processed_output_file = run_token_mode(args, processor, lemma_index)
    elif args.type == "sentence":
        processed_output_file = run_sentence_mode(args, processor, lemma_index)

    if args.pipe and processed_output_file:
        print(os.path.basename(processed_output_file))

if __name__ == "__main__":
    main()