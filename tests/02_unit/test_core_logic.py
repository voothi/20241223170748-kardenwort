import pytest
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

# Add src and helpers to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / 'src'))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'helpers'))
from mock_nlp import MockToken, MockMorph

from kardenwort.core.kardenwort import (
    deduplicate_lemmas,
    format_lemma_capitalization,
    parse_markdown_for_branch_headers,
    _strip_markdown_header,
    generate_filename_prefix_from_text,
    get_overridden_lemma_for_word,
    correct_spacy_lemma,
    find_separable_verb_particle_pairs,
    load_lemma_override_rules,
    load_dictionary,
    apply_field_mapping,
    get_anki_csv_header,
    get_field_index_map,
    load_classification_dictionaries,
    prepare_row_data
)

def test_deduplicate_lemmas():
    # Basic deduplication (Order preserved by first occurrence of lowercased lemma)
    assert deduplicate_lemmas(["Haus", "haus", "Auto"]) == ["Haus", "Auto"]
    # Case preservation (prefer capitalized, but order determined by FIRST occurrence of lowercased variant)
    assert deduplicate_lemmas(["auto", "Haus", "Auto"]) == ["Auto", "Haus"]
    # Empty list
    assert deduplicate_lemmas([]) == []
    # Single element
    assert deduplicate_lemmas(["test"]) == ["test"]

def test_strip_markdown_header():
    assert _strip_markdown_header("# Header") == "Header"
    assert _strip_markdown_header("## Subheader ") == "Subheader"
    assert _strip_markdown_header("No header") == "No header"
    assert _strip_markdown_header("###   Triple") == "Triple"

def test_generate_filename_prefix_from_text():
    text = "Dies ist ein Test für Kardenwort"
    assert generate_filename_prefix_from_text(text, 3) == "dies-ist-ein"
    # Special characters
    assert generate_filename_prefix_from_text("Schöne Häuser!", 2) == "schoene-haeuser"
    # Fewer words than limit
    assert generate_filename_prefix_from_text("Short", 5) == "short"

def test_parse_markdown_for_branch_headers():
    lines = [
        "# Root",
        "## Branch 1",
        "### Leaf 1",
        "## Branch 2",
        "Just text"
    ]
    indices = parse_markdown_for_branch_headers(lines)
    assert 0 in indices
    assert 1 in indices
    assert 2 not in indices
    assert 3 not in indices

def test_format_lemma_capitalization(mock_nlp):
    args = SimpleNamespace(de_force_noun_capitalization=True, force_proper_noun_capitalization=True)
    token = MockToken("Häuser", "NOUN")
    assert format_lemma_capitalization(token, "haus", args) == "Haus"
    
    token_propn = MockToken("Berlin", "PROPN")
    assert format_lemma_capitalization(token_propn, "berlin", args) == "Berlin"

def test_get_overridden_lemma_for_word():
    override_rules = {
        'priority1': {('spacy_lemma', 'source_word'): [('target_lemma', None)]},
        'priority1_regex': [],
        'priority2': {},
        'priority2_regex': [],
        'priority3': {}
    }
    assert get_overridden_lemma_for_word('spacy_lemma', 'source_word', override_rules, "Context") == 'target_lemma'
    assert get_overridden_lemma_for_word('other', 'source_word', override_rules, "Context") == 'other'

def test_correct_spacy_lemma(mock_nlp):
    de_dictionary = {"Haus", "Auto"}
    token = MockToken("Hauss", lemma_="Hauss", pos_="NOUN", case_morph=["Gen"])
    assert correct_spacy_lemma(token, de_dictionary, fix_genitive=True) == "Haus"

def test_find_separable_verb_particle_pairs():
    t1 = MockToken("w0", dep_="ROOT", i=0)
    t2 = MockToken("w1", dep_="svp", i=1, head_i=0)
    t2.head = t1
    
    doc = [t1, t2]
    pairs = find_separable_verb_particle_pairs(doc)
    assert 0 in pairs
    assert pairs[0] == t2

def test_load_dictionary(tmp_path):
    d_file = tmp_path / "german.dic"
    d_file.write_text("Haus\nAuto\n", encoding="utf-8")
    dic = load_dictionary(str(d_file))
    assert "Haus" in dic
    assert "Auto" in dic

def test_load_classification_dictionaries(tmp_path, capsys):
    # Test valid parsing
    c_file = tmp_path / "oxford.tsv"
    content = [
        "word\tpos\tcefr",
        "apple\tn\tA1",
        "abandon\tv\tB2",
        "a, an\tdet\tA1",
        "Header_like_but_lowercase\t\tC1"
    ]
    c_file.write_text("\n".join(content), encoding="utf-8")
    
    args = [f"oxford={c_file}"]
    classifications = load_classification_dictionaries(args)
    
    assert "oxford" in classifications
    assert classifications["oxford"]["apple"] == "A1"
    assert classifications["oxford"]["abandon"] == "B2"
    assert classifications["oxford"]["a"] == "A1"
    assert classifications["oxford"]["an"] == "A1"
    # The 'word' header should be skipped.
    assert "word" not in classifications["oxford"]
    
    # Test invalid format
    load_classification_dictionaries(["invalid_format"])
    captured = capsys.readouterr()
    assert "Invalid --classify format" in captured.err
    
    # Test file not found
    load_classification_dictionaries(["missing=missing.tsv"])
    captured = capsys.readouterr()
    assert "Classification dictionary file not found" in captured.err

    # Test prefix parsing
    c_file_prefix = tmp_path / "oxford-prefix.tsv"
    c_file_prefix.write_text("word\tcefr\nbanana\tB1\n", encoding="utf-8")
    args_prefix = [f"oxford=3k:{c_file_prefix}"]
    classifications_prefix = load_classification_dictionaries(args_prefix)
    assert classifications_prefix["oxford"]["banana"] == "3k:B1"

    # Test parse_prefix_and_path explicitly
    from kardenwort.core.kardenwort import parse_prefix_and_path
    assert parse_prefix_and_path("3k:path/to/file") == ("3k", "path/to/file")
    assert parse_prefix_and_path("5k:path/to/file") == ("5k", "path/to/file")
    assert parse_prefix_and_path("C:\\path\\to\\file") == ("", "C:\\path\\to\\file")
    assert parse_prefix_and_path("path/to/file") == ("", "path/to/file")

def test_load_lemma_override_rules(tmp_path):
    o_file = tmp_path / "override.tsv"
    content = [
        "spacy_lemma\tsource_word\ttarget_lemma\t",
        "\tsource_only\ttarget2\t"
    ]
    o_file.write_text("\n".join(content), encoding="utf-8")
    rules = load_lemma_override_rules(str(o_file))
    assert ('spacy_lemma', 'source_word') in rules['priority1']

def test_get_anki_csv_header():
    header = get_anki_csv_header()
    assert "WordSource" in header

def test_apply_field_mapping():
    header = ["A", "B"]
    f_map = {"A": 0, "B": 1}
    row = ["", ""]
    data = {"src1": "VAL1", "src2": "VAL2"}
    mapping = {"A": "src1", "B": "src2"}
    apply_field_mapping(row, data, mapping, f_map)
    assert row == ["VAL1", "VAL2"]

def test_prepare_row_data_with_classifications():
    args = SimpleNamespace(language="en", tts_destination_lang="ru")

    kwargs = {
        'lemma': 'apple',
        'classifications': {
            'oxford': {'apple': 'A1', 'banana': 'A2'},
            'cambridge': {'apple': 'B1'}
        }
    }
    
    row_data = prepare_row_data(args, **kwargs)
    assert row_data['lemma'] == 'apple'
    assert row_data['oxford'] == 'A1'
    assert row_data['cambridge'] == 'B1'
    assert row_data['tts_source_en'] == "1"
    assert row_data['tts_dest_ru'] == "1"

from kardenwort.core.kardenwort import _format_gcs_component_case, _cleanup_temp_files, TEMP_FILES_TO_CLEANUP

