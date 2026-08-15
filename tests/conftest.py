"""Global pytest fixtures and root test environment configuration."""

import sys
import argparse
from pathlib import Path
import pytest

# Ensure src and tests/helpers are on sys.path globally for all test runs
tests_root = Path(__file__).resolve().parent
src_path = str(tests_root.parent / 'src')
helpers_path = str(tests_root / 'helpers')

if src_path not in sys.path:
    sys.path.insert(0, src_path)
if helpers_path not in sys.path:
    sys.path.insert(0, helpers_path)

import kardenwort.core.kardenwort as kw
from mock_nlp import MockPipelineNLP
from test_configs import DEFAULT_FIELD_MAPPING, DEFAULT_OVERRIDE_RULES, DEFAULT_DE_DICTIONARY


@pytest.fixture
def mock_nlp(monkeypatch):
    """Injects a stateless MockPipelineNLP instance into kardenwort core."""
    nlp_instance = MockPipelineNLP('de')
    monkeypatch.setattr(kw, 'nlp', nlp_instance, raising=False)
    import kardenwort.core.legacy_baselines as legacy_baselines
    monkeypatch.setattr(legacy_baselines, 'nlp', nlp_instance, raising=False)
    return nlp_instance


@pytest.fixture
def default_args(tmp_path):
    """Provides a standard baseline argparse.Namespace for extraction pipelines."""
    src_path = tmp_path / "src.txt"
    src_path.write_text("Haus Haus Auto.\nAuto Haus Hund.", encoding="utf-8")
    
    return argparse.Namespace(
        deduplication_scope='global',
        language='de',
        combine_source_words=False,
        combine_source_words_order='contractions_first',
        combine_source_words_prefer_lowercase=True,
        prefer_shortest_form=False,
        preserve_composite_tokens=False,
        strip_headers=None,
        add_header=True,
        wordlist_use_br=False,
        stdout_print_output_basename=False,
        de_gcs=False,
        de_gcs_add_parts_to_wordlist=False,
        de_gcs_pos_tags=['NN', 'NOUN', 'N'],
        de_fix_genitive=False,
        de_gcs_mask_unknown_parts=False,
        de_gcs_preserve_compound_word=False,
        de_gcs_skip_merge_fractions=False,
        de_gcs_only_nouns=True,
        de_gcs_combine_noun_modes=False,
        de_gcs_part_singularization='only-nouns',
        anki_markdown_decks=False,
        anki_create_subdecks=False,
        anki_parent_deck=None,
        anki_deck_content=False,
        anki_sentence_subdecks=False,
        anki_context_use_br=False,
        source_timestamps=[],
        token_mappings_enabled=False,
        token_mappings_lemmatize=False,
        use_simplemma_correction=False,
        simplemma_smart_fallback=False,
        simplemma_after_spacy=False,
        de_force_noun_capitalization=True,
        force_proper_noun_capitalization=True,
        apostrophe_chars="', ’, ‘, `, ´, ʼ",
        type='word',
        text1_file=str(src_path),
        text2_file=None,
        text3_file=None,
        classification_case_sensitive=False,
        tts_destination_lang=None,
        tts_tertiary_lang=None,
    )


@pytest.fixture
def standard_field_mapping():
    """Returns a copy of the 11-field Anki mapping dictionary."""
    return dict(DEFAULT_FIELD_MAPPING)


@pytest.fixture
def standard_override_rules():
    """Returns a copy of the 5-tier empty lemma override rules structure."""
    return {k: v.copy() if isinstance(v, (dict, list)) else v for k, v in DEFAULT_OVERRIDE_RULES.items()}


@pytest.fixture
def standard_de_dictionary():
    """Returns a copy of the baseline German vocabulary test set."""
    return set(DEFAULT_DE_DICTIONARY)
