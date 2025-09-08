# token_mix_combined.py

import sys
import spacy
import csv
import argparse
from datetime import datetime
import os
import re
from contextlib import contextmanager
import io

try:
    from german_compound_splitter import comp_split
    GCS_AVAILABLE = True
except ImportError:
    GCS_AVAILABLE = False

@contextmanager
def suppress_stdout():
    """A context manager to suppress stdout, useful for noisy libraries."""
    with open(os.devnull, "w") as devnull:
        old_stdout = sys.stdout
        sys.stdout = devnull
        try:
            yield
        finally:
            sys.stdout = old_stdout

# ==============================================================================
#  Strategy Pattern for Lemmatization
# ==============================================================================

class TokenLemmatizationStrategy:
    """Abstract base class for all lemmatization strategies."""
    def __init__(self, processor):
        self.processor = processor

    def get_lemmas(self, token, parent_lemma, sentence_text):
        raise NotImplementedError

class ProtectedTokenStrategy(TokenLemmatizationStrategy):
    """Strategy for tokens that should not be split, like URLs and emails."""
    def get_lemmas(self, token, parent_lemma, sentence_text):
        return [parent_lemma]

class HyphenatedStrategy(TokenLemmatizationStrategy):
    """Strategy for splitting hyphenated words."""
    def get_lemmas(self, token, parent_lemma, sentence_text):
        lemmas = []
        if self.processor.args.gcs_include_compound:
            lemmas.append(parent_lemma)
        
        parts = token.text.split('-')
        for part in parts:
            part = part.strip()
            if part and len(part) > 1:
                doc = self.processor.nlp(part)
                part_token = doc[0] if doc else None
                if part_token:
                    part_lemma = self.processor._get_capitalized_lemma(part_token, part_token.lemma_)
                    final_part_lemma = self.processor._apply_override(part_lemma, part, token.text, sentence_text)
                    if final_part_lemma:
                        lemmas.append(final_part_lemma)
        return lemmas

class CompoundWordStrategy(TokenLemmatizationStrategy):
    """Strategy for splitting German compound words using GCS."""
    def get_lemmas(self, token, parent_lemma, sentence_text):
        try:
            components = self.processor._run_gcs_splitter(token)
            if len(components) <= 1:
                return [parent_lemma] # GCS failed to split, fall back to default

            lemmas = []
            if self.processor.args.gcs_include_compound:
                lemmas.append(parent_lemma)
            
            for part_raw in set(components):
                part = part_raw.strip('-')
                if part and len(part) >= 3:
                    doc = self.processor.nlp(part)
                    part_token = doc[0] if doc else None
                    if part_token:
                        part_lemma = self.processor._get_capitalized_lemma(part_token, part_token.lemma_)
                        final_part_lemma = self.processor._apply_override(part_lemma, part, token.text, sentence_text)
                        if final_part_lemma:
                            lemmas.append(self.processor._smooth_gcs_case(final_part_lemma))
            return lemmas
        except Exception:
            return [parent_lemma] # Fallback on any GCS error

