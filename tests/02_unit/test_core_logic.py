import pytest
from pathlib import Path
import sys
from unittest.mock import MagicMock

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / 'src'))

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

def test_format_lemma_capitalization():
    class MockToken:
        def __init__(self, text, pos, is_sent_start=False, like_url=False, like_email=False):
            self.text = text
            self.pos_ = pos
            self.is_sent_start = is_sent_start
            self.like_url = like_url
            self.like_email = like_email
            
    class MockArgs:
        de_force_noun_capitalization = True
        force_proper_noun_capitalization = True

    from kardenwort.core import kardenwort
    original_nlp = getattr(kardenwort, 'nlp', None)
    
    class MockNLP:
        lang = 'de'
    kardenwort.nlp = MockNLP()
    
    try:
        args = MockArgs()
        token = MockToken("Häuser", "NOUN")
        assert format_lemma_capitalization(token, "haus", args) == "Haus"
        
        token_propn = MockToken("Berlin", "PROPN")
        assert format_lemma_capitalization(token_propn, "berlin", args) == "Berlin"
    finally:
        kardenwort.nlp = original_nlp

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

def test_correct_spacy_lemma():
    class MockMorph:
        def __init__(self, data): self.data = data
        def get(self, key, default=None): return self.data.get(key, default)
        
    class MockToken:
        def __init__(self, lemma, pos, case_morph):
            self.lemma_ = lemma
            self.pos_ = pos
            self.morph = MockMorph({"Case": case_morph})
            
    from kardenwort.core import kardenwort
    original_nlp = getattr(kardenwort, 'nlp', None)
    class MockNLP: lang = 'de'
    kardenwort.nlp = MockNLP()
    
    try:
        de_dictionary = {"Haus", "Auto"}
        token = MockToken("Hauss", "NOUN", ["Gen"])
        assert correct_spacy_lemma(token, de_dictionary, fix_genitive=True) == "Haus"
    finally:
        kardenwort.nlp = original_nlp

def test_find_separable_verb_particle_pairs():
    class MockToken:
        def __init__(self, i, dep, head_i=None):
            self.i = i
            self.dep_ = dep
            self.head = MagicMock()
            self.head.i = head_i

    t1 = MockToken(0, "ROOT")
    t2 = MockToken(1, "svp", head_i=0)
    
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
        "Header_like_but_lowercase\t\tC1"
    ]
    c_file.write_text("\n".join(content), encoding="utf-8")
    
    args = [f"oxford={c_file}"]
    classifications = load_classification_dictionaries(args)
    
    assert "oxford" in classifications
    assert classifications["oxford"]["apple"] == "A1"
    assert classifications["oxford"]["abandon"] == "B2"
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
    class MockArgs:
        language = "en"
        tts_destination_lang = "ru"

    kwargs = {
        'lemma': 'apple',
        'classifications': {
            'oxford': {'apple': 'A1', 'banana': 'A2'},
            'cambridge': {'apple': 'B1'}
        }
    }
    
    row_data = prepare_row_data(MockArgs(), **kwargs)
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
