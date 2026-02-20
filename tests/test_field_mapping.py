import unittest
from kardenwort.core.kardenwort import apply_field_mapping, get_anki_csv_header, get_field_index_map, prepare_row_data

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

    def test_prepare_row_data_basic(self):
        class MockArgs:
            language = "de"
            tts_destination_lang = "ru"
        
        args = MockArgs()
        data = prepare_row_data(
            args,
            lemma="Haus",
            source_word="Häuser",
            source_sentence="Schöne Häuser.",
            deck_name="German::Architecture"
        )
        
        self.assertEqual(data['lemma'], "Haus")
        self.assertEqual(data['source_word'], "Häuser")
        self.assertEqual(data['source_sentence'], "Schöne Häuser.")
        self.assertEqual(data['deck_name'], "German::Architecture")
        self.assertEqual(data['tts_source_de'], "1")
        self.assertEqual(data['tts_dest_ru'], "1")

    def test_prepare_row_data_empty_args(self):
        class MockArgs:
            language = None
            tts_destination_lang = None
        
        args = MockArgs()
        data = prepare_row_data(args, lemma="test")
        self.assertEqual(data['lemma'], "test")
        # Ensure no tts keys are added
        self.assertNotIn('tts_source_None', data)
        self.assertNotIn('tts_dest_None', data)

    def test_get_anki_csv_header_override(self):
        custom_header = ["A", "B", "C"]
        header = get_anki_csv_header(header_override=custom_header)
        self.assertEqual(header, custom_header)
        
        f_map = get_field_index_map(header_override=custom_header)
        self.assertEqual(f_map, {"A": 0, "B": 1, "C": 2})

    def test_apply_field_mapping_duplicate_mapping(self):
        csv_row = list(self.empty_row)
        row_data = {"src1": "VAL1", "src2": "VAL2"}
        field_mapping = {"WordSourceAI": "src1"}
        field_mapping["WordSourceAI"] = "src2" # Overwrite mapping
        
        apply_field_mapping(csv_row, row_data, field_mapping, self.field_index_map)
        
        self.assertEqual(csv_row[self.field_index_map["WordSourceAI"]], "VAL2")

if __name__ == '__main__':
    unittest.main()