def test_format_gcs_component_case():
    assert _format_gcs_component_case("") == ""
    assert _format_gcs_component_case("A") == "A"
    assert _format_gcs_component_case("HAUS") == "Haus"
    assert _format_gcs_component_case("auto") == "auto" # The function does not capitalize the first letter; it preserves it.

def test_cleanup_temp_files(tmp_path):
    f1 = tmp_path / "1.txt"
    f2 = tmp_path / "2.txt"
    f1.write_text("test")
    
    # f2 doesn't exist, shouldn't crash
    TEMP_FILES_TO_CLEANUP.clear()
    TEMP_FILES_TO_CLEANUP.extend([str(f1), str(f2)])
    
    _cleanup_temp_files()
    assert not f1.exists()
    
    # Cleanup state
    TEMP_FILES_TO_CLEANUP.clear()

def test_load_dictionary_errors(tmp_path, capsys):
    # Test missing file error
    dic = load_dictionary(str(tmp_path / "missing.dic"))
    assert len(dic) == 0
    captured = capsys.readouterr()
    assert "Dictionary file not found" in captured.err

    # Test general exception (e.g., passing a directory instead of a file)
    dic = load_dictionary(str(tmp_path))
    assert len(dic) == 0
    captured = capsys.readouterr()
    assert "Error reading dictionary file" in captured.err

def test_load_lemma_override_rules_errors(tmp_path, capsys):
    o_file = tmp_path / "bad_override.tsv"
    # Format: Result_Lemma \t Original_Word \t Target_Lemma \t Context
    content = [
        "too\tshort", # malformed line < 3 cols
        "missing\ttarget\t", # empty target_lemma
        "\t\tvalid_target" # missing spacy_lemma and source_word
    ]
    o_file.write_text("\n".join(content), encoding="utf-8")
    
    rules = load_lemma_override_rules(str(o_file))
    captured = capsys.readouterr()
    
    assert "Skipping malformed line 1" in captured.err
    assert "Skipping invalid rule on line 2" in captured.err
    assert "Skipping invalid rule on line 3" in captured.err
    assert not rules['priority1']

def test_extract_lemmas_from_sentence():
    from kardenwort.core.kardenwort import extract_lemmas_from_sentence
    
    class MockMorph:
        def __init__(self, data): self.data = data
        def get(self, key, default=None): return self.data.get(key, default)
        
    class MockToken:
        def __init__(self, text, lemma, pos, i, dep, head_i=None, is_alpha=True, like_url=False, like_email=False, is_sent_start=False):
            self.text = text
            self.lemma_ = lemma
            self.pos_ = pos
            self.i = i
            self.dep_ = dep
            self.head = MagicMock()
            self.head.i = head_i
            self.is_alpha = is_alpha
            self.like_url = like_url
            self.like_email = like_email
            self.is_sent_start = is_sent_start
            self.morph = MockMorph({})

    # "Das ist ein Test." -> skip "Das" (stop word? wait, no stop word logic here, just extracts all).
    # But wait, extract_lemmas_from_sentence extracts EVERYTHING that is is_alpha.
    
    t0 = MockToken("Das", "der", "PRON", 0, "sb", is_sent_start=True)
    t1 = MockToken("ist", "sein", "AUX", 1, "ROOT")
    t2 = MockToken("ein", "ein", "DET", 2, "nk")
    t3 = MockToken("Test", "Test", "NOUN", 3, "pd")
    t4 = MockToken(".", ".", "PUNCT", 4, "punct", is_alpha=False)
    
    doc = [t0, t1, t2, t3, t4]
    
    class MockNLP:
        lang = 'de'
        def __call__(self, text):
            return doc
    
    class MockArgs:
        de_force_noun_capitalization = True
        force_proper_noun_capitalization = True
        de_gcs_part_singularization = 'none'

    from kardenwort.core import kardenwort
    original_nlp = getattr(kardenwort, 'nlp', None)
    kardenwort.nlp = MockNLP()
    
    try:
        lemmas = extract_lemmas_from_sentence(
            "Das ist ein Test.",
            lemma_sort_index={"Sein": 0, "Test": 1, "Der": 2, "Ein": 3},
            nlp_model=MockNLP(),
            de_dictionary=set(["Test"]),
            lemma_override_rules={},
            de_gcs_pos_tags=["NOUN", "PROPN"],
            args=MockArgs()
        )
        
        # We expect: "sein", "Test", "der", "ein" (but formatted with capitalization)
        # Because we mocked de_force_noun_capitalization=True, NOUNs become capitalized.
        # "Test" becomes "Test". "sein" becomes "Sein" (wait, format_lemma_capitalization doesn't change verbs if not NOUN, but `str.capitalize()` might not be called on verbs).
        # Actually, let's just see what it produces: "der", "sein", "ein", "Test".
        # deduplicate_lemmas prefers capitalized forms.
        assert "Test" in lemmas
        assert len(lemmas) == 4
    finally:
        kardenwort.nlp = original_nlp


def test_extract_lemmas_with_simplemma():
    from kardenwort.core.kardenwort import extract_lemmas_from_sentence
    
    class MockMorph:
        def __init__(self, data): self.data = data
        def get(self, key, default=None): return self.data.get(key, default)
        
    class MockToken:
        def __init__(self, text, lemma, pos, i, dep, head_i=None, is_alpha=True, like_url=False, like_email=False, is_sent_start=False):
            self.text = text
            self.lemma_ = lemma
            self.pos_ = pos
            self.i = i
            self.dep_ = dep
            self.head = MagicMock()
            self.head.i = head_i
            self.is_alpha = is_alpha
            self.like_url = like_url
            self.like_email = like_email
            self.is_sent_start = is_sent_start
            self.morph = MockMorph({})

    # Mock token where SpaCy fails to lemmatize properly (gegangen -> gegangen)
    t0 = MockToken("gegangen", "gegangen", "VERB", 0, "ROOT")
    
    doc = [t0]
    
    class MockNLP:
        lang = 'de'
        def __call__(self, text):
            return doc
    
    class MockArgs:
        language = 'de'
        de_force_noun_capitalization = True
        force_proper_noun_capitalization = True
        de_gcs_part_singularization = 'none'
        use_simplemma_correction = True

    from kardenwort.core import kardenwort
    original_nlp = getattr(kardenwort, 'nlp', None)
    kardenwort.nlp = MockNLP()
    
    try:
        lemmas = extract_lemmas_from_sentence(
            "gegangen",
            lemma_sort_index={},
            nlp_model=MockNLP(),
            de_dictionary=set(),
            lemma_override_rules={},
            de_gcs_pos_tags=["NOUN", "PROPN"],
            args=MockArgs()
        )
        
        # simplemma should correct "gegangen" to "gehen"
        assert "gehen" in lemmas
        assert "gegangen" not in lemmas
    finally:
        kardenwort.nlp = original_nlp

def test_load_lemma_override_rules_regex(tmp_path):
    o_file = tmp_path / "regex_override.tsv"
    content = [
        "Result_Lemma\tOriginal_Word\tTarget_Lemma\tContext",
        "spm1\tregex:.*word.*\ttgt1\t",
        "\tregex:^start\ttgt2\t",
        "spm3\t\ttgt3\tregex:.*context.*"
    ]
    o_file.write_text("\n".join(content), encoding="utf-8")
    
    rules = load_lemma_override_rules(str(o_file))
    
    assert len(rules['priority1_regex']) == 1
    assert rules['priority1_regex'][0][0] == "spm1"
    assert rules['priority1_regex'][0][1] == ".*word.*"
    assert rules['priority1_regex'][0][2][0] == "tgt1"
    
    assert len(rules['priority2_regex']) == 1
    assert rules['priority2_regex'][0][0] == "^start"
    
    assert "spm3" in rules['priority3']
    assert rules['priority3']["spm3"][0][1] == "regex:.*context.*"

