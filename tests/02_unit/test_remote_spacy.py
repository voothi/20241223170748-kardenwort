import json
import time
import socket
import threading
import pytest
from unittest.mock import patch, MagicMock

from kardenwort.server.spacy_server import SpacyHTTPServer, SpacyRequestHandler
from kardenwort.core.kardenwort import (
    RemoteMorph,
    RemoteToken,
    RemoteSpan,
    RemoteDoc,
    RemotePipelineNLP,
    extract_lemmas_from_sentence,
)
from kardenwort.core.kardenwort_runner import get_script_args


def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def spacy_server():
    port = get_free_port()
    server = SpacyHTTPServer(('127.0.0.1', port), SpacyRequestHandler, preload_models=True)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(0.2)
    base_url = f"http://127.0.0.1:{port}"
    yield base_url
    server.shutdown()
    server.server_close()


def test_remote_morph():
    morph_empty = RemoteMorph("")
    assert not morph_empty
    assert morph_empty.get("Case") == []
    assert str(morph_empty) == ""

    morph_val = RemoteMorph("Case=Nom|Gender=Masc|Number=Sing")
    assert morph_val
    assert morph_val.get("Case") == ["Nom"]
    assert morph_val.get("Gender") == ["Masc"]
    assert morph_val.get("Missing", ["default"]) == ["default"]
    assert str(morph_val) == "Case=Nom|Gender=Masc|Number=Sing"


def test_remote_token_and_doc():
    tokens_data = [
        {"word": "Der", "lemma": "der", "pos": "DET", "tag": "ART", "morphology": "Case=Nom", "sentence_index": 1, "idx": 0, "whitespace": " "},
        {"word": "Hund", "lemma": "Hund", "pos": "NOUN", "tag": "NN", "morphology": "Case=Nom|Gender=Masc", "sentence_index": 1, "idx": 4, "whitespace": " "},
        {"word": "bellt", "lemma": "bellen", "pos": "VERB", "tag": "VVFIN", "morphology": "Person=3", "sentence_index": 1, "idx": 9, "whitespace": ". "},
        {"word": "Die", "lemma": "der", "pos": "DET", "tag": "ART", "morphology": "Case=Nom", "sentence_index": 2, "idx": 16, "whitespace": " "},
        {"word": "Katze", "lemma": "Katze", "pos": "NOUN", "tag": "NN", "morphology": "Case=Nom|Gender=Fem", "sentence_index": 2, "idx": 20, "whitespace": "."},
    ]
    raw_text = "Der Hund bellt. Die Katze."
    doc = RemoteDoc(tokens_data, raw_text)

    assert len(doc) == 5
    assert doc.text == raw_text
    assert len(doc.sents) == 2

    tok0 = doc[0]
    assert tok0.text == "Der"
    assert tok0.lemma_ == "der"
    assert tok0.pos_ == "DET"
    assert tok0.tag_ == "ART"
    assert tok0.is_sent_start is True
    assert tok0.is_alpha is True
    assert tok0.idx == 0
    assert tok0.whitespace_ == " "
    assert tok0.morph.get("Case") == ["Nom"]

    tok1 = doc[1]
    assert tok1.is_sent_start is False
    assert tok1.idx == 4
    assert tok1.whitespace_ == " "

    tok3 = doc[3]
    assert tok3.text == "Die"
    assert tok3.is_sent_start is True
    assert tok3.idx == 16

    assert tok0.doc is doc
    assert doc.sents[0].text == "Der Hund bellt."
    assert doc.sents[1].text == "Die Katze."
    assert doc.has_annotation("SENT_START") is True


def test_remote_doc_possessive_whitespace_and_attachment():
    from kardenwort.core.kardenwort import is_possessive_token, find_possessive_token_pairs
    tokens_data = [
        {"word": "Aschenbrenner", "lemma": "Aschenbrenner", "pos": "PROPN", "tag": "NNP", "morphology": "Number=Sing", "sentence_index": 1, "idx": 0, "whitespace": ""},
        {"word": "'s", "lemma": "'s", "pos": "PART", "tag": "POS", "morphology": "", "sentence_index": 1, "idx": 13, "whitespace": " "},
        {"word": "situational", "lemma": "situational", "pos": "ADJ", "tag": "JJ", "morphology": "Degree=Pos", "sentence_index": 1, "idx": 16, "whitespace": " "},
        {"word": "awareness", "lemma": "awareness", "pos": "NOUN", "tag": "NN", "morphology": "Number=Sing", "sentence_index": 1, "idx": 28, "whitespace": "."},
    ]
    raw_text = "Aschenbrenner's situational awareness."
    doc = RemoteDoc(tokens_data, raw_text)

    assert doc.sents[0].text == "Aschenbrenner's situational awareness."
    assert is_possessive_token(doc[1]) is True
    poss_indices, poss_suffixes = find_possessive_token_pairs(doc)
    assert 1 in poss_indices
    assert poss_suffixes[0] == "'s"



def test_remote_pipeline_nlp_live(spacy_server):
    nlp_client = RemotePipelineNLP(server_url=spacy_server, lang="de", timeout=5.0)
    raw_text = "Der schnelle braune Fuchs springt über den faulen Hund."
    doc = nlp_client(raw_text)

    assert isinstance(doc, RemoteDoc)
    assert len(doc) > 0
    words = [t.text for t in doc]
    assert "Fuchs" in words
    assert "springt" in words

    fuchs_tok = next(t for t in doc if t.text == "Fuchs")
    assert fuchs_tok.pos_ in ("NOUN", "PROPN")
    assert fuchs_tok.lemma_ == "Fuchs"
    assert fuchs_tok.idx == raw_text.index("Fuchs")
    assert fuchs_tok.whitespace_ == " "