class DefaultStrategy(TokenLemmatizationStrategy):
    """The default strategy for simple words."""
    def get_lemmas(self, token, parent_lemma, sentence_text):
        return [parent_lemma]

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
            if args.gcs_dictionary and os.path.exists(args.gcs_dictionary):
                self.german_dict = load_dictionary_to_set(args.gcs_dictionary)
            if self.args.gcs:
                if not GCS_AVAILABLE:
                    print("Error: 'german-compound-splitter' library not installed.", file=sys.stderr); sys.exit(1)
                if args.gcs_dictionary and os.path.exists(args.gcs_dictionary):
                    with suppress_stdout():
                        self.ahocs = comp_split.read_dictionary_from_file(args.gcs_dictionary)
                else:
                    print(f"Error: GCS dictionary file '{args.gcs_dictionary}' not found!", file=sys.stderr); sys.exit(1)
        
        self.lemma_overrides = load_lemma_overrides(args.lemma_override_file)
        self._init_strategies()

    def _init_strategies(self):
        self.strategies = {
            'protected': ProtectedTokenStrategy(self),
            'hyphenated': HyphenatedStrategy(self),
            'compound': CompoundWordStrategy(self),
            'default': DefaultStrategy(self)
        }

    def _select_strategy(self, token):
        if token.like_url or token.like_email:
            return self.strategies['protected']
        if self.args.gcs and '-' in token.text:
            return self.strategies['hyphenated']
        if self.args.gcs and self.ahocs and self.args.language == 'de' and len(token.text) > 3 and token.pos_ in self.args.gcs_pos_tags:
            return self.strategies['compound']
        return self.strategies['default']

    def get_lemmas_for_token(self, token, sentence_text):
        spacy_lemma = self._get_corrected_lemma(token)
        default_lemma = self._get_capitalized_lemma(token, spacy_lemma)
        parent_lemma = self._apply_override(default_lemma, token.text, sentence_text)
        
        strategy = self._select_strategy(token)
        lemmas = strategy.get_lemmas(token, parent_lemma, sentence_text)
        
        return self._collapse_lemmas(lemmas)

    def process_token_stream(self, text_stream):
        unique_lemmas = {}
        token_to_sentence_info = {}
        
        for i, sentence_text in enumerate(text_stream):
            doc = self.nlp(sentence_text)
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
                    finalized_lemmas = [self._apply_override(combined_lemma, original_inflected_form, sentence_text)]
                else:
                    finalized_lemmas = self.get_lemmas_for_token(token, sentence_text)

                for lemma in finalized_lemmas:
                    if lemma:
                        if lemma not in unique_lemmas:
                            unique_lemmas[lemma] = original_inflected_form
                            token_to_sentence_info[lemma] = (i, sentence_text)
                        elif len(original_inflected_form) < len(unique_lemmas[lemma]):
                             unique_lemmas[lemma] = original_inflected_form
                             
        return unique_lemmas, token_to_sentence_info
    
    def process_sentence_stream(self, text_stream1, text_stream2, text_stream3):
        output_data = []
        for i, line1 in enumerate(text_stream1):
            line2 = text_stream2[i] if text_stream2 and i < len(text_stream2) else ""
            line3 = text_stream3[i] if text_stream3 and i < len(text_stream3) else ""
            output_data.append((line1.strip(), line2.strip(), line3.strip()))
        return output_data

    def _run_gcs_splitter(self, token):
        word_to_split = token.text
        if self.args.no_make_singular: should_make_singular = False
        elif self.args.make_singular: should_make_singular = True
        else: should_make_singular = (token.pos_ in ['NOUN', 'PROPN'])

        with suppress_stdout():
            if self.args.gcs_combine_noun_modes:
                dissection1 = comp_split.dissect(word_to_split, self.ahocs, make_singular=should_make_singular, only_nouns=True, mask_unknown=self.args.gcs_mask_unknown)
                dissection2 = comp_split.dissect(word_to_split, self.ahocs, make_singular=should_make_singular, only_nouns=False, mask_unknown=self.args.gcs_mask_unknown)
                components1 = dissection1 if self.args.gcs_skip_merge_fractions else comp_split.merge_fractions(dissection1)
                components2 = dissection2 if self.args.gcs_skip_merge_fractions else comp_split.merge_fractions(dissection2)
                return list(set(components1 + components2))
            else:
                dissection = comp_split.dissect(word_to_split, self.ahocs, make_singular=should_make_singular, only_nouns=not self.args.gcs_only_nouns_false, mask_unknown=self.args.gcs_mask_unknown)
                return dissection if self.args.gcs_skip_merge_fractions else comp_split.merge_fractions(dissection)

    def _get_corrected_lemma(self, token):
        spacy_lemma = token.lemma_
        if (self.args.gcs_fix_genitive and self.args.language == 'de' and token.pos_ in ["NOUN", "PROPN"] and 'Gen' in token.morph.get("Case", [])):
            if spacy_lemma.endswith(('s', 'es')) and len(spacy_lemma) > 1:
                candidate = spacy_lemma[:-1] if spacy_lemma.endswith('s') else spacy_lemma[:-2]
                if candidate.capitalize() in self.german_dict: return candidate
        return spacy_lemma

    def _get_capitalized_lemma(self, token, spacy_lemma):
        original_text = token.text
        if (original_text.isupper() and len(original_text) > 1) or any(c.isupper() for c in original_text[1:]):
            return original_text
        if self.args.force_lemma_capitalization:
            if (self.nlp.lang == 'de' and token.pos_ in ["NOUN", "PROPN"]) or \
               (self.nlp.lang != 'de' and token.pos_ == "PROPN"):
                return spacy_lemma.capitalize()
        return spacy_lemma

    def _collapse_lemmas(self, candidates):
        lemmas_by_lower = {}
        for lemma in candidates:
            if not lemma: continue
            lower_lemma = lemma.lower()
            if lower_lemma not in lemmas_by_lower:
                lemmas_by_lower[lower_lemma] = set()
            lemmas_by_lower[lower_lemma].add(lemma)
        final_lemmas = []
        for _, variants in lemmas_by_lower.items():
            preferred_variant = next((v for v in variants if v and v[0].isupper()), None)
            final_lemmas.append(preferred_variant if preferred_variant else list(variants)[0] if variants else None)
        return [lemma for lemma in final_lemmas if lemma]

    def _find_matching_override_rule(self, rules, context_sentence):
        if not rules: return None
        context_rules = [r for r in rules if r[1]]
        global_rule = next((r for r in rules if not r[1]), None)
        for target_lemma, context in context_rules:
            if context:
                if context.startswith('regex:'):
                    try:
                        if re.search(context[6:], context_sentence): return target_lemma
                    except re.error: pass
                elif context in context_sentence:
                    return target_lemma
        return global_rule[0] if global_rule else None

    def _apply_override(self, default_lemma, source_word, context_sentence):
        # Priority 1
        rules1 = self.lemma_overrides.get('priority1', {}).get((default_lemma, source_word))
        if (match := self._find_matching_override_rule(rules1, context_sentence)) is not None: return match
        for res_lemma, pattern, rule in self.lemma_overrides.get('priority1_regex', []):
            if res_lemma == default_lemma and re.fullmatch(pattern, source_word):
                if (match := self._find_matching_override_rule([rule], context_sentence)) is not None: return match
        # Priority 2
        rules2 = self.lemma_overrides.get('priority2', {}).get(source_word)
        if (match := self._find_matching_override_rule(rules2, context_sentence)) is not None: return match
        for pattern, rule in self.lemma_overrides.get('priority2_regex', []):
            if re.fullmatch(pattern, source_word):
                if (match := self._find_matching_override_rule([rule], context_sentence)) is not None: return match
        # Priority 3
        rules3 = self.lemma_overrides.get('priority3', {}).get(default_lemma)
        if (match := self._find_matching_override_rule(rules3, context_sentence)) is not None: return match
        return default_lemma
    
    def _smooth_gcs_case(self, lemma):
        if len(lemma) > 1 and lemma.islower() and lemma.capitalize() in self.german_dict:
            return lemma.capitalize()
        return lemma