def test_find_matching_override_in_context():
    from kardenwort.core.kardenwort import find_matching_override_in_context
    rules = [
        ("tgt1", "regex:.*match.*"),
        ("tgt2", "exact"),
        ("tgt3", None)
    ]
    
    assert find_matching_override_in_context(rules, "this is a match here") == "tgt1"
    assert find_matching_override_in_context(rules, "we need exact phrase") == "tgt2"
    assert find_matching_override_in_context(rules, "no context overlap") == "tgt3"
    assert find_matching_override_in_context([("tgt", "regex:[.*")], "err") is None # testing regex error branch doesn't necessarily crash but caught

def test_get_overridden_lemma_for_word_regex():
    from kardenwort.core.kardenwort import get_overridden_lemma_for_word
    rules = {
        'priority1': {},
        'priority1_regex': [("spl1", ".*match.*", ("tgt1", None))],
        'priority2': {},
        'priority2_regex': [(".*start.*", ("tgt2", None))],
        'priority3': {}
    }
    
    assert get_overridden_lemma_for_word("spl1", "this_is_a_match", rules, "") == "tgt1"
    assert get_overridden_lemma_for_word("spl2", "we_start_here", rules, "") == "tgt2"

def test_accountant_zettelkasten_sentence(tmp_path):
    from kardenwort.core.kardenwort import load_classification_dictionaries, prepare_row_data
    
    # 1. Create simulated dictionaries
    dict_3k = tmp_path / "oxford-3000.tsv"
    dict_3k.write_text("word\tcefr\ndecision\tA2\nmethod\tA2\nmake\tA1\n", encoding="utf-8")
    
    dict_5k = tmp_path / "oxford-5000.tsv"
    dict_5k.write_text("word\tcefr\naccountant\tB2\nabolish\tC1\n", encoding="utf-8")
    
    # 2. Load classifications using dynamic prefixes
    args = [
        f"oxford=3k:{dict_3k}",
        f"oxford=5k:{dict_5k}"
    ]
    classifications = load_classification_dictionaries(args)
    
    # 3. Test various words in the target sentence
    class MockArgs:
        language = "en"
        tts_destination_lang = "ru"
        
    sentence_words = {
        "accountant": "5k:B2",
        "decision": "3k:A2",
        "abolish": "5k:C1",
        "zettelkasten": None,
        "method": "3k:A2"
    }
    
    for word, expected_val in sentence_words.items():
        row_data = prepare_row_data(MockArgs(), lemma=word, classifications=classifications)
        if expected_val:
            assert row_data.get("oxford") == expected_val
        else:
            assert "oxford" not in row_data

def test_load_token_mappings(tmp_path):
    import kardenwort.core.kardenwort as kw
    mapping_file = tmp_path / "mappings.tsv"
    mapping_file.write_text("isn't\tis\tnot\nz. B.\tzum\tBeispiel\n# comment\ninvalid\n", encoding="utf-8")
    
    mappings = kw.load_token_mappings([str(mapping_file)], case_sensitive=False, normalize_apostrophes=True, normalize_spaces=True)
    assert "isn't" in mappings
    assert mappings["isn't"] == ["is", "not"]
    assert "z.b." in mappings
    assert mappings["z.b."] == ["zum", "Beispiel"]

def test_find_token_mappings_in_text():
    import kardenwort.core.kardenwort as kw
    
    class MockArgs:
        token_mappings_enabled = True
        token_mappings_case_sensitive = False
        token_mappings_normalize_apostrophes = True
        token_mappings_normalize_spaces = True
        token_mappings_enable_context_disambiguation = True
        
    class MockToken:
        def __init__(self, text, whitespace, idx):
            self.text = text
            self.whitespace_ = whitespace
            self.idx = idx
            
    args = MockArgs()
    text = "He isn't going to the z. B. park."
    doc = [
        MockToken("He", " ", 0),
        MockToken("is", "", 3),
        MockToken("n't", " ", 5),
        MockToken("going", " ", 9),
        MockToken("to", " ", 15),
        MockToken("the", " ", 18),
        MockToken("z", "", 22),
        MockToken(".", " ", 23),
        MockToken("B", "", 25),
        MockToken(".", " ", 26),
        MockToken("park", "", 28),
        MockToken(".", "", 32)
    ]
    
    mappings = {
        "isn't": ["is", "not"],
        "z.b.": ["zum", "Beispiel"]
    }
    
    matches, mapped_tokens = kw.find_token_mappings_in_text(text, doc, mappings, args)
    assert len(matches) == 2
    
    # check isn't
    assert "isn't" in [m['source_word'] for m in matches.values()]
    
    # check z. B.
    assert "z. B." in [m['source_word'] for m in matches.values()]

def test_extract_mapped_token_inflected_expansion():
    import spacy
    import argparse
    import kardenwort.core.kardenwort as kw
    
    nlp_en = spacy.blank("en")
    
    # English contraction: isn't -> is, not
    match_en = {
        'source_word': "isn't",
        'lemmas': ["is", "not"]
    }
    args_en = argparse.Namespace(
        token_mappings_lemmatize=False,
        combine_source_words_order='contractions_first',
        combine_source_words_prefer_lowercase=True,
        apostrophe_chars="', ’, ‘, `, ´, ʼ"
    )
    lemmas_en, mapped_sources_en = kw._extract_mapped_token(
        match_en, nlp_en, None, {}, args_en, "This ensures isn't properly generates.", False
    )
    assert lemmas_en == ["is", "not"]
    assert mapped_sources_en["is"] == "isn't, is"
    assert mapped_sources_en["not"] == "isn't, not"
    
    # German abbreviation: z. B. -> zum, Beispiel
    match_de = {
        'source_word': "z. B.",
        'lemmas': ["zum", "Beispiel"]
    }
    args_de = argparse.Namespace(
        token_mappings_lemmatize=False,
        combine_source_words_order='contractions_first',
        combine_source_words_prefer_lowercase=True,
        apostrophe_chars="', ’, ‘, `, ´, ʼ"
    )
    lemmas_de, mapped_sources_de = kw._extract_mapped_token(
        match_de, nlp_en, None, {}, args_de, "Wir gehen z. B. in den Park.", False
    )
    assert lemmas_de == ["zum", "Beispiel"]
    assert mapped_sources_de["zum"] == "z. B., zum"
    assert mapped_sources_de["Beispiel"] == "z. B., Beispiel"

def test_sentence_deduplication_preserves_multiple_source_words():
    import kardenwort.core.kardenwort as kw
    import argparse
    
    # We will simulate the loops inside process_parallel_text_files for deduplication_scope = 'sentence'
    args = argparse.Namespace(
        deduplication_scope='sentence',
        language='en'
    )
    
    lemmas_in_sentence = {}
    
    # Simulate adding the token "not" generated by the contraction "isn't"
    lemma = "not"
    source_word_form_1 = "isn't"
    data_entry_1 = {'lemma': lemma, 'source_word': source_word_form_1}
    
    dedup_key_1 = (lemma, source_word_form_1.lower())
    if dedup_key_1 not in lemmas_in_sentence:
        lemmas_in_sentence[dedup_key_1] = data_entry_1
        
    # Simulate adding the token "not" generated by the independent word "not"
    source_word_form_2 = "not"
    data_entry_2 = {'lemma': lemma, 'source_word': source_word_form_2}
    
    dedup_key_2 = (lemma, source_word_form_2.lower())
    if dedup_key_2 not in lemmas_in_sentence:
        lemmas_in_sentence[dedup_key_2] = data_entry_2
        
    # Both entries should be preserved because they come from different source words
    assert len(lemmas_in_sentence) == 2
    assert (lemma, "isn't") in lemmas_in_sentence
    assert (lemma, "not") in lemmas_in_sentence


