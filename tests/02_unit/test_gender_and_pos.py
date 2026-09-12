import pytest
from types import SimpleNamespace
from kardenwort.core.kardenwort import (
    FIELD_WORD_SOURCE_POS,
    FIELD_WORD_SOURCE_GENDER,
    KEY_POS,
    KEY_GENDER,
    normalize_pos_tag,
    extract_gender_from_token,
    prepare_row_data,
    apply_field_mapping,
    RemoteToken,
    RemoteDoc,
    ExtractionConfig,
)
from mock_nlp import MockToken


def test_normalize_pos_tag():
    assert normalize_pos_tag("NOUN") == "n."
    assert normalize_pos_tag("PROPN") == "n."
    assert normalize_pos_tag("VERB") == "v."
    assert normalize_pos_tag("AUX") == "v."
    assert normalize_pos_tag("ADJ") == "adj."
    assert normalize_pos_tag("ADV") == "adv."
    assert normalize_pos_tag("ADP") == "prep."
    assert normalize_pos_tag("PREP") == "prep."
    assert normalize_pos_tag("PRON") == "pron."
    assert normalize_pos_tag("CCONJ") == "conj."
    assert normalize_pos_tag("SCONJ") == "conj."
    assert normalize_pos_tag("CONJ") == "conj."
    assert normalize_pos_tag("NUM") == "num."
    assert normalize_pos_tag("DET") == "art."
    assert normalize_pos_tag("PART") == "part."
    assert normalize_pos_tag("INTJ") == "intj."
    # Lowercase or already normalized
    assert normalize_pos_tag("n.") == "n."
    assert normalize_pos_tag("noun") == "n."
    assert normalize_pos_tag("verb") == "v."
    assert normalize_pos_tag("") == ""
    assert normalize_pos_tag(None) == ""


def test_extract_gender_from_token_nouns():
    tok_masc = MockToken("Tisch", pos_="NOUN", gender_morph=["Masc"])
    assert extract_gender_from_token(tok_masc) == "m"

    tok_fem = MockToken("Tür", pos_="NOUN", gender_morph=["Fem"])
    assert extract_gender_from_token(tok_fem) == "f"

    tok_neut = MockToken("Haus", pos_="NOUN", gender_morph=["Neut"])
    assert extract_gender_from_token(tok_neut) == "n"

    tok_propn = MockToken("Berlin", pos_="PROPN", gender_morph=["Neut"])
    assert extract_gender_from_token(tok_propn) == "n"


def test_extract_gender_strict_noun_restriction():
    # Verbs must never have gender, even if morph has gender data
    tok_verb = MockToken("gehen", pos_="VERB", gender_morph=["Masc"])
    assert extract_gender_from_token(tok_verb) == ""

    # Adjectives must never have gender
    tok_adj = MockToken("schön", pos_="ADJ", gender_morph=["Fem"])
    assert extract_gender_from_token(tok_adj) == ""

    # Pronouns, prepositions, etc.
    tok_prep = MockToken("über", pos_="ADP", gender_morph=["Neut"])
    assert extract_gender_from_token(tok_prep) == ""


def test_remote_token_gender_and_pos():
    token_dict = {
        "word": "Haus",
        "lemma": "Haus",
        "pos": "NOUN",
        "gender": "n",
        "morphology": "Gender=Neut|Number=Sing",
        "sentence_index": 1,
        "idx": 0,
        "whitespace": " "
    }
    tok = RemoteToken(
        word=token_dict["word"],
        lemma=token_dict["lemma"],
        pos=token_dict["pos"],
        morphology=token_dict["morphology"],
        gender=token_dict["gender"]
    )
    assert tok.pos_ == "NOUN"
    assert tok.gender == "n"

    doc = RemoteDoc([token_dict], raw_text="Haus ")
    assert len(doc) == 1
    assert doc[0].gender == "n"
    assert doc[0].pos_ == "NOUN"


def test_prepare_row_data_and_field_mapping_gender_pos():
    cfg = ExtractionConfig()
    row_data = prepare_row_data(
        cfg,
        lemma="Haus",
        source_word="Häuser",
        pos="NOUN",
        gender="n"
    )
    assert row_data[KEY_POS] == "n."
    assert row_data[KEY_GENDER] == "n"

    header = ["WordSource", "WordSourcePOS", "WordSourceGender"]
    field_index_map = {name: i for i, name in enumerate(header)}
    csv_row = [""] * len(header)
    field_mapping = {
        "WordSourcePOS": "pos",
        "WordSourceGender": "gender"
    }
    apply_field_mapping(csv_row, row_data, field_mapping, field_index_map)
    assert csv_row[field_index_map["WordSourcePOS"]] == "n."
    assert csv_row[field_index_map["WordSourceGender"]] == "n"


def test_extract_gender_lemma_precedence():
    # Contextual token 'Arbeiten' in 'das Arbeiten' has Neut morph
    tok_substantivized = MockToken("Arbeiten", pos_="NOUN", gender_morph=["Neut"])
    
    class MockArbeitNLP:
        lang = 'de'
        def __call__(self, text):
            if text == "Arbeit":
                return [MockToken("Arbeit", pos_="NOUN", gender_morph=["Fem"])]
            return [MockToken(text, pos_="NOUN", gender_morph=["Neut"])]
            
    mock_nlp = MockArbeitNLP()
    assert extract_gender_from_token(tok_substantivized, lemma="Arbeit", nlp_model=mock_nlp) == "f"