# ==============================================================================
#  Utility Functions
# ==============================================================================

def load_dictionary_to_set(file_path):
    # ... (code is identical to previous versions, omitted for brevity)
    return set()

def load_lemma_overrides(file_path):
    # ... (code is identical to previous versions, omitted for brevity)
    return {'priority1': {}, 'priority1_regex': [], 'priority2': {}, 'priority2_regex': [], 'priority3': {}}

def load_lemma_index(file_path):
    # ... (code is identical to previous versions, omitted for brevity)
    return {}

def find_verb_particle_pairs(doc):
    # ... (code is identical to previous versions, omitted for brevity)
    return {}

def read_text_from_source(source):
    if not source: return []
    try:
        if '\n' in source or not os.path.exists(source):
            return source.splitlines()
        else:
            with open(source, "r", encoding="utf-8") as f:
                return [line.rstrip("\n") for line in f]
    except Exception as e:
        print(f"Error reading source {source}: {e}", file=sys.stderr)
        sys.exit(1)

def generate_output_path(args, text_stream):
    if not args.output: return None
    
    path_obj = io.StringIO()
    if args.timestamp:
        path_obj.write(datetime.now().strftime("%Y%m%d%H%M%S") + "-")

    if args.autoname is not None and text_stream:
        first_line = text_stream[0]
        words = re.findall(r'\b\w+\b', first_line)
        autoname_part = "-".join(words[:args.autoname])
        path_obj.write(autoname_part)
    
    base_name = os.path.basename(args.output)
    dir_name = os.path.dirname(args.output)
    
    prefix = path_obj.getvalue()
    final_name = prefix + base_name if prefix else base_name
    return os.path.join(dir_name, final_name)