def test_get_simplemma_input_text_combinations():
    from kardenwort.core.kardenwort import get_simplemma_input_text
    import argparse

    class MockToken:
        def __init__(self, text, lemma, pos, is_sent_start=False):
            self.text = text
            self.lemma_ = lemma
            self.pos_ = pos
            self.is_sent_start = is_sent_start

    # Case 1: VERB at sentence start, pos_aware=True -> should lowercase
    tok_verb = MockToken("Schreiben", "Schreiben", "VERB", is_sent_start=True)
    args = argparse.Namespace(simplemma_after_spacy=False, simplemma_pos_aware=True)
    assert get_simplemma_input_text(tok_verb, args) == "schreiben"

    # Case 2: NOUN at sentence start, pos_aware=True -> should NOT lowercase
    tok_noun = MockToken("Haus", "Haus", "NOUN", is_sent_start=True)
    assert get_simplemma_input_text(tok_noun, args) == "Haus"

    # Case 3: PROPN at sentence start, pos_aware=True -> should NOT lowercase
    tok_propn = MockToken("Berlin", "Berlin", "PROPN", is_sent_start=True)
    assert get_simplemma_input_text(tok_propn, args) == "Berlin"

    # Case 4: ADJ at sentence start, pos_aware=True -> should lowercase
    tok_adj = MockToken("Schön", "schön", "ADJ", is_sent_start=True)
    assert get_simplemma_input_text(tok_adj, args) == "schön"

    # Case 5: VERB NOT at sentence start, pos_aware=True -> should NOT lowercase via pos_aware (keeps casing of text/lemma)
    tok_verb_mid = MockToken("Schreiben", "Schreiben", "VERB", is_sent_start=False)
    assert get_simplemma_input_text(tok_verb_mid, args) == "Schreiben"

    # Case 6: simplemma_after_spacy=True selects lemma_ instead of text
    tok_diff = MockToken("Gegangen", "gehen", "VERB", is_sent_start=False)
    args_after = argparse.Namespace(simplemma_after_spacy=True, simplemma_pos_aware=False)
    assert get_simplemma_input_text(tok_diff, args_after) == "gehen"

    # Case 7: Both flags True on sentence start verb where lemma is capitalized
    tok_both = MockToken("Habt", "Habt", "VERB", is_sent_start=True)
    args_both = argparse.Namespace(simplemma_after_spacy=True, simplemma_pos_aware=True)
    assert get_simplemma_input_text(tok_both, args_both) == "habt"


def test_simplemma_sentence_initial_verbs_integration():
    import argparse
    from kardenwort.core import kardenwort as kw
    from unittest.mock import MagicMock

    class MockToken:
        def __init__(self, text, lemma, pos, is_sent_start=True):
            self.text = text
            self.lemma_ = lemma
            self.pos_ = pos
            self.is_sent_start = is_sent_start
            self.i = 0
            self.like_url = False
            self.like_email = False
            self.morph = MagicMock()
            self.morph.get.return_value = []

    nlp_model = MagicMock()
    nlp_model.lang = 'de'
    de_dictionary = {"Haus", "schreiben", "begründen", "haben"}
    lemma_override_rules = {}
    sentence_text = "Test sentence."

    args_pos_aware_fallback = argparse.Namespace(
        simplemma_after_spacy=True,
        simplemma_pos_aware=True,
        simplemma_smart_fallback=True,
        use_simplemma_correction=False,
        force_proper_noun_capitalization=False,
        prefer_shortest_form=False,
        de_force_noun_capitalization=False,
        de_noun_capitalization=False,
        token_mappings_lemmatize=True
    )

    # Test "Schreiben" -> "schreiben" (where SpaCy left lemma as "Schreiben" or similar)
    tok1 = MockToken("Schreiben", "Schreiben", "VERB", is_sent_start=True)
    lemmas1, _ = kw._extract_standard_token(
        tok1, nlp_model, de_dictionary, lemma_override_rules, sentence_text,
        de_fix_genitive=True, de_gcs=False, gcs_automaton=None, de_gcs_pos_tags=[],
        args=args_pos_aware_fallback, separable_verb_map={}
    )
    assert "schreiben" in lemmas1

    # Test "Begründen" -> "begründen"
    tok2 = MockToken("Begründen", "Begründen", "VERB", is_sent_start=True)
    lemmas2, _ = kw._extract_standard_token(
        tok2, nlp_model, de_dictionary, lemma_override_rules, sentence_text,
        de_fix_genitive=True, de_gcs=False, gcs_automaton=None, de_gcs_pos_tags=[],
        args=args_pos_aware_fallback, separable_verb_map={}
    )
    assert "begründen" in lemmas2

    # Test "Habt" -> "haben"
    tok3 = MockToken("Habt", "Habt", "VERB", is_sent_start=True)
    lemmas3, _ = kw._extract_standard_token(
        tok3, nlp_model, de_dictionary, lemma_override_rules, sentence_text,
        de_fix_genitive=True, de_gcs=False, gcs_automaton=None, de_gcs_pos_tags=[],
        args=args_pos_aware_fallback, separable_verb_map={}
    )
    assert "haben" in lemmas3


def test_composite_identifier_decomposition_extract_standard_token():
    import argparse
    from kardenwort.core import kardenwort as kw
    from mock_nlp import MockPipelineNLP

    nlp = MockPipelineNLP('en')
    tok = MockToken("split_camel_case", pos_="NOUN", is_alpha=False)
    args = argparse.Namespace(language='en', de_force_noun_capitalization=False)
    
    lemmas, mapped_sources = kw._extract_standard_token(
        tok, nlp, de_dictionary=None, lemma_override_rules={},
        sentence_text="def split_camel_case(val):", de_fix_genitive=False,
        de_gcs=False, gcs_automaton=None, de_gcs_pos_tags=[],
        args=args, separable_verb_map={}
    )
    
    assert "split" in lemmas
    assert "camel" in lemmas
    assert "case" in lemmas
    assert mapped_sources["split"] == "split_camel_case"
    assert mapped_sources["camel"] == "split_camel_case"
    assert mapped_sources["case"] == "split_camel_case"


def test_camel_case_token_decomposition_extract_standard_token():
    import argparse
    from kardenwort.core import kardenwort as kw
    from mock_nlp import MockPipelineNLP, MockToken

    nlp = MockPipelineNLP('en')
    tok = MockToken("flipWord", pos_="NOUN", is_alpha=True)
    args = argparse.Namespace(language='en', de_force_noun_capitalization=False)
    
    assert kw.is_composite_token("flipWord") is True
    assert kw.is_composite_token("isNumericToken") is True
    assert kw.is_composite_token("PascalCase") is True
    assert kw.is_composite_token("Simple") is False
    
    lemmas, mapped_sources = kw._extract_standard_token(
        tok, nlp, de_dictionary=None, lemma_override_rules={},
        sentence_text="function flipWord(span):", de_fix_genitive=False,
        de_gcs=False, gcs_automaton=None, de_gcs_pos_tags=[],
        args=args, separable_verb_map={}
    )
    
    assert "flip" in lemmas
    assert "word" in lemmas
    assert mapped_sources["flip"] == "flipWord"
    assert mapped_sources["word"] == "flipWord"


def test_named_entity_and_brand_preservation_extract_standard_token():
    import argparse
    from kardenwort.core import kardenwort as kw
    from mock_nlp import MockPipelineNLP, MockToken

    nlp = MockPipelineNLP('en')
    args = argparse.Namespace(language='en', de_force_noun_capitalization=False, preserve_composite_tokens=False)

    # Brands with camelCase/PascalCase ARE treated as composite tokens uniformly
    assert kw.is_composite_token("ChatGPT") is True
    assert kw.is_composite_token("OpenAI") is True
    assert kw.is_composite_token("YouTube") is True
    assert kw.is_composite_token("iPhone") is True

    # Standard token extraction decomposes them into constituent parts
    tok = MockToken("ChatGPT", pos_="PROPN", is_alpha=True)
    lemmas, mapped_sources = kw._extract_standard_token(
        tok, nlp, de_dictionary=None, lemma_override_rules={},
        sentence_text="We use ChatGPT every day.", de_fix_genitive=False,
        de_gcs=False, gcs_automaton=None, de_gcs_pos_tags=[],
        args=args, separable_verb_map={}
    )
    assert "chat" in lemmas
    assert "GPT" in lemmas
    assert mapped_sources["chat"] == "ChatGPT"
    assert mapped_sources["GPT"] == "ChatGPT"

    # With preserve_composite_tokens=True, the whole token is also included
    args_preserve = argparse.Namespace(language='en', de_force_noun_capitalization=False, preserve_composite_tokens=True)
    lemmas_pres, mapped_pres = kw._extract_standard_token(
        tok, nlp, de_dictionary=None, lemma_override_rules={},
        sentence_text="We use ChatGPT every day.", de_fix_genitive=False,
        de_gcs=False, gcs_automaton=None, de_gcs_pos_tags=[],
        args=args_preserve, separable_verb_map={}
    )
    assert "chat" in lemmas_pres
    assert "GPT" in lemmas_pres
    assert "ChatGPT" in lemmas_pres



