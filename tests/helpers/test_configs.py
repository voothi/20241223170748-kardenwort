"""Shared configuration dictionaries, arg factories, and fixture baselines for Kardenwort tests."""

import argparse
from typing import Dict, Any, Set

# Standard 11-field Anki mapping baseline used across pipeline tests
DEFAULT_FIELD_MAPPING: Dict[str, str] = {
    "WordSource": "lemma",
    "Quotation": "source_word",
    "SentenceSource": "source_sentence",
    "SentenceSourceWordlist": "wordlist",
    "Deck": "deck_name",
    "Note": "subtitle_start_time",
    "SentenceSourceContextLeft": "source_context_left",
    "SentenceSourceContextRight": "source_context_right",
    "SentenceDestination": "target_sentence",
    "SentenceDestination2": "tertiary_sentence",
    "SentenceSourceIndex": "sentence_index",
}

# Standard empty 5-tier lemma override rules structure
DEFAULT_OVERRIDE_RULES: Dict[str, Any] = {
    "priority1": {},
    "priority1_regex": [],
    "priority2": {},
    "priority2_regex": [],
    "priority3": {}
}

# Standard test German vocabulary dictionary
DEFAULT_DE_DICTIONARY: Set[str] = {
    "Bundes", "Land", "Verwaltung",
    "Haus", "Auto", "Hund",
    "Satz", "Title",
    "Eins", "Zwei", "Drei", "Vier", "Groß"
}


def extract_gcs_kwargs(args: argparse.Namespace) -> Dict[str, Any]:
    """Extracts the standardized German compound splitting & classification flags from an args namespace."""
    return {
        'de_gcs_only_nouns': getattr(args, 'de_gcs_only_nouns', True),
        'de_gcs_combine_noun_modes': getattr(args, 'de_gcs_combine_noun_modes', False),
        'de_fix_genitive': getattr(args, 'de_fix_genitive', False),
        'de_gcs_mask_unknown_parts': getattr(args, 'de_gcs_mask_unknown_parts', False),
        'de_gcs_preserve_compound_word': getattr(args, 'de_gcs_preserve_compound_word', False),
        'de_gcs_skip_merge_fractions': getattr(args, 'de_gcs_skip_merge_fractions', False),
        'classifications': getattr(args, 'classifications', {}),
        'token_mappings': getattr(args, 'token_mappings', {}),
    }