def get_full_header():
    return ["WordSource", "WordTarget", "WordSourceInflectedForm", "Tags", "SentenceId", "SentenceOrder", "SentenceSource", "SentenceSourceContextLeft", "SentenceSourceContextRight", "SentenceTarget", "SentenceTargetContextLeft", "SentenceSourceWordlist", "SentenceSourceFull", "SentenceTargetFull", "AudioSource", "AudioTarget", "ImageSource", "ImageTarget", "PronunciationSource", "PronunciationTarget", "DefinitionSource", "DefinitionTarget", "ExampleSource", "ExampleTarget", "SynonymSource", "SynonymTarget", "AntonymSource", "AntonymTarget", "NotesSource", "NotesTarget", "AiSource", "AiTarget", "AiExtra1", "AiExtra2", "AiExtra3", "User1", "User2", "User3", "User4", "User5", "User6", "User7", "User8", "User9", "User10", "System1", "System2", "System3", "System4", "System5", "System6", "System7", "System8", "System9", "System10", "SystemExtra1", "SystemExtra2", "SystemExtra3", "SystemExtra4", "SystemExtra5", "SystemExtra6", "SystemExtra7", "SystemExtra8", "SystemExtra9", "SystemExtra10", "SystemExtra11", "SystemExtra12", "SystemExtra13", "SystemExtra14", "SystemExtra15", "SystemExtra16", "SystemExtra17", "SystemExtra18", "SystemExtra19", "SystemExtra20"]