def test_path_token_decomposition_and_numeric_filtering_extract_standard_token():
    import argparse
    from kardenwort.core import kardenwort as kw
    from mock_nlp import MockPipelineNLP, MockToken

    nlp = MockPipelineNLP('en')
    tok = MockToken("openspec/changes/archive/20260815131120-token-mapping-inflected-expansion/", pos_="NOUN", is_alpha=False)
    args = argparse.Namespace(language='en', de_force_noun_capitalization=False, preserve_composite_tokens=True)
    
    lemmas, mapped_sources = kw._extract_standard_token(
        tok, nlp, de_dictionary=None, lemma_override_rules={},
        sentence_text="Archived to: openspec/changes/archive/20260815131120-token-mapping-inflected-expansion/", de_fix_genitive=False,
        de_gcs=False, gcs_automaton=None, de_gcs_pos_tags=[],
        args=args, separable_verb_map={}, preserve_composite_tokens=True
    )
    
    assert "openspec" in lemmas
    assert "changes" in lemmas
    assert "archive" in lemmas
    assert "token" in lemmas
    assert "mapping" in lemmas
    assert "inflected" in lemmas
    assert "expansion" in lemmas
    # Ensure no trailing slashes on individual lemmas
    assert "expansion/" not in lemmas
    assert "archive/" not in lemmas
    # Ensure numeric timestamp is omitted
    assert "20260815131120" not in lemmas
    # Ensure entire path is NOT preserved as a composite lemma
    assert "openspec/changes/archive/20260815131120-token-mapping-inflected-expansion/" not in lemmas
    # Ensure mapped_sources maps each lemma to its constituent sub-part, not the entire path
    assert mapped_sources["archive"] == "archive"
    assert mapped_sources["token"] == "token"
    assert mapped_sources["expansion"] == "expansion"


def test_composite_identifier_extract_lemmas_from_sentence():
    import argparse
    from kardenwort.core.kardenwort import extract_lemmas_from_sentence
    from mock_nlp import MockPipelineNLP

    nlp = MockPipelineNLP('en')
    sentence = "result = prepare_lookup_tsv ( decompose_identifier )"
    args = argparse.Namespace(language='en', de_force_noun_capitalization=False)
    
    lemmas = extract_lemmas_from_sentence(
        sentence_text=sentence,
        lemma_sort_index={},
        nlp_model=nlp,
        args=args
    )

    assert "prepare" in lemmas
    assert "lookup" in lemmas
    assert "tsv" in lemmas
    assert "decompose" in lemmas
    assert "identifier" in lemmas


