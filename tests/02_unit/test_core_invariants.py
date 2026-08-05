import itertools
import pytest
from typing import List, Dict, Any, Tuple
from pathlib import Path
import sys

# Add src and helpers to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / 'src'))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'helpers'))
from mock_nlp import MockToken as _MockToken

from kardenwort.core.kardenwort import (
    deduplicate_lemmas,
    sort_inflected_forms,
    format_lemma_capitalization,
    get_anki_csv_header,
    get_field_index_map,
    prepare_row_data,
    apply_field_mapping,
)
import kardenwort.core.kardenwort as kardenwort_mod

# ==============================================================================
# 1. Combinatorial Matrix Generators
# ==============================================================================

EXTRACTION_FLAGS = [
    "prefer_lowercase",
    "combine_source_words",
    "prefer_shortest_form",
    "token_mappings_enabled",
]

GCS_FLAGS = [
    "de_gcs_only_nouns",
    "de_gcs_combine_noun_modes",
    "de_gcs_mask_unknown_parts",
    "de_gcs_preserve_compound_word",
    "de_gcs_skip_merge_fractions",
]

CAPITALIZATION_FLAGS = [
    "de_force_noun_capitalization",
    "force_proper_noun_capitalization",
    "de_fix_genitive",
]

TABULAR_FLAGS = [
    "add_wordlist_col",
    "wordlist_use_br",
    "anki_markdown_decks",
    "anki_sentence_subdecks",
]


def generate_extraction_matrix() -> List[Dict[str, Any]]:
    """
    Generates a deterministic 16-state parameter matrix across extraction flags.
    Returns 2^4 = 16 permutations.
    """
    matrix = list(itertools.product([True, False], repeat=len(EXTRACTION_FLAGS)))
    return [dict(zip(EXTRACTION_FLAGS, values)) for values in matrix]


def generate_gcs_matrix() -> List[Dict[str, Any]]:
    """
    Generates a deterministic 32-state parameter matrix across GCS flags.
    Returns 2^5 = 32 permutations.
    """
    matrix = list(itertools.product([True, False], repeat=len(GCS_FLAGS)))
    return [dict(zip(GCS_FLAGS, values)) for values in matrix]


def generate_capitalization_matrix() -> List[Dict[str, Any]]:
    """
    Generates a deterministic 8-state parameter matrix across capitalization flags.
    Returns 2^3 = 8 permutations.
    """
    matrix = list(itertools.product([True, False], repeat=len(CAPITALIZATION_FLAGS)))
    return [dict(zip(CAPITALIZATION_FLAGS, values)) for values in matrix]


def generate_tabular_matrix() -> List[Dict[str, Any]]:
    """
    Generates a deterministic 16-state parameter matrix across tabular mapping flags.
    Returns 2^4 = 16 permutations.
    """
    matrix = list(itertools.product([True, False], repeat=len(TABULAR_FLAGS)))
    return [dict(zip(TABULAR_FLAGS, values)) for values in matrix]


# ==============================================================================
# 2. Assertion Tests for Generator Dimensions and Completeness
# ==============================================================================

def test_extraction_matrix_dimensions_and_completeness():
    matrix = generate_extraction_matrix()
    assert len(matrix) == 16, "Extraction matrix must have exactly 16 permutations (2^4)."
    # Verify completeness and no duplicate configurations
    unique_tuples = {tuple(sorted(d.items())) for d in matrix}
    assert len(unique_tuples) == 16, "All configurations in extraction matrix must be unique."
    for item in matrix:
        assert set(item.keys()) == set(EXTRACTION_FLAGS)


def test_gcs_matrix_dimensions_and_completeness():
    matrix = generate_gcs_matrix()
    assert len(matrix) == 32, "GCS matrix must have exactly 32 permutations (2^5)."
    unique_tuples = {tuple(sorted(d.items())) for d in matrix}
    assert len(unique_tuples) == 32, "All configurations in GCS matrix must be unique."
    for item in matrix:
        assert set(item.keys()) == set(GCS_FLAGS)


def test_capitalization_matrix_dimensions_and_completeness():
    matrix = generate_capitalization_matrix()
    assert len(matrix) == 8, "Capitalization matrix must have exactly 8 permutations (2^3)."
    unique_tuples = {tuple(sorted(d.items())) for d in matrix}
    assert len(unique_tuples) == 8, "All configurations in capitalization matrix must be unique."
    for item in matrix:
        assert set(item.keys()) == set(CAPITALIZATION_FLAGS)


