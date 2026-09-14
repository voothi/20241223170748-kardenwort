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
    resolve_contraction_constituent_pos,
    _extract_mapped_token,
)
from mock_nlp import MockToken, MockDoc


def test_resolve_contraction_constituent_pos():
    # Preposition sub-lemmas
    for prep in ["zu", "in", "an", "bei", "von", "für", "durch", "um", "auf", "unter", "hinter", "vor"]:
        assert resolve_contraction_constituent_pos(prep) == "prep."
    
    # Article sub-lemmas
    for art in ["der", "die", "das", "dem", "den", "des", "ein", "eine", "einem", "einen", "einer"]:
        assert resolve_contraction_constituent_pos(art) == "art."

    # Pronoun sub-lemmas
    for pron in ["es", "ich", "du", "er", "sie"]:
        assert resolve_contraction_constituent_pos(pron) == "pron."

    # Unknown tokens fallback to default_pos
    assert resolve_contraction_constituent_pos("gehen", default_pos="v.") == "v."
    assert resolve_contraction_constituent_pos("Haus", default_pos="n.") == "n."


def test_extract_mapped_token_contraction_pos_zur():
    import argparse
    from mock_nlp import MockPipelineNLP

    nlp = MockPipelineNLP('de')
    match = {
        'source_word': 'zur',
        'lemmas': ['zu', 'der']
    }
    args = argparse.Namespace(
        token_mappings_lemmatize=False,
        combine_source_words_order='contractions_first',
        combine_source_words_prefer_lowercase=True,
        apostrophe_chars="', ’, ‘, `, ´, ʼ"
    )

    valid_lemmas, mapped_sources, mapped_pos = _extract_mapped_token(
        match, nlp, None, {}, args, "Wir gehen zur Schule.", False, return_pos=True
    )
    assert valid_lemmas == ["zu", "der"]
    assert mapped_pos["zu"] == "prep."
    assert mapped_pos["der"] == "art."


def test_extract_mapped_token_contraction_pos_german_apprart_variants():
    import argparse
    from mock_nlp import MockPipelineNLP

    nlp = MockPipelineNLP('de')
    args = argparse.Namespace(
        token_mappings_lemmatize=False,
        combine_source_words_order='contractions_first',
        combine_source_words_prefer_lowercase=True,
        apostrophe_chars="', ’, ‘, `, ´, ʼ"
    )

    contractions = [
        ("im", ["in", "dem"], "prep.", "art."),
        ("am", ["an", "dem"], "prep.", "art."),
        ("beim", ["bei", "dem"], "prep.", "art."),
        ("vom", ["von", "dem"], "prep.", "art."),
        ("ans", ["an", "das"], "prep.", "art."),
        ("ins", ["in", "das"], "prep.", "art."),
        ("zum", ["zu", "dem"], "prep.", "art."),
        ("zur", ["zu", "der"], "prep.", "art."),
    ]

    for source_word, sub_lemmas, expected_pos1, expected_pos2 in contractions:
        match = {'source_word': source_word, 'lemmas': sub_lemmas}
        _, _, mapped_pos = _extract_mapped_token(
            match, nlp, None, {}, args, f"Er ist {source_word} Haus.", False, return_pos=True
        )
        assert mapped_pos[sub_lemmas[0]] == expected_pos1
        assert mapped_pos[sub_lemmas[1]] == expected_pos2


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


def test_extract_gender_contextual_substantivized_and_plural():
    # Substantivized verb: 'das Arbeiten' -> NOUN with Neut gender -> 'n'
    tok_substantivized = MockToken("Arbeiten", pos_="NOUN", gender_morph=["Neut"])
    assert extract_gender_from_token(tok_substantivized) == "n"

    # Plural feminine noun: 'die Arbeiten' -> NOUN with Fem gender -> 'f'
    tok_plural_fem = MockToken("Arbeiten", pos_="NOUN", gender_morph=["Fem"])
    assert extract_gender_from_token(tok_plural_fem) == "f"


def test_extract_gender_grundwort_compound_precedence():
    # Suffix/Grundwort '-partner' resolves strictly to 'm', overriding contextual statistical misclassifications
    tok_partner_misclassified = MockToken("Lieferpartner", pos_="NOUN", gender_morph=["Fem"])
    assert extract_gender_from_token(tok_partner_misclassified) == "m"

    # Capitalized German noun misclassified as ADJ or PROPN by spaCy
    tok_adj_misclassified = MockToken("Lieferpartner", pos_="ADJ")
    assert extract_gender_from_token(tok_adj_misclassified) == "m"

    tok_propn_partner = MockToken("Handelspartner", pos_="PROPN")
    assert extract_gender_from_token(tok_propn_partner) == "m"

    # Grundwort '-mann'
    tok_mann = MockToken("Kaufmann", pos_="NOUN", gender_morph=["Fem"])
    assert extract_gender_from_token(tok_mann) == "m"

    # Derivational suffixes
    assert extract_gender_from_token(MockToken("Lieferung", pos_="NOUN")) == "f"
    assert extract_gender_from_token(MockToken("Wahrheit", pos_="NOUN")) == "f"
    assert extract_gender_from_token(MockToken("Möglichkeit", pos_="NOUN")) == "f"
    assert extract_gender_from_token(MockToken("Freundschaft", pos_="NOUN")) == "f"
    assert extract_gender_from_token(MockToken("Universität", pos_="NOUN")) == "f"
    assert extract_gender_from_token(MockToken("Mädchen", pos_="NOUN")) == "n"
    assert extract_gender_from_token(MockToken("Dokument", pos_="NOUN")) == "n"


def test_extract_gender_definite_article_precedence_das_arbeiten():
    # Definite article 'das' child strictly resolves to 'n' even if base token or morph indicates otherwise
    tok_art = MockToken("das", pos_="DET", dep_="nk", head_i=1)
    tok_noun = MockToken("Arbeiten", pos_="NOUN", head_i=1, gender_morph=["Fem"])
    doc = MockDoc([tok_art, tok_noun], "das Arbeiten")
    assert extract_gender_from_token(tok_noun) == "n"


def test_extract_gender_real_spacy_amazon_lieferpartner_and_arbeiten():
    try:
        import spacy
        nlp = spacy.load("de_core_news_lg")
    except Exception:
        pytest.skip("spacy or de_core_news_lg model not installed in test environment")

    doc = nlp("Wie ist das Arbeiten als Fahrer:in bei einem Amazon Lieferpartner ?")
    token_arbeiten = None
    token_lieferpartner = None
    for token in doc:
        if token.text == "Arbeiten":
            token_arbeiten = token
        elif token.text == "Lieferpartner":
            token_lieferpartner = token

    assert token_arbeiten is not None
    assert token_lieferpartner is not None
    assert extract_gender_from_token(token_arbeiten) == "n"
    assert extract_gender_from_token(token_lieferpartner) == "m"