def test_remote_pipeline_contractions_and_abbreviations_parity(spacy_server):
    # German abbreviations and contractions
    de_client = RemotePipelineNLP(server_url=spacy_server, lang="de", timeout=5.0)
    de_text = "Wir gehen zum Haus, bzw. in den Garten."
    de_doc = de_client(de_text)

    # Verify character offsets match slice positions in source text
    for tok in de_doc:
        assert de_text[tok.idx:tok.idx + len(tok.text)] == tok.text

    # English contractions
    en_client = RemotePipelineNLP(server_url=spacy_server, lang="en", timeout=5.0)
    en_text = "I've decided that there's no problem."
    en_doc = en_client(en_text)

    for tok in en_doc:
        assert en_text[tok.idx:tok.idx + len(tok.text)] == tok.text


def test_remote_pipeline_nlp_fallback():
    # Point to an unreachable port
    nlp_client = RemotePipelineNLP(server_url="http://127.0.0.1:59999", lang="de", timeout=0.5)

    mock_local_model = MagicMock()
    mock_local_doc = MagicMock()
    mock_local_model.return_value = mock_local_doc

    with patch.object(nlp_client, '_get_local_nlp', return_value=mock_local_model):
        doc = nlp_client("Ein Test")
        assert doc == mock_local_doc
        assert nlp_client._fallback_mode is True


def test_extract_lemmas_with_remote_nlp(spacy_server):
    nlp_client = RemotePipelineNLP(server_url=spacy_server, lang="de", timeout=5.0)
    lemmas = extract_lemmas_from_sentence(
        sentence_text="Der schnelle Fuchs springt.",
        lemma_sort_index={},
        nlp_model=nlp_client,
        de_dictionary={"Fuchs", "schnell", "springen", "der"}
    )
    assert "Fuchs" in lemmas
    assert any("spring" in l.lower() for l in lemmas)


@pytest.fixture
def mock_config():
    config = MagicMock()
    def mock_get(section, option, fallback=None):
        data = {
            ('project_structure', 'source_code_dir'): 'src/kardenwort/core',
            ('project_structure', 'data_dir'): 'data',
            ('project_structure', 'source_texts_dir'): 'source_texts',
            ('project_structure', 'generated_results_dir'): 'results',
            ('scripts', 'kardenwort_script_filename'): 'kardenwort.py',
            ('output_format', 'output_template'): 'result.{mode}.{suffix}.{language}.tsv',
            ('input_files', 'text1_file'): 'text1.txt',
            ('input_files', 'text2_file'): 'text2.txt',
            ('input_files', 'text3_file'): 'text3.txt',
            ('language_resources', 'dictionary_file_de'): 'german.dic'
        }
        return data.get((section, option), fallback)

    def mock_getboolean(section, option, fallback=None):
        data = {
            ('output_format', 'wordlist_use_br'): False,
            ('output_format', 'add_header'): True
        }
        return data.get((section, option), fallback)

    def mock_getitem(key):
        sections = {
            'language_resources': {
                'lemma_file_de': 'de/deu.csv',
                'override_file_de': 'de/override.tsv',
                'lemma_file_en': 'en/en.csv',
                'override_file_en': 'en/override.tsv',
            }
        }
        return sections[key]

    config.get.side_effect = mock_get
    config.getboolean.side_effect = mock_getboolean
    config.__getitem__.side_effect = mock_getitem
    config.has_section.return_value = False
    return config


def test_runner_args_with_spacy_server_url(mock_config):
    class MockArgs:
        def __init__(self):
            self.language = "de"
            self.type = "word"
            self.mode = "single"
            self.deduplication_scope = "global"
            self.tts_destination_lang = None
            self.text = "Hallo"
            self.multi_text = False
            self.prefer_shortest_form = False
            self.preserve_composite_tokens = False
            self.anki_create_subdecks = False
            self.anki_parent_deck = None
            self.anki_markdown_decks = False
            self.anki_sentence_subdecks = False
            self.anki_deck_content = None
            self.suspend_cards = False
            self.strip_headers = None
            self.de_gcs = False
            self.de_gcs_pos_tags = None
            self.text1_file = None
            self.text2_file = None
            self.text3_file = None
            self.spacy_server_url = "http://127.0.0.1:8081"

    mock_mapping = MagicMock()
    mock_mapping.__contains__.side_effect = lambda k: k in ('anki_fields', 'anki_field_mapping.word')
    mock_mapping.items.return_value = [('1', 'Quotation'), ('2', 'WordSource')]
    mock_mapping.__getitem__.return_value = {'Quotation': 'source_word', 'WordSource': 'lemma'}

    from pathlib import Path
    args = get_script_args(
        MockArgs(),
        python_path=Path("python"),
        workspace_path=Path("."),
        config=mock_config,
        anki_mapping=mock_mapping
    )
    assert "--spacy-server-url" in args
    idx = args.index("--spacy-server-url")
    assert args[idx + 1] == "http://127.0.0.1:8081"
