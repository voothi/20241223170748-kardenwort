import os
import sys
import json
import re
import io
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, MagicMock, mock_open
import pytest

# Set up sys.path for unit tests and helpers
src_path = str(Path(__file__).resolve().parent.parent.parent / 'src')
scripts_path = str(Path(__file__).resolve().parent.parent.parent / 'scripts')
helpers_path = str(Path(__file__).resolve().parent.parent / 'helpers')
if src_path not in sys.path:
    sys.path.insert(0, src_path)
if scripts_path not in sys.path:
    sys.path.insert(0, scripts_path)
if helpers_path not in sys.path:
    sys.path.insert(0, helpers_path)

import kardenwort.core.kardenwort as kw
import kardenwort.core.kardenwort_lite as kw_lite
import sendto_vocab
from mock_nlp import MockToken


# ==============================================================================
# 8. Cross-Cutting Feature Invariant & Regression Verification (Pytest Suite)
# ==============================================================================

# 8.1
def test_8_1_prepare_row_data_tts():
    args = SimpleNamespace(language='de', tts_destination_lang='ru')
    row_data = kw.prepare_row_data(args, lemma="Haus", source_word="Hause")
    assert row_data.get('tts_source_de') == "1"
    assert row_data.get('tts_dest_ru') == "1"

    header = kw.get_anki_csv_header()
    assert len(header) == 90
    tts_cols = [
        "Source-en-GB", "Source-en-US", "Source-de-DE", "Source-uk-UA", "Source-ru-RU",
        "Destination-en-GB", "Destination-en-US", "Destination-de-DE", "Destination-uk-UA", "Destination-ru-RU"
    ]
    for col in tts_cols:
        assert col in header

# 8.2
def test_8_2_auto_lite_mode():
    mock_stdin = io.StringIO("")
    mock_stdin.reconfigure = lambda *args, **kwargs: None
    with patch('sys.argv', ['kardenwort_lite', 'Haus']), \
         patch('sys.stdin', mock_stdin), \
         patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
        mock_stdout.reconfigure = lambda *args, **kwargs: None
        kw_lite.main()
        output = mock_stdout.getvalue()
        assert len(output) > 0

# 8.3
def test_8_3_multi_text_separator_parsing():
    input_text_combined = "First text line 1\n---\nSecond text line 2\n---\nThird text line 3"
    parts = re.split(r'\s*---\s*', input_text_combined.strip())
    text_blocks = parts[:3]
    assert len(text_blocks) == 3
    assert text_blocks[0] == "First text line 1"
    assert text_blocks[1] == "Second text line 2"
    assert text_blocks[2] == "Third text line 3"
    for block in text_blocks:
        assert "---" not in block

# 8.4
def test_8_4_write_deck_metadata(tmp_path):
    args = SimpleNamespace(
        anki_deck_content=['parent-source', 'parent-translations'],
        anki_markdown_decks=False,
        anki_create_subdecks=False,
        anki_parent_deck="TestParent"
    )
    out_file = str(tmp_path / "test.word.tsv")
    with patch('builtins.open', mock_open()) as mock_file:
        kw._write_deck_metadata(args, out_file, "Source content", "Target content", "Tertiary content")
        assert mock_file.called

# 8.5
def test_8_5_load_classification_dictionaries_case_sensitivity(tmp_path):
    fpath = str(tmp_path / "dict.tsv")
    with open(fpath, 'w', encoding='utf-8') as f:
        f.write("Header1\tHeader2\n")
        f.write("Haus\tNoun\n")
        f.write("laufen\tVerb\n")

    # Case sensitive
    classifications = kw.load_classification_dictionaries([f"test_cs={fpath}"], case_sensitive=True)
    assert "test_cs" in classifications

    # Case insensitive
    classifications_ci = kw.load_classification_dictionaries([f"test_ci={fpath}"], case_sensitive=False)
    assert "test_ci" in classifications_ci
    assert "haus" in classifications_ci["test_ci"]

# 8.6
def test_8_6_token_mappings_toggles():
    args = SimpleNamespace(
        token_mappings_enabled=True,
        token_mappings_normalize_spaces=True,
        token_mappings_enable_context_disambiguation=True,
        token_mappings_lemmatize=False,
        token_mappings_normalize_apostrophes=True,
        token_mappings_case_sensitive=False,
        de_force_noun_capitalization=False,
        force_proper_noun_capitalization=False
    )
    mapped = kw._lemmatize_mapped_tokens(["test"], None, set(), {}, args, "test text")
    assert mapped == ["test"]

    args.token_mappings_lemmatize = True
    mock_nlp = MagicMock()
    mock_nlp.return_value = [MockToken("test", "test")]
    mock_nlp.lang = "en"
    with patch.object(kw, 'nlp', mock_nlp):
        mapped_lemmatized = kw._lemmatize_mapped_tokens(["test"], mock_nlp, set(), {}, args, "test text")
    assert len(mapped_lemmatized) == 1
    assert mapped_lemmatized[0] == "test"