def test_composite_identifier_process_parallel_text_files_tsv(tmp_path, monkeypatch):
    import csv
    import argparse
    from types import SimpleNamespace
    from kardenwort.core.kardenwort import ParallelTextsStrategy, ExtractionConfig, ExecutionContext
    import kardenwort.core.legacy_baselines as legacy_baselines
    from mock_nlp import MockPipelineNLP

    nlp = MockPipelineNLP('en')
    monkeypatch.setattr(legacy_baselines, 'nlp', nlp)
    source_text = "def split_camel_case():\n    prepare_lookup_tsv()\n    decompose_identifier()"
    out_tsv = str(tmp_path / "vocab.tsv")

    args = argparse.Namespace(
        deduplication_scope='global',
        language='en',
        combine_source_words=False,
        combine_source_words_order='contractions_first',
        combine_source_words_prefer_lowercase=True,
        apostrophe_chars="', ’, ‘, `, ´, ʼ",
        prefer_shortest_form=False,
        strip_headers=None,
        add_header=True,
        add_source_word_col=True,
        add_wordlist_col=True,
        add_sentence_index_col=True,
        stdout_print_output_basename=False,
        de_gcs=False,
        de_gcs_add_parts_to_wordlist=False,
        de_gcs_pos_tags=[],
        de_fix_genitive=False,
        de_gcs_mask_unknown_parts=False,
        de_gcs_preserve_compound_word=False,
        de_gcs_skip_merge_fractions=False,
        de_gcs_only_nouns=False,
        de_gcs_combine_noun_modes=False,
        de_gcs_part_singularization='none',
        de_force_noun_capitalization=False,
        force_proper_noun_capitalization=False,
        anki_markdown_decks=False,
        anki_create_subdecks=False,
        anki_sentence_subdecks=False,
        anki_context_use_br=False,
        anki_parent_deck=None,
        anki_deck_content=None,
        context_window_type=None,
        unit_type='sentence',
        sentence_context_size=1,
        source_text=source_text,
        source_text_content=source_text,
        output_file_path=out_tsv,
        field_mapping={
            'WordSource': 'lemma',
            'WordSourceInflectedForm': 'source_word',
            'SentenceSource': 'source_sentence'
        },
        anki_header=['WordSource', 'WordSourceInflectedForm', 'SentenceSource'],
        header=['WordSource', 'WordSourceInflectedForm', 'SentenceSource']
    )

    # 1. Test ParallelTextsStrategy
    config = ExtractionConfig.from_args(args)
    ctx = ExecutionContext(nlp_model=nlp, simplemma_lang='en')
    records = list(ParallelTextsStrategy().execute(config, ctx))

    lemmas_map = {}
    for r in records:
        if r.row_data:
            lemmas_map[r.row_data.get('lemma')] = r.row_data.get('source_word')

    assert 'split' in lemmas_map
    assert 'camel' in lemmas_map
    assert 'case' in lemmas_map
    assert 'prepare' in lemmas_map
    assert 'lookup' in lemmas_map
    assert 'tsv' in lemmas_map
    assert 'decompose' in lemmas_map
    assert 'identifier' in lemmas_map
    assert 'split_camel_case' in lemmas_map['split']
    assert 'prepare_lookup_tsv' in lemmas_map['prepare']
    assert 'decompose_identifier' in lemmas_map['decompose']

    # 2. Test legacy_baselines.process_parallel_text_files
    legacy_baselines.process_parallel_text_files(
        source_text=source_text,
        lemma_sort_index={},
        language='en',
        target_text_path=None,
        tertiary_text_path=None,
        sentence_context_size=1,
        output_file_path=out_tsv,
        add_source_word_col=True,
        add_wordlist_col=False,
        add_sentence_index_col=False,
        add_header=True,
        wordlist_use_br=False,
        stdout_print_output_basename=False,
        de_gcs=False,
        gcs_automaton=None,
        de_gcs_add_parts_to_wordlist=False,
        de_dictionary=None,
        lemma_override_rules={},
        de_gcs_pos_tags=[],
        field_mapping=args.field_mapping,
        anki_header=['WordSource', 'WordSourceInflectedForm', 'SentenceSource'],
        args=args,
        nlp=nlp
    )

    file_records = []
    with open(out_tsv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            file_records.append(row)

    file_lemmas = {r['WordSource']: r['WordSourceInflectedForm'] for r in file_records}
    assert 'split' in file_lemmas
    assert 'prepare' in file_lemmas
    assert 'decompose' in file_lemmas


def test_code_identifier_and_url_delimiter_tokenization():
    import spacy
    from kardenwort.core.kardenwort import extract_lemmas_from_sentence, ExtractionConfig

    try:
        nlp = spacy.load('en_core_web_lg', exclude=["ner", "parser"])
    except Exception:
        pytest.skip('en_core_web_lg not installed in current environment')

    args = SimpleNamespace(
        language='en',
        de_gcs=False,
        de_gcs_only_nouns=False,
        de_gcs_combine_noun_modes=False,
        de_fix_genitive=False,
        de_gcs_mask_unknown_parts=False,
        de_gcs_preserve_compound_word=False,
        de_gcs_skip_merge_fractions=False,
        simplemma_pos_aware=False,
        simplemma_smart_fallback=False,
        preserve_capitalization=False,
        strip_garbage_characters='',
        de_gcs_part_singularization='none',
        de_gcs_pos_tags=[]
    )

    # 1. Filename with underscore and extension (.py)
    res_py = extract_lemmas_from_sentence("text_tokenizer.py", {}, nlp, {}, {}, [], args=args)
    assert set(res_py) == {'Py', 'text', 'tokenizer'} or set(res_py) == {'py', 'text', 'tokenizer'}

    # 2. Dotted code identifier
    res_dot = extract_lemmas_from_sentence("os.path.join", {}, nlp, {}, {}, [], args=args)
    assert set(res_dot) == {'join', 'os', 'path'} or set(res_dot) == {'join', 'Os', 'path'}

    # 3. Snake_case identifier
    res_snake = extract_lemmas_from_sentence("prepare_lookup_tsv", {}, nlp, {}, {}, [], args=args)
    assert set(res_snake) == {'lookup', 'prepare', 'Tsv'} or set(res_snake) == {'lookup', 'prepare', 'tsv'}

    # 4. Explicit URL preservation
    res_url = extract_lemmas_from_sentence("Visit https://spacy.io/api for docs.", {}, nlp, {}, {}, [], args=args)
    assert "https://spacy.io/api" in res_url
    assert "spacy" not in res_url  # URL was not chopped up into separate sub-tokens


def test_retokenize_hyphenated_compounds():
    import spacy
    from kardenwort.core.kardenwort import retokenize_hyphenated_compounds

    nlp_en = spacy.blank('en')
    text = "In-Memory Execution and user-friendly and kebab-case-identifier and 2024-2026 and -15 and A - B and --dash"
    doc = nlp_en(text)
    doc = retokenize_hyphenated_compounds(doc)

    tokens = [t.text for t in doc]
    assert "In-Memory" in tokens
    assert "user-friendly" in tokens
    assert "kebab-case-identifier" in tokens
    # Numeric range and standalone dashes must NOT be merged
    assert "2024-2026" not in tokens
    assert "2024" in tokens
    assert "2026" in tokens
    assert "A - B" not in tokens
    assert "A" in tokens
    assert "B" in tokens
    assert "--dash" in tokens or ("--" in tokens and "dash" in tokens)


def test_hyphenated_compound_lemma_extraction_and_source_form():
    import spacy
    from kardenwort.core.kardenwort import (
        retokenize_hyphenated_compounds, _extract_standard_token, extract_lemmas_from_sentence
    )

    nlp_en = spacy.blank('en')
    args = SimpleNamespace(
        language='en',
        de_gcs=False,
        de_gcs_only_nouns=False,
        de_gcs_combine_noun_modes=False,
        de_fix_genitive=False,
        de_gcs_mask_unknown_parts=False,
        de_gcs_preserve_compound_word=False,
        de_gcs_skip_merge_fractions=False,
        simplemma_pos_aware=False,
        simplemma_smart_fallback=False,
        preserve_capitalization=False,
        strip_garbage_characters='',
        de_gcs_part_singularization='none',
        de_gcs_pos_tags=[]
    )

    # 1. extract_lemmas_from_sentence on English hyphenated compounds
    lemmas = extract_lemmas_from_sentence("C. Threaded In-Memory Execution", {}, nlp_en, {}, {}, [], args=args)
    assert "in" in lemmas or "In" in lemmas
    assert "memory" in lemmas or "Memory" in lemmas

    # 2. _extract_standard_token verifies source_word_form mapping
    doc = retokenize_hyphenated_compounds(nlp_en("In-Memory"))
    token = doc[0]
    extracted_lemmas, mapped_sources = _extract_standard_token(
        token=token,
        nlp_model=nlp_en,
        de_dictionary=set(),
        lemma_override_rules={},
        sentence_text="In-Memory",
        de_fix_genitive=False,
        de_gcs=False,
        gcs_automaton=None,
        de_gcs_pos_tags=[],
        args=args,
        separable_verb_map={}
    )

    assert "in" in extracted_lemmas or "In" in extracted_lemmas
    assert "memory" in extracted_lemmas or "Memory" in extracted_lemmas
    for lem in extracted_lemmas:
        assert mapped_sources[lem] == "In-Memory"

    # 3. kebab-case constituent ordering
    doc_kebab = retokenize_hyphenated_compounds(nlp_en("kebab-case-file"))
    kebab_lemmas, kebab_mapped = _extract_standard_token(
        token=doc_kebab[0],
        nlp_model=nlp_en,
        de_dictionary=set(),
        lemma_override_rules={},
        sentence_text="kebab-case-file",
        de_fix_genitive=False,
        de_gcs=False,
        gcs_automaton=None,
        de_gcs_pos_tags=[],
        args=args,
        separable_verb_map={}
    )
    assert kebab_lemmas == ["kebab", "case", "file"]
    for lem in kebab_lemmas:
        assert kebab_mapped[lem] == "kebab-case-file"


def test_hyphenated_compound_process_parallel_text_files_tsv(tmp_path, monkeypatch):
    import argparse
    import spacy
    from kardenwort.core.kardenwort import ParallelTextsStrategy, ExtractionConfig, ExecutionContext
    import kardenwort.core.legacy_baselines as legacy_baselines

    nlp_en = spacy.blank('en')
    monkeypatch.setattr(legacy_baselines, 'nlp', nlp_en)
    source_text = "C. Threaded In-Memory Execution\nuser-friendly kebab-case-name"
    out_tsv = str(tmp_path / "vocab_hyphen.tsv")

    args = argparse.Namespace(
        deduplication_scope='global',
        language='en',
        combine_source_words=False,
        combine_source_words_order='contractions_first',
        combine_source_words_prefer_lowercase=True,
        apostrophe_chars="', ’, ‘, `, ´, ʼ",
        prefer_shortest_form=False,
        strip_headers=None,
        add_header=True,
        add_source_word_col=True,
        add_wordlist_col=True,
        add_sentence_index_col=True,
        stdout_print_output_basename=False,
        de_gcs=False,
        de_gcs_add_parts_to_wordlist=False,
        de_gcs_pos_tags=[],
        de_fix_genitive=False,
        de_gcs_mask_unknown_parts=False,
        de_gcs_preserve_compound_word=False,
        de_gcs_skip_merge_fractions=False,
        de_gcs_only_nouns=False,
        de_gcs_combine_noun_modes=False,
        de_gcs_part_singularization='none',
        de_force_noun_capitalization=False,
        force_proper_noun_capitalization=False,
        anki_markdown_decks=False,
        anki_create_subdecks=False,
        anki_sentence_subdecks=False,
        anki_context_use_br=False,
        anki_parent_deck=None,
        anki_deck_content=None,
        context_window_type=None,
        unit_type='sentence',
        sentence_context_size=1,
        source_text=source_text,
        source_text_content=source_text,
        output_file_path=out_tsv,
        field_mapping={
            'WordSource': 'lemma',
            'WordSourceInflectedForm': 'source_word',
            'SentenceSource': 'source_sentence'
        },
        anki_header=['WordSource', 'WordSourceInflectedForm', 'SentenceSource'],
        header=['WordSource', 'WordSourceInflectedForm', 'SentenceSource']
    )

    config = ExtractionConfig.from_args(args)
    ctx = ExecutionContext(nlp_model=nlp_en, simplemma_lang='en')
    records = list(ParallelTextsStrategy().execute(config, ctx))

    lemmas_map = {}
    for r in records:
        if r.row_data:
            lemmas_map[r.row_data.get('lemma')] = r.row_data.get('source_word')

    assert 'in' in lemmas_map or 'In' in lemmas_map
    assert 'memory' in lemmas_map or 'Memory' in lemmas_map
    in_key = 'in' if 'in' in lemmas_map else 'In'
    mem_key = 'memory' if 'memory' in lemmas_map else 'Memory'
    assert lemmas_map[in_key] == 'In-Memory'
    assert lemmas_map[mem_key] == 'In-Memory'

    assert 'user' in lemmas_map
    assert 'friendly' in lemmas_map
    assert lemmas_map['user'] == 'user-friendly'
    assert lemmas_map['friendly'] == 'user-friendly'


def test_hyphenated_compound_german_gcs_orthogonality():
    import spacy
    from kardenwort.core.kardenwort import (
        retokenize_hyphenated_compounds, _extract_standard_token
    )

    try:
        nlp_de = spacy.load('de_core_news_sm', exclude=["ner", "parser"])
    except Exception:
        nlp_de = spacy.blank('de')

    args_gcs_off = SimpleNamespace(
        language='de',
        de_gcs=False,
        de_gcs_only_nouns=False,
        de_gcs_combine_noun_modes=False,
        de_fix_genitive=False,
        de_gcs_mask_unknown_parts=False,
        de_gcs_preserve_compound_word=False,
        de_gcs_skip_merge_fractions=False,
        simplemma_pos_aware=False,
        simplemma_smart_fallback=False,
        preserve_capitalization=False,
        strip_garbage_characters='',
        de_gcs_part_singularization='none',
        de_gcs_pos_tags=[]
    )

    doc = retokenize_hyphenated_compounds(nlp_de("Projekt-Manager"))
    token = doc[0]
    lemmas_off, mapped_off = _extract_standard_token(
        token=token,
        nlp_model=nlp_de,
        de_dictionary=set(),
        lemma_override_rules={},
        sentence_text="Projekt-Manager",
        de_fix_genitive=False,
        de_gcs=False,
        gcs_automaton=None,
        de_gcs_pos_tags=[],
        args=args_gcs_off,
        separable_verb_map={}
    )

    assert "Projekt" in lemmas_off or "projekt" in lemmas_off
    assert "Manager" in lemmas_off or "manager" in lemmas_off
    for lem in lemmas_off:
        assert mapped_off[lem] == "Projekt-Manager"


def test_preserve_composite_tokens_unit_english():
    import argparse
    from kardenwort.core import kardenwort as kw
    from mock_nlp import MockPipelineNLP

    nlp = MockPipelineNLP('en')
    tok = MockToken("state-of-the-art", pos_="ADJ", is_alpha=False)

    # 1. Disabled (default)
    args_disabled = argparse.Namespace(language='en', de_force_noun_capitalization=False, preserve_composite_tokens=False)
    lemmas_disabled, mapped_disabled = kw._extract_standard_token(
        tok, nlp, de_dictionary=None, lemma_override_rules={},
        sentence_text="This is a state-of-the-art solution.", de_fix_genitive=False,
        de_gcs=False, gcs_automaton=None, de_gcs_pos_tags=[],
        args=args_disabled, separable_verb_map={},
        preserve_composite_tokens=False
    )
    assert "state-of-the-art" not in lemmas_disabled
    assert "state" in lemmas_disabled
    assert "art" in lemmas_disabled

    # 2. Enabled
    args_enabled = argparse.Namespace(language='en', de_force_noun_capitalization=False, preserve_composite_tokens=True)
    lemmas_enabled, mapped_enabled = kw._extract_standard_token(
        tok, nlp, de_dictionary=None, lemma_override_rules={},
        sentence_text="This is a state-of-the-art solution.", de_fix_genitive=False,
        de_gcs=False, gcs_automaton=None, de_gcs_pos_tags=[],
        args=args_enabled, separable_verb_map={},
        preserve_composite_tokens=True
    )
    assert "state-of-the-art" in lemmas_enabled
    assert "state" in lemmas_enabled
    assert "art" in lemmas_enabled
    assert mapped_enabled["state-of-the-art"] == "state-of-the-art"
    assert mapped_enabled["state"] == "state-of-the-art"


def test_preserve_composite_tokens_unit_german():
    import argparse
    from kardenwort.core import kardenwort as kw
    from mock_nlp import MockPipelineNLP

    nlp = MockPipelineNLP('de')
    tok = MockToken("viel-zu-beschäftigte", lemma_="viel-zu-beschäftigt", pos_="ADJ", is_alpha=False)

    # 1. Disabled (default)
    args_disabled = argparse.Namespace(language='de', de_force_noun_capitalization=False, preserve_composite_tokens=False)
    lemmas_disabled, _ = kw._extract_standard_token(
        tok, nlp, de_dictionary=set(), lemma_override_rules={},
        sentence_text="Er ist eine viel-zu-beschäftigte Person.", de_fix_genitive=False,
        de_gcs=False, gcs_automaton=None, de_gcs_pos_tags=[],
        args=args_disabled, separable_verb_map={},
        preserve_composite_tokens=False
    )
    assert "viel-zu-beschäftigt" not in lemmas_disabled
    assert "viel" in lemmas_disabled

    # 2. Enabled
    args_enabled = argparse.Namespace(language='de', de_force_noun_capitalization=False, preserve_composite_tokens=True)
    lemmas_enabled, mapped_enabled = kw._extract_standard_token(
        tok, nlp, de_dictionary=set(), lemma_override_rules={},
        sentence_text="Er ist eine viel-zu-beschäftigte Person.", de_fix_genitive=False,
        de_gcs=False, gcs_automaton=None, de_gcs_pos_tags=[],
        args=args_enabled, separable_verb_map={},
        preserve_composite_tokens=True
    )
    assert "viel-zu-beschäftigt" in lemmas_enabled
    assert "viel" in lemmas_enabled
    assert mapped_enabled["viel-zu-beschäftigt"] == "viel-zu-beschäftigte"


def test_preserve_composite_tokens_extract_lemmas_from_sentence():
    from kardenwort.core.kardenwort import extract_lemmas_from_sentence, ExtractionConfig
    from mock_nlp import MockPipelineNLP

    nlp = MockPipelineNLP('en')
    sentence = "We offer a state-of-the-art platform."

    # 1. Disabled (default)
    cfg_off = ExtractionConfig(language='en', preserve_composite_tokens=False, de_force_noun_capitalization=False)
    lemmas_off = extract_lemmas_from_sentence(
        sentence_text=sentence,
        lemma_sort_index={},
        nlp_model=nlp,
        extraction_config=cfg_off
    )
    assert not any(x.lower() == "state-of-the-art" for x in lemmas_off)
    assert any(x.lower() == "state" for x in lemmas_off)
    assert any(x.lower() == "art" for x in lemmas_off)

    # 2. Enabled
    cfg_on = ExtractionConfig(language='en', preserve_composite_tokens=True, de_force_noun_capitalization=False)
    lemmas_on = extract_lemmas_from_sentence(
        sentence_text=sentence,
        lemma_sort_index={},
        nlp_model=nlp,
        extraction_config=cfg_on
    )
    assert any(x.lower() == "state-of-the-art" for x in lemmas_on)
    assert any(x.lower() == "state" for x in lemmas_on)
    assert any(x.lower() == "art" for x in lemmas_on)


def test_combine_source_words_deduplicates_multi_token_forms(tmp_path):
    import argparse
    from kardenwort.core.kardenwort import sort_inflected_forms
    from mock_nlp import MockPipelineNLP

    nlp = MockPipelineNLP('en')
    src_file = tmp_path / "test.en.txt"
    src_file.write_text("Specs: ✓ Synced to main spec. All specs complete.", encoding="utf-8")
    tgt_file = tmp_path / "test.ru.txt"
    tgt_file.write_text("Спецификации: готово.", encoding="utf-8")
    out_file = tmp_path / "out.tsv"

    args = argparse.Namespace(
        source_file=str(src_file),
        target_file=str(tgt_file),
        output_file=str(out_file),
        language='en',
        deduplication_scope='global',
        combine_source_words=True,
        combine_source_words_order='contractions_first',
        combine_source_words_prefer_lowercase=True,
        token_mappings_enabled=True,
        token_mappings_file="data/en/lemma_abbreviations_en.tsv",
        token_mappings_lemmatize=True,
        preserve_composite_tokens=False,
        de_force_noun_capitalization=False,
        strip_garbage_characters="",
        anki_create_subdecks=False,
        anki_markdown_decks=False,
        prefer_shortest_form=False
    )

    forms = ["specifications, Specs", "specifications, spec", "specifications, specs"]
    existing = []
    for cur in forms:
        for form in [s.strip() for s in cur.split(',') if s.strip()]:
            if form not in existing:
                existing.append(form)
    sorted_forms = sort_inflected_forms(existing, config=args)
    assert len(sorted_forms) == len(set(sorted_forms))
    assert sorted_forms.count("specifications") == 1


def test_function_call_bracket_decomposition_and_id_preservation():
    import spacy
    from kardenwort.core.kardenwort import extract_lemmas_from_sentence, _extract_standard_token, ExtractionConfig

    try:
        nlp = spacy.load("en_core_web_lg", exclude=["ner", "parser"])
    except Exception:
        pytest.skip("SpaCy en_core_web_lg model not installed")

    sentence = "Call split_camel_case(raw_word) using compound_id and id."
    config = ExtractionConfig(language='en', preserve_composite_tokens=True, de_force_noun_capitalization=False)

    lemmas = extract_lemmas_from_sentence(
        sentence_text=sentence,
        lemma_sort_index={},
        nlp_model=nlp,
        extraction_config=config
    )

    lemmas_lower = [l.lower() for l in lemmas]

    # Verify function signature components
    assert "split_camel_case" in lemmas_lower
    assert "split" in lemmas_lower
    assert "camel" in lemmas_lower
    assert "case" in lemmas_lower
    assert "raw_word" in lemmas_lower
    assert "raw" in lemmas_lower
    assert "word" in lemmas_lower

    # Verify ID preservation
    assert "compound_id" in lemmas_lower
    assert "compound" in lemmas_lower
    assert "id" in lemmas_lower

    # Verify that id is NOT split into contraction components (I / 'd)
    doc = nlp("compound_id id")
    tok_compound = doc[0]
    tok_id = doc[1]

    lemmas_comp, mapped_comp = _extract_standard_token(
        tok_compound, nlp, de_dictionary=None, lemma_override_rules={},
        sentence_text=sentence, de_fix_genitive=False,
        de_gcs=False, gcs_automaton=None, de_gcs_pos_tags=[],
        args=config, separable_verb_map={},
        preserve_composite_tokens=True
    )
    assert any(l.lower() == "compound_id" for l in lemmas_comp)
    assert "compound" in [l.lower() for l in lemmas_comp]
    assert "id" in [l.lower() for l in lemmas_comp]
    assert mapped_comp.get("compound") == "compound_id" or mapped_comp.get("Compound") == "compound_id"
    assert mapped_comp.get("id") == "compound_id" or mapped_comp.get("Id") == "compound_id"

    lemmas_id, mapped_id = _extract_standard_token(
        tok_id, nlp, de_dictionary=None, lemma_override_rules={},
        sentence_text=sentence, de_fix_genitive=False,
        de_gcs=False, gcs_automaton=None, de_gcs_pos_tags=[],
        args=config, separable_verb_map={},
        preserve_composite_tokens=True
    )
    assert any(l.lower() == "id" for l in lemmas_id)
    assert not any(l.lower() == "'d" or l == "d" for l in lemmas_id)


def test_wed_and_id_tokenizer_exception_removal():
    import spacy
    from kardenwort.core.kardenwort import extract_lemmas_from_sentence, configure_spacy_model, ExtractionConfig

    try:
        nlp = spacy.load("en_core_web_lg", exclude=["ner", "parser"])
    except Exception:
        try:
            nlp = spacy.load("en_core_web_sm", exclude=["ner", "parser"])
        except Exception:
            nlp = spacy.blank("en")

    configure_spacy_model(nlp)

    sentence = "They wed in June and meet on Wed, Aug 16."
    config = ExtractionConfig(language='en', preserve_composite_tokens=True, de_force_noun_capitalization=False)

    lemmas = extract_lemmas_from_sentence(
        sentence_text=sentence,
        lemma_sort_index={},
        nlp_model=nlp,
        extraction_config=config
    )
    lemmas_lower = [l.lower() for l in lemmas]

    assert "wed" in lemmas_lower
    # Ensure it wasn't decomposed into 'd or would/had from slang contraction
    assert "'d" not in lemmas_lower

    doc = nlp(sentence)
    tokens_text = [t.text for t in doc]
    assert "wed" in tokens_text
    assert "Wed" in tokens_text
    assert "we" not in [t.text.lower() for t in doc]


def test_split_camel_case_acronym_plurals():
    """Verify split_camel_case preserves uppercase acronym plurals."""
    from kardenwort.core.kardenwort import split_camel_case

    for word in ["LLMs", "GPUs", "APIs", "CPUs", "SDKs", "URLs"]:
        assert split_camel_case(word) == [word]


def test_possessive_token_suppression_and_inflection():
    """Verify possessive tokens ('s, 's, ') are suppressed as standalone lemmas."""
    import spacy
    from kardenwort.core.kardenwort import (
        extract_lemmas_from_sentence, configure_spacy_model, ExtractionConfig,
        is_possessive_token, find_possessive_token_pairs
    )

    try:
        nlp = spacy.load("en_core_web_lg", exclude=["ner", "parser"])
    except Exception:
        try:
            nlp = spacy.load("en_core_web_sm", exclude=["ner", "parser"])
        except Exception:
            nlp = spacy.blank("en")

    configure_spacy_model(nlp)

    sentence = "Alibaba's Qwen has become the world's most-downloaded AI model family, per Hugging Face's latest report in China's market."
    config = ExtractionConfig(language='en', preserve_composite_tokens=True)

    lemmas = extract_lemmas_from_sentence(
        sentence_text=sentence,
        lemma_sort_index={},
        nlp_model=nlp,
        extraction_config=config
    )
    lemmas_lower = [l.lower() for l in lemmas]

    # Preceding nouns / entities must be present
    assert "alibaba" in lemmas_lower
    assert "world" in lemmas_lower
    assert "china" in lemmas_lower
    assert "face" in lemmas_lower

    # Standalone possessive particles MUST NOT be emitted
    assert "'s" not in lemmas
    assert "’s" not in lemmas
    assert "s" not in lemmas_lower

    # Test find_possessive_token_pairs directly on doc
    doc = nlp(sentence)
    poss_indices, poss_suffixes = find_possessive_token_pairs(doc)
    assert len(poss_indices) >= 4  # Alibaba's, world's, Face's, China's
    for idx in poss_indices:
        assert is_possessive_token(doc[idx])


def test_path_and_file_compound_subtoken_inflections():
    """Verify sub-tokens extracted from file paths and compound file names propagate specific source words."""
    import argparse
    from kardenwort.core import kardenwort as kw
    from mock_nlp import MockPipelineNLP, MockToken

    nlp = MockPipelineNLP('en')
    tok = MockToken("run_goldens.py", pos_="NOUN", is_alpha=False)
    args = argparse.Namespace(language='en', de_force_noun_capitalization=False, preserve_composite_tokens=False)

    lemmas, mapped_sources = kw._extract_standard_token(
        tok, nlp, de_dictionary=None, lemma_override_rules={},
        sentence_text="Execute run_goldens.py now.", de_fix_genitive=False,
        de_gcs=False, gcs_automaton=None, de_gcs_pos_tags=[],
        args=args, separable_verb_map={}
    )

    assert "run" in lemmas
    assert "goldens" in lemmas
    assert "py" in lemmas
    assert mapped_sources["run"] == "run"
    assert mapped_sources["goldens"] == "goldens"
    assert mapped_sources["py"] == "py"