def test_tabular_matrix_dimensions_and_completeness():
    matrix = generate_tabular_matrix()
    assert len(matrix) == 16, "Tabular matrix must have exactly 16 permutations (2^4)."
    unique_tuples = {tuple(sorted(d.items())) for d in matrix}
    assert len(unique_tuples) == 16, "All configurations in tabular matrix must be unique."
    for item in matrix:
        assert set(item.keys()) == set(TABULAR_FLAGS)


def test_generator_dimensions_and_completeness_unified():
    """
    Unified scenario test verifying all four generators for mathematical completeness
    without randomness or external dependencies.
    """
    generators = [
        (generate_extraction_matrix, 16, EXTRACTION_FLAGS),
        (generate_gcs_matrix, 32, GCS_FLAGS),
        (generate_capitalization_matrix, 8, CAPITALIZATION_FLAGS),
        (generate_tabular_matrix, 16, TABULAR_FLAGS),
    ]
    for gen_fn, expected_count, expected_keys in generators:
        matrix = gen_fn()
        assert len(matrix) == expected_count
        assert len({tuple(sorted(d.items())) for d in matrix}) == expected_count
        for item in matrix:
            assert set(item.keys()) == set(expected_keys)


# ==============================================================================
# 3. Linguistic Helper Invariant Verification
# ==============================================================================

@pytest.mark.parametrize("config", generate_extraction_matrix())
def test_deduplicate_lemmas_invariants(config):
    """
    Verifies order invariance across all candidate token states across all 16 extraction
    parameter states without throwing exceptions or corrupting token text.
    """
    # Basic deduplication preserving deterministic first-occurrence order of lowercased variants
    assert deduplicate_lemmas(["Haus", "haus", "Auto"]) == ["Haus", "Auto"]
    # Case preservation preferring capitalized variant when present, while preserving first occurrence order
    assert deduplicate_lemmas(["auto", "Haus", "Auto", "haus"]) == ["Auto", "Haus"]
    assert deduplicate_lemmas(["Laufen", "laufen"]) == ["Laufen"]
    assert deduplicate_lemmas([]) == []
    assert deduplicate_lemmas(["test"]) == ["test"]


@pytest.mark.parametrize("config", generate_extraction_matrix())
def test_sort_inflected_forms_invariants(config):
    """
    Verifies contraction sorting and lowercase preference behavior across extraction states.
    """
    prefer_lower = config["prefer_lowercase"]
    apostrophes = ["'"]
    
    # Check lowercase preference behavior on mixed-case variants
    forms = ["Ist", "ist", "sind"]
    sorted_forms = sort_inflected_forms(forms, apostrophe_chars=apostrophes, order='contractions_first', prefer_lowercase=prefer_lower)
    if prefer_lower:
        # Lowercase override folds "Ist" and "ist" together into "ist"
        assert len(sorted_forms) == 2
        assert "ist" in sorted_forms
        assert "sind" in sorted_forms
    else:
        # Both case variants remain distinct when prefer_lowercase=False
        assert len(sorted_forms) == 3
        assert "Ist" in sorted_forms and "ist" in sorted_forms

    # Check contraction sorting behavior
    contraction_forms = ["did", "don't", "do not"]
    sorted_contractions = sort_inflected_forms(contraction_forms, apostrophe_chars=apostrophes, order='contractions_first', prefer_lowercase=prefer_lower)
    # Contractions and compound forms containing apostrophes or spaces are complex and must sort before simple words
    assert sorted_contractions[0] in ["don't", "do not"]
    assert sorted_contractions[1] in ["don't", "do not"]
    assert sorted_contractions[2] == "did"


class _MockArgs:
    def __init__(self, config):
        for k, v in config.items():
            setattr(self, k, v)


