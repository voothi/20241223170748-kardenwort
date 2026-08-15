import pytest
from types import SimpleNamespace
from kardenwort.core.kardenwort import apply_field_mapping, get_anki_csv_header, get_field_index_map, prepare_row_data

@pytest.fixture
def field_setup():
    header = get_anki_csv_header()
    field_index_map = get_field_index_map()
    empty_row = [""] * len(header)
    return header, field_index_map, empty_row

@pytest.mark.parametrize("row_data, field_mapping, expected_values", [
    # Basic mapping
    ({"source_word": "test_word"}, {"WordSourceAI": "source_word"}, {"WordSourceAI": "test_word"}),
    # Multiple mapping
    (
        {"source_word": "inflected", "lemma": "base", "source_sentence": "Sentence."},
        {"WordSourceAI": "source_word", "WordSourceInflectedFormAI": "lemma", "SentenceSource": "source_sentence"},
        {"WordSourceAI": "inflected", "WordSourceInflectedFormAI": "base", "SentenceSource": "Sentence."}
    ),
    # Unknown data source
    ({"source_word": "test_word"}, {"WordSourceAI": "missing_source"}, {"WordSourceAI": ""}),
    # Case preservation
    ({"SourceWord": "MixedCase"}, {"WordSourceAI": "SourceWord"}, {"WordSourceAI": "MixedCase"}),
    # Duplicate mapping (last one wins)
    ({"src1": "VAL1", "src2": "VAL2"}, {"WordSourceAI": "src1", "WordSourceAI": "src2"}, {"WordSourceAI": "VAL2"}),
])
def test_apply_field_mapping_parameterized(field_setup, row_data, field_mapping, expected_values):
    _, field_index_map, empty_row = field_setup
    csv_row = list(empty_row)
    
    apply_field_mapping(csv_row, row_data, field_mapping, field_index_map)
    
    for field_name, expected_val in expected_values.items():
        if field_name in field_index_map:
            assert csv_row[field_index_map[field_name]] == expected_val

def test_apply_field_mapping_unknown_anki_field(field_setup):
    _, field_index_map, empty_row = field_setup
    csv_row = list(empty_row)
    row_data = {"source_word": "test_word"}
    field_mapping = {"UnknownFieldXYZ": "source_word"}
    
    # Should not throw an exception
    apply_field_mapping(csv_row, row_data, field_mapping, field_index_map)
    assert csv_row == empty_row

def test_apply_field_mapping_sentence_mode(field_setup):
    _, field_index_map, empty_row = field_setup
    csv_row = list(empty_row)
    row_data = {
        "source_sentence": "Source.",
        "target_sentence": "Target.",
        "deck_name": "TestDeck"
    }
    field_mapping = {
        "SentenceSource": "source_sentence",
        "SentenceDestination": "target_sentence",
        "Deck": "deck_name"
    }
    
    apply_field_mapping(csv_row, row_data, field_mapping, field_index_map)
    assert csv_row[field_index_map["SentenceSource"]] == "Source."
    assert csv_row[field_index_map["SentenceDestination"]] == "Target."
    assert csv_row[field_index_map["Deck"]] == "TestDeck"

def test_prepare_row_data_basic():
    args = SimpleNamespace(language="de", tts_destination_lang="ru")
    data = prepare_row_data(
        args,
        lemma="Haus",
        source_word="Häuser",
        source_sentence="Schöne Häuser.",
        deck_name="German::Architecture"
    )
    
    assert data['lemma'] == "Haus"
    assert data['source_word'] == "Häuser"
    assert data['source_sentence'] == "Schöne Häuser."
    assert data['deck_name'] == "German::Architecture"
    assert data.get('tts_source_de') == "1"
    assert data.get('tts_dest_ru') == "1"

def test_prepare_row_data_empty_args():
    args = SimpleNamespace(language=None, tts_destination_lang=None)
    data = prepare_row_data(args, lemma="test")
    assert data['lemma'] == "test"
    assert 'tts_source_None' not in data
    assert 'tts_dest_None' not in data

def test_prepare_row_data_subtitle_start_time():
    args = SimpleNamespace(language="en", tts_destination_lang="de")
    data = prepare_row_data(args, lemma="hello", subtitle_start_time="1.234")
    assert data['lemma'] == "hello"
    assert data['subtitle_start_time'] == "1.234"

def test_get_anki_csv_header_override():
    custom_header = ["A", "B", "C"]
    header = get_anki_csv_header(header_override=custom_header)
    assert header == custom_header
    
    f_map = get_field_index_map(header_override=custom_header)
    assert f_map == {"A": 0, "B": 1, "C": 2}

def test_apply_field_mapping_preserves_raw_source_word_for_quotation(field_setup):
    _, field_index_map, empty_row = field_setup
    csv_row = list(empty_row)
    row_data = {
        "source_word": "isn't, is",
        "raw_source_word": "isn't",
        "lemma": "be"
    }
    field_mapping = {
        "Quotation": "source_word",
        "WordSource": "lemma",
        "WordSourceInflectedForm": "source_word",
        "WordSourceInflectedForm2": "source_word"
    }
    apply_field_mapping(csv_row, row_data, field_mapping, field_index_map)
    assert csv_row[field_index_map["Quotation"]] == "isn't"
    assert csv_row[field_index_map["WordSource"]] == "be"
    assert csv_row[field_index_map["WordSourceInflectedForm"]] == "isn't, is"
    assert csv_row[field_index_map["WordSourceInflectedForm2"]] == "isn't, is"

