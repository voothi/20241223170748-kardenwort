import pytest
from pathlib import Path
import sys
from unittest.mock import MagicMock

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))

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
    get_field_index_map
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