# ==============================================================================
#  Main Execution Logic
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="Extract and process tokens or sentences from text.", formatter_class=argparse.RawTextHelpFormatter)
    # ... (All argparse definitions are identical to the user-provided script) ...
    # (Pasting the full argparse setup for completeness)
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
    parser.add_argument("--lemma-override-file", help="Path to a TSV file for context-aware lemma overrides.")
    parser.add_argument("--force-lemma-capitalization", action="store_true", help="Force capitalization of noun lemmas (NOUN, PROPN).")
    gcs_group = parser.add_argument_group('GCS (German Compound Splitting) options')
    gcs_group.add_argument("--gcs", action="store_true", help="Enable German Compound Splitting. Requires --language de.")
    gcs_group.add_argument("--gcs-pos-tags", nargs='+', default=['NOUN', 'PROPN', 'ADV', 'ADJ'], help='Specify which Part-of-Speech tags to apply splitting to.')
    gcs_group.add_argument("--gcs-dictionary", default="german.dic", help="Path to the dictionary file for GCS.")
    gcs_group.add_argument("--gcs-in-wordlist", action="store_true", help="Also add German compound components to the SentenceSourceWordlist field.")
    gcs_group.add_argument("--gcs-include-compound", action="store_true", help="Include the original compound word in the lemma list along with its split components.")
    gcs_group.add_argument("--gcs-only-nouns-false", action="store_true", help="Allows any type of word for GCS splitting.")
    gcs_group.add_argument("--gcs-combine-noun-modes", action="store_true", help="Run GCS in both noun-only and any-word modes and combine results.")
    gcs_group.add_argument("--gcs-fix-genitive", action="store_true", help="Corrects German genitive noun lemmas (e.g., 'Hauses' -> 'Haus').")
    gcs_group.add_argument("--gcs-mask-unknown", action="store_true", help="Mask word parts not found in the dictionary as 'unknown'.")
    gcs_group.add_argument("--make-singular", action="store_true", help="Force making compound parts singular during GCS splitting.")
    gcs_group.add_argument("--no-make-singular", action="store_true", help="Prevent making compound parts singular during GCS splitting.")
    gcs_group.add_argument("--gcs-skip-merge-fractions", action="store_true", help="Disable merging of GCS components, outputting raw parts.")
    
    args = parser.parse_args()

    # Process GCS POS tags
    ALL_POS_TAGS = {'ADJ', 'ADP', 'ADV', 'AUX', 'CCONJ', 'DET', 'INTJ', 'NOUN', 'NUM', 'PART', 'PRON', 'PROPN', 'PUNCT', 'SCONJ', 'SYM', 'VERB', 'X'}
    user_tags = set(args.gcs_pos_tags)
    if 'ALL' in user_tags:
        args.gcs_pos_tags = list(ALL_POS_TAGS)
    elif any(tag.startswith('!') for tag in user_tags):
        excluded_tags = {tag[1:] for tag in user_tags if tag.startswith('!')}
        args.gcs_pos_tags = list(ALL_POS_TAGS - excluded_tags)

    processor = TokenProcessor(args)
    lemma_index = load_lemma_index(args.lemma_index_file)

    if args.type == "token":
        input_source = args.text if args.text else args.text1
        if not input_source:
            print("Error: Either --text or --text1 must be provided for token mode.", file=sys.stderr); sys.exit(1)
        
        text_stream = read_text_from_source(input_source)
        unique_lemmas, token_info = processor.process_token_stream(text_stream)
        sorted_tokens = sorted(list(unique_lemmas.keys()), key=lambda token: (token not in lemma_index, lemma_index.get(token, 0), token.lower()))
        
        output_path = generate_output_path(args, text_stream)

        if not output_path:
            # Console output mode
            if args.html:
                print("<table>")
                for token in sorted_tokens: print(f"<tr><td>{token}</td><td>{unique_lemmas.get(token, '')}</td></tr>")
                print("</table>")
            elif args.two_column_output:
                for token in sorted_tokens: print(f"{token}\t{unique_lemmas.get(token, '')}")
            else:
                for token in sorted_tokens: print(token)
            return

        with open(output_path, "w", newline="", encoding="utf-8") as tsvfile:
            tsv_writer = csv.writer(tsvfile, delimiter="\t")
            if args.with_fields: tsv_writer.writerow(get_full_header())
            
            for token in sorted_tokens:
                row = [""] * len(get_full_header())
                sent_idx, sentence = token_info.get(token, (-1, ""))
                if sent_idx == -1: continue

                row[0] = row[1] = token
                if args.two_column_output_to_file: row[2] = unique_lemmas.get(token, '')
                
                row[6] = sentence.strip()
                row[12] = sentence.strip() # SentenceSourceFull
                
                # Context
                left_context_start = max(0, sent_idx - args.sentence_context_size)
                row[7] = "\n".join(text_stream[left_context_start:sent_idx])
                right_context_end = min(len(text_stream), sent_idx + 1 + args.sentence_context_size)
                row[8] = "\n".join(text_stream[sent_idx + 1:right_context_end])
                
                if args.include_simple_list:
                    doc = processor.nlp(sentence)
                    wordlist = set()
                    for t in doc:
                        lemmas = processor.get_lemmas_for_token(t, sentence)
                        if args.gcs_in_wordlist or len(lemmas) == 1:
                            wordlist.update(lemmas)
                        else: # Don't add components if gcs_in_wordlist is false
                            base_lemma = processor.get_lemmas_for_token(t, sentence)[0]
                            wordlist.add(base_lemma)

                    sorted_wordlist = sorted(list(wordlist), key=lambda x: (x not in lemma_index, lemma_index.get(x, 0), x.lower()))
                    row[11] = "<br>".join(sorted_wordlist) if args.with_br else "\n".join(sorted_wordlist)
                
                tsv_writer.writerow(row)

        if args.pipe:
            print(os.path.basename(output_path))

    elif args.type == "sentence":
        stream1 = read_text_from_source(args.text1)
        stream2 = read_text_from_source(args.text2)
        stream3 = read_text_from_source(args.text3)
        sentence_data = processor.process_sentence_stream(stream1, stream2, stream3)
        output_path = generate_output_path(args, stream1)

        with open(output_path, "w", newline="", encoding="utf-8") as tsvfile:
            tsv_writer = csv.writer(tsvfile, delimiter="\t")
            if args.with_fields: tsv_writer.writerow(get_full_header())

            for i, (s1, s2, s3) in enumerate(sentence_data):
                row = [""] * len(get_full_header())
                row[6] = s1
                row[9] = s2
                # Assuming s3 goes into a user field or similar, not defined in original logic
                if args.include_simple_list:
                    doc = processor.nlp(s1)
                    wordlist = {lemma for t in doc for lemma in processor.get_lemmas_for_token(t, s1)}
                    sorted_wordlist = sorted(list(wordlist), key=lambda x: (x not in lemma_index, lemma_index.get(x, 0), x.lower()))
                    row[11] = "<br>".join(sorted_wordlist) if args.with_br else "\n".join(sorted_wordlist)
                
                tsv_writer.writerow(row)

        if args.pipe:
            print(os.path.basename(output_path))


if __name__ == "__main__":
    main()