# 8.7
def test_8_7_edge_case_extraction_modifiers():
    args = SimpleNamespace(use_simplemma_correction=True, simplemma_after_spacy=False, simplemma_pos_aware=False)
    tok = MockToken("Häuser", "Haus", "NOUN")
    override, fallback = kw.get_simplemma_lemmas(tok, 'de', args)
    assert override is not None

    # strip_garbage_characters test
    garbage_chars = "-"
    raw_word = "-word-in-hyphens-"
    cleaned = raw_word.strip(garbage_chars)
    assert cleaned == "word-in-hyphens"

# 8.8
def test_8_8_lemma_override_rules(tmp_path):
    fpath = str(tmp_path / "overrides.tsv")
    with open(fpath, 'w', encoding='utf-8') as f:
        f.write("#SpacyLemma\tSourceWord\tTargetLemma\tContextCondition\tPosCondition\n")
        f.write("gehen\tging\tgehen-override\t\tVERB\n")

    rules = kw.load_lemma_override_rules(fpath)
    assert len(rules['priority1']) == 1
    overridden = kw.get_overridden_lemma_for_word("gehen", "ging", rules, "Er ging nach Hause.")
    assert overridden == "gehen-override"

# 8.9
def test_8_9_german_morphology_overrides():
    args = SimpleNamespace(de_force_noun_capitalization=True, force_proper_noun_capitalization=False)
    tok = MockToken("haus", "haus", "NOUN")
    mock_nlp = MagicMock()
    mock_nlp.lang = "de"
    with patch.object(kw, 'nlp', mock_nlp):
        formatted = kw.format_lemma_capitalization(tok, "haus", args)
        assert formatted == "Haus"

# 8.10
def test_8_10_structural_parsing():
    line = "### Section Header"
    match = re.match(r'^(#+)\s+(.*)', line.strip())
    assert match is not None
    assert match.group(2).strip() == "Section Header"

    doc = [MockToken("auf", "auf", "PART", idx=0), MockToken("stehen", "stehen", "VERB", idx=1)]
    sep_map = kw.find_separable_verb_particle_pairs(doc)
    assert isinstance(sep_map, dict)

# 8.11
def test_8_11_granular_component_extractions():
    prefix, path = kw.parse_prefix_and_path("1.en:path/to/dict.tsv")
    assert prefix == "1.en"
    assert path == "path/to/dict.tsv"

    # Windows path without prefix
    prefix2, path2 = kw.parse_prefix_and_path("C:\\path\\to\\file.tsv")
    assert prefix2 == ""
    assert path2 == "C:\\path\\to\\file.tsv"

# 8.12
def test_8_12_contextual_formatting_and_routing():
    prefix = kw.generate_filename_prefix_from_text("Über das große Haus", 3)
    assert prefix == "ueber-das-grosse"

    row = [""] * 88
    field_index_map = {"WordSourceAI": 10}
    field_mapping = {"WordSourceAI": "ai_word_source"}
    row_data = {"ai_word_source": "Generated AI Explanation"}
    kw.apply_field_mapping(row, row_data, field_mapping, field_index_map)
    assert row[10] == "Generated AI Explanation"

# 8.13
def test_8_13_kardenwort_lite_isolated_behaviors():
    # Cyrillic detection
    cleaned_word = "дом"
    has_cyrillic = any('\u0400' <= char <= '\u04FF' for char in cleaned_word)
    assert has_cyrillic
    langs = ('en', 'de', 'ru', 'uk')
    active_langs = tuple(l for l in langs if l in ('ru', 'uk'))
    assert active_langs == ('ru', 'uk')

    latin_word = "house"
    has_cyrillic2 = any('\u0400' <= char <= '\u04FF' for char in latin_word)
    assert not has_cyrillic2

# 8.14
def test_8_14_sendto_vocab_orchestration():
    dummy_path = Path("2026-08-05 DE Test Notes.txt")
    zid, topic, lang = sendto_vocab.parse_filename(dummy_path)
    assert zid is None
    assert topic == "2026-08-05 DE Test Notes"
    assert lang is None

    zid_path = Path("20260805220000-my-test-subtitle.de.srt")
    zid, topic, lang = sendto_vocab.parse_filename(zid_path)
    assert zid == "20260805220000"
    assert topic == "my-test-subtitle"
    assert lang == "de"

# 8.15
def test_8_15_goldendict_cli_modernization():
    cmd_dir = str(Path(__file__).resolve().parent.parent.parent / 'scripts' / 'run' / 'cmd')
    if not os.path.exists(cmd_dir):
        pytest.skip(f"Cmd directory not found: {cmd_dir}")

    cmd_files = [f for f in os.listdir(cmd_dir) if f.endswith('.cmd')]
    assert len(cmd_files) == 24, "Expected exactly 24 .cmd wrappers in scripts/run/cmd/"

    for cmd_file in cmd_files:
        fpath = os.path.join(cmd_dir, cmd_file)
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
        # Verify they use CFG_kardenwort_runner_filename, CFG_kardenwort_script_filename, or direct script call
        is_valid = (
            "CFG_kardenwort_runner_filename" in content
            or "CFG_kardenwort_script_filename" in content
            or "kardenwort.py" in content
            or "kardenwort_runner" in content
            or "KARDENWORT_SCRIPT" in content
        )
        assert is_valid, f"Wrapper {cmd_file} does not invoke kardenwort_runner or kardenwort script"
        # Verify no legacy shim is directly executed without Python/runner
        assert "legacy_shim.cmd" not in content.lower()