@pytest.mark.parametrize("config", generate_capitalization_matrix())
def test_format_lemma_capitalization_invariants(config):
    """
    Verifies formatting and capitalization invariance using mocked spaCy tokens and argument namespaces.
    """
    original_nlp = getattr(kardenwort_mod, 'nlp', None)
    
    class _MockNLP:
        lang = 'de'
        
    kardenwort_mod.nlp = _MockNLP()
    
    try:
        args = _MockArgs(config)
        
        # URL / email token always reduces to lowercase regardless of capitalization config
        url_token = _MockToken("HTTPS://EXAMPLE.COM", "NOUN", like_url=True)
        assert format_lemma_capitalization(url_token, "HTTPS://EXAMPLE.COM", args) == "https://example.com"

        # German Noun capitalization rule when nlp.lang == 'de'
        noun_token = _MockToken("häuser", "NOUN")
        res_noun = format_lemma_capitalization(noun_token, "haus", args)
        if config["de_force_noun_capitalization"]:
            assert res_noun == "Haus"
        else:
            assert res_noun == "haus"

        # Proper Noun capitalization rule
        propn_token = _MockToken("berlin", "PROPN")
        res_propn = format_lemma_capitalization(propn_token, "berlin", args)
        if config["force_proper_noun_capitalization"] or config["de_force_noun_capitalization"]:
            assert res_propn == "Berlin"
        else:
            assert res_propn == "berlin"
            
        # Non-noun at sentence start
        verb_token = _MockToken("laufen", "VERB", is_sent_start=True)
        assert format_lemma_capitalization(verb_token, "laufen", args) == "laufen"
        
    finally:
        kardenwort_mod.nlp = original_nlp


# ==============================================================================
# 4. Tabular & Anki Field Mapping Invariant Verification
# ==============================================================================

@pytest.mark.parametrize("config", generate_tabular_matrix())
def test_tabular_and_anki_field_mapping_invariants(config):
    """
    Verifies that tabular formatting and field index mapping remain entirely invariant
    across tabular configuration variations, locking down baseline TSV header and field mapping behavior.
    """
    # 1. Verify get_anki_csv_header invariance
    header = get_anki_csv_header()
    assert isinstance(header, list) and len(header) > 0
    
    # 2. Verify get_field_index_map invariance and exact 1-to-1 mapping with header
    index_map = get_field_index_map()
    assert len(index_map) == len(header)
    for i, col_name in enumerate(header):
        assert index_map[col_name] == i
        
    # 3. Test prepare_row_data across configuration permutations with realistic data
    class _MockArgs:
        language = "de"
        tts_destination_lang = "ru"
        
    args = _MockArgs()
    
    # Test wordlist column variations according to tabular flags
    wordlist_val = "w1<br>w2" if config["wordlist_use_br"] else "w1\\nw2"
    deck_val = "Deck::001-sentence" if (config["anki_markdown_decks"] and config["anki_sentence_subdecks"]) else "Deck"
    
    row_data = prepare_row_data(
        args,
        lemma="Haus",
        source_word="Häuser",
        source_sentence="Schöne Häuser.",
        deck_name=deck_val,
        wordlist=wordlist_val,
        subtitle_start_time="00:01:23.456",
        classifications={"oxford": {"haus": "B1"}},
        classification_case_sensitive=False
    )
    
    assert row_data["lemma"] == "Haus"
    assert row_data["source_word"] == "Häuser"
    assert row_data["source_sentence"] == "Schöne Häuser."
    assert row_data["deck_name"] == deck_val
    assert row_data["wordlist"] == wordlist_val
    assert row_data["subtitle_start_time"] == "00:01:23.456"
    assert row_data["tts_source_de"] == "1"
    assert row_data["tts_dest_ru"] == "1"
    assert row_data.get("oxford") == "B1"

    # 4. Verify apply_field_mapping produces deterministic TSV row output
    empty_row = [""] * len(header)
    csv_row = list(empty_row)
    
    # Simulate both word and sentence field mappings from anki-mapping.ini baseline
    word_mapping = {
        "WordSource": "lemma",
        "Quotation": "source_word",
        "SentenceSource": "source_sentence",
        "SentenceSourceWordlist": "wordlist",
        "Deck": "deck_name",
        "Source-de-DE": "tts_source_de",
        "Destination-ru-RU": "tts_dest_ru",
        "Note": "subtitle_start_time",
    }
    
    apply_field_mapping(csv_row, row_data, word_mapping, index_map)
    
    assert csv_row[index_map["WordSource"]] == "Haus"
    assert csv_row[index_map["Quotation"]] == "Häuser"
    assert csv_row[index_map["SentenceSource"]] == "Schöne Häuser."
    assert csv_row[index_map["SentenceSourceWordlist"]] == wordlist_val
    assert csv_row[index_map["Deck"]] == deck_val
    assert csv_row[index_map["Source-de-DE"]] == "1"
    assert csv_row[index_map["Destination-ru-RU"]] == "1"
    assert csv_row[index_map["Note"]] == "00:01:23.456"

