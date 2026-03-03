import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
import json
import sys
import os

# Add src to sys.path to allow importing from kardenwort
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))

from kardenwort.core.kardenwort_runner import get_script_args

class TestConfigConsistency(unittest.TestCase):

    def setUp(self):
        self.python_path = Path("/mock/python")
        self.workspace_path = Path("/mock/workspace")
        
        self.config = MagicMock()
        # Mocking config sections
        self.config.get.side_effect = self.mock_get
        self.config.getboolean.side_effect = self.mock_getboolean
        self.config.__getitem__.side_effect = self.mock_getitem
        self.config.__contains__.side_effect = self.mock_contains
        self.config.items.side_effect = self.mock_items

    def mock_get(self, section, option, fallback=None):
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

    def mock_getboolean(self, section, option, fallback=None):
        data = {
            ('output_format', 'wordlist_use_br'): False,
            ('output_format', 'add_header'): True
        }
        return data.get((section, option), fallback)

    def mock_getitem(self, key):
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
            }
        }
        if key in sections:
            return sections[key]
        raise KeyError(key)

    def mock_contains(self, key):
        return key in ['language_resources', 'anki_fields', 'anki_field_mapping.word']

    def mock_items(self, section):
        if section == 'anki_fields':
            return [('Quotation', ''), ('WordSourceAI', '')]
        return []

    def test_get_script_args_de_word(self):
        class Args:
            language = "de"
            type = "word"
            mode = "single"
            deduplication_scope = "global"
            tts_destination_lang = "ru"
            text = None
            multi_text = False
            prefer_shortest_form = False
            anki_create_subdecks = False
            anki_parent_deck = None
            anki_markdown_decks = False
            anki_sentence_subdecks = False
            anki_deck_content = None
            strip_headers = None
            de_gcs = False

        args = Args()
        script_args = get_script_args(args, self.python_path, self.workspace_path, self.config)
        
        # Verify base args
        self.assertIn("--language", script_args)
        self.assertIn("de", script_args)
        self.assertIn("--type", script_args)
        self.assertIn("word", script_args)
        
        # Verify config-driven args
        self.assertIn("--add-header", script_args)
        self.assertNotIn("--wordlist-use-br", script_args)
        
        # Verify mapped fields
        self.assertIn("--anki-csv-header", script_args)
        header_json = script_args[script_args.index("--anki-csv-header") + 1]
        self.assertEqual(json.loads(header_json), ["Quotation", "WordSourceAI"])

    def test_get_script_args_wordlist_br_enabled(self):
        self.config.getboolean.side_effect = lambda s, o, fallback=None: True if o == 'wordlist_use_br' else self.mock_getboolean(s, o, fallback)
        
        class Args:
            language = "de"
            type = "word"
            mode = "single"
            deduplication_scope = "global"
            tts_destination_lang = None
            text = None
            multi_text = False
            prefer_shortest_form = False
            anki_create_subdecks = False
            anki_parent_deck = None
            anki_markdown_decks = False
            anki_sentence_subdecks = False
            anki_deck_content = None
            strip_headers = None
            de_gcs = False
            
        args = Args()
        script_args = get_script_args(args, self.python_path, self.workspace_path, self.config)
        self.assertIn("--wordlist-use-br", script_args)

if __name__ == '__main__':
    unittest.main()
