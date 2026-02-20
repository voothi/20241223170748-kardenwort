import unittest
from kardenwort.core.kardenwort import apply_field_mapping, get_anki_csv_header, get_field_index_map

class TestFieldMapping(unittest.TestCase):

    def setUp(self):
        self.header = get_anki_csv_header()
        self.field_index_map = get_field_index_map()
        self.empty_row = [""] * len(self.header)
        
    def test_apply_field_mapping_empty(self):
        csv_row = list(self.empty_row)
        row_data = {"source_word": "test_word", "lemma": "test_lemma"}
        field_mapping = {}
        
        apply_field_mapping(csv_row, row_data, field_mapping, self.field_index_map)
        
        self.assertEqual(csv_row, self.empty_row)

    def test_apply_field_mapping_basic(self):
        csv_row = list(self.empty_row)
        row_data = {"source_word": "test_word", "lemma": "test_lemma"}
        field_mapping = {"WordSourceAI": "source_word"}
        
        apply_field_mapping(csv_row, row_data, field_mapping, self.field_index_map)
        
        expected_idx = self.field_index_map["WordSourceAI"]
        self.assertEqual(csv_row[expected_idx], "test_word")

    def test_apply_field_mapping_multiple(self):
        csv_row = list(self.empty_row)
        row_data = {
            "source_word": "inflected", 
            "lemma": "base",
            "source_sentence": "Das ist ein Satz."
        }
        field_mapping = {
            "WordSourceAI": "source_word",
            "WordSourceInflectedFormAI": "lemma",
            "SentenceSource": "source_sentence"
        }
        
        apply_field_mapping(csv_row, row_data, field_mapping, self.field_index_map)
        
        self.assertEqual(csv_row[self.field_index_map["WordSourceAI"]], "inflected")
        self.assertEqual(csv_row[self.field_index_map["WordSourceInflectedFormAI"]], "base")
        self.assertEqual(csv_row[self.field_index_map["SentenceSource"]], "Das ist ein Satz.")

    def test_apply_field_mapping_unknown_anki_field(self):
        csv_row = list(self.empty_row)
        row_data = {"source_word": "test_word"}
        field_mapping = {"UnknownFieldXYZ": "source_word"}
        
        # Should not throw an exception, but warn internally
        apply_field_mapping(csv_row, row_data, field_mapping, self.field_index_map)
        
        self.assertEqual(csv_row, self.empty_row)

    def test_apply_field_mapping_unknown_data_source(self):
        csv_row = list(self.empty_row)
        row_data = {"source_word": "test_word"}
        field_mapping = {"WordSourceAI": "missing_source"}
        
        apply_field_mapping(csv_row, row_data, field_mapping, self.field_index_map)
        
        expected_idx = self.field_index_map["WordSourceAI"]
        self.assertEqual(csv_row[expected_idx], "")

    def test_apply_field_mapping_sentence_mode(self):
        csv_row = list(self.empty_row)
        row_data = {
            "source_sentence": "This is a sentence.",
            "target_sentence": "Das ist ein Satz.",
            "deck_name": "TestDeck"
        }
        field_mapping = {
            "SentenceSource": "source_sentence",
            "SentenceDestination": "target_sentence",
            "Deck": "deck_name"
        }
        
        apply_field_mapping(csv_row, row_data, field_mapping, self.field_index_map)
        
        self.assertEqual(csv_row[self.field_index_map["SentenceSource"]], "This is a sentence.")
        self.assertEqual(csv_row[self.field_index_map["SentenceDestination"]], "Das ist ein Satz.")
        self.assertEqual(csv_row[self.field_index_map["Deck"]], "TestDeck")

    def test_apply_field_mapping_case_preservation(self):
        # Ensure that the logic doesn't fail if DataSource names differ only in case 
        # (though currently the logic just uses .get on the dict)
        csv_row = list(self.empty_row)
        row_data = {"SourceWord": "MixedCase"}
        field_mapping = {"WordSourceAI": "SourceWord"}
        
        apply_field_mapping(csv_row, row_data, field_mapping, self.field_index_map)
        
        self.assertEqual(csv_row[self.field_index_map["WordSourceAI"]], "MixedCase")

    def test_field_index_map_size(self):
        self.assertEqual(len(self.field_index_map), len(self.header))

    def test_get_tts_field_indices_validity(self):
        from kardenwort.core.kardenwort import get_tts_field_indices
        tts_indices = get_tts_field_indices()
        
        # Check source languages
        for lang_key in ['en', 'us', 'de', 'uk', 'ru']:
            idx = tts_indices['source'][lang_key]
            self.assertIsInstance(idx, int)
            self.assertTrue(0 <= idx < len(self.header))
            
        # Check destination languages
        for lang_key in ['en', 'us', 'de', 'uk', 'ru']:
            idx = tts_indices['destination'][lang_key]
            self.assertIsInstance(idx, int)
            self.assertTrue(0 <= idx < len(self.header))

    def test_apply_field_mapping_duplicate_mapping(self):
        csv_row = list(self.empty_row)
        row_data = {"src1": "VAL1", "src2": "VAL2"}
        field_mapping = {"WordSourceAI": "src1"}
        field_mapping["WordSourceAI"] = "src2" # Overwrite mapping
        
        apply_field_mapping(csv_row, row_data, field_mapping, self.field_index_map)
        
        self.assertEqual(csv_row[self.field_index_map["WordSourceAI"]], "VAL2")

if __name__ == '__main__':
    unittest.main()
