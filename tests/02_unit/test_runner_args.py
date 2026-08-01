import pytest
from pathlib import Path
import json
import sys
from unittest.mock import MagicMock

# Add src to sys.path to allow importing from kardenwort
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / 'src'))

from kardenwort.core.kardenwort_runner import get_script_args

class MockArgs:
    def __init__(self, **kwargs):
        self.language = "de"
        self.type = "word"
        self.mode = "single"
        self.deduplication_scope = "global"
        self.tts_destination_lang = None
        self.text = None
        self.multi_text = False
        self.prefer_shortest_form = False
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
        
        for k, v in kwargs.items():
            setattr(self, k, v)

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
                'override_file_en': 'en/override.tsv'
            },
            'anki_field_mapping.word': {
                'WordSourceAI': 'lemma',
                'Quotation': 'source_word'
            },
            'anki_field_mapping.sentence': {
                'Quotation': 'source_sentence',
                'SentenceSource': 'source_sentence'
            }
        }
        if key in sections:
            return sections[key]
        raise KeyError(key)

    config.get.side_effect = mock_get
    config.getboolean.side_effect = mock_getboolean
    config.__getitem__.side_effect = mock_getitem
    config.__contains__.side_effect = lambda k: k in ['language_resources', 'anki_fields', 'anki_field_mapping.word', 'anki_field_mapping.sentence']
    config.items.side_effect = lambda section: [('Quotation', ''), ('WordSourceAI', '')] if section == 'anki_fields' else []
    
    return config

def test_get_script_args_de_word(mock_config):
    python_path = Path("/mock/python")
    workspace_path = Path("/mock/workspace")
    args = MockArgs(language="de", type="word", tts_destination_lang="ru")
    
    script_args = get_script_args(args, python_path, workspace_path, mock_config, mock_config)
    
    # Verify base args
    assert "--language" in script_args
    assert "de" in script_args
    assert "--type" in script_args
    assert "word" in script_args
    
    # Verify config-driven args
    assert "--add-header" in script_args
    assert "--wordlist-use-br" not in script_args
    
    # Verify mapped fields
    assert "--anki-csv-header" in script_args
    header_json = script_args[script_args.index("--anki-csv-header") + 1]
    assert json.loads(header_json) == ["Quotation", "WordSourceAI"]

def test_get_script_args_wordlist_br_enabled(mock_config):
    # Enable wordlist_use_br for this test
    original_getboolean = mock_config.getboolean.side_effect
    mock_config.getboolean.side_effect = lambda s, o, fallback=None: True if o == 'wordlist_use_br' else original_getboolean(s, o, fallback)
    
    python_path = Path("/mock/python")
    workspace_path = Path("/mock/workspace")
    args = MockArgs(language="de", type="word")
    
    script_args = get_script_args(args, python_path, workspace_path, mock_config, mock_config)
    assert "--wordlist-use-br" in script_args

@pytest.mark.parametrize("lang, expected_lemma", [
    ("de", "de/deu.csv"),
    ("en", "en/en.csv")
])
def test_get_script_args_languages(mock_config, lang, expected_lemma):
    python_path = Path("/mock/python")
    workspace_path = Path("/mock/workspace")
    args = MockArgs(language=lang, type="word")
    
    script_args = get_script_args(args, python_path, workspace_path, mock_config, mock_config)
    assert f"--lemma-index-file" in script_args
    # Find the index of --lemma-index-file and check the next element
    idx = script_args.index("--lemma-index-file")
    assert expected_lemma in script_args[idx+1].replace('\\', '/')

def test_get_script_args_missing_lang_config(mock_config):
    python_path = Path("/mock/python")
    workspace_path = Path("/mock/workspace")
    args = MockArgs(language="fr", type="word")
    
    with pytest.raises(ValueError, match="Missing config for language 'fr'"):
        get_script_args(args, python_path, workspace_path, mock_config, mock_config)


def test_get_script_args_gcs_orthogonal_flags(mock_config):
    python_path = Path("/mock/python")
    workspace_path = Path("/mock/workspace")
    args = MockArgs(
        language="de",
        type="word",
        de_gcs=True,
        de_gcs_pos_tags=["ALL"],
        de_gcs_preserve_compound_word=True,
        de_gcs_split_mode="only-nouns"
    )
    
    script_args = get_script_args(args, python_path, workspace_path, mock_config, mock_config)
    assert "--de-gcs" in script_args
    assert "--de-gcs-pos-tags" in script_args
    assert "ALL" in script_args
    assert "--de-gcs-preserve-compound-word" in script_args
    assert "--de-gcs-split-mode" in script_args
    assert "only-nouns" in script_args
