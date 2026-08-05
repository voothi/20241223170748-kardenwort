import itertools
import pytest
from typing import List, Dict, Any, Tuple
from pathlib import Path
import sys

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / 'src'))

# ==============================================================================
# 1. Combinatorial Matrix Generators
# ==============================================================================

EXTRACTION_FLAGS = [
    "prefer_lowercase",
    "combine_source_words",
    "prefer_shortest_form",
    "token_mappings_enabled",
]

GCS_FLAGS = [
    "de_gcs_only_nouns",
    "de_gcs_combine_noun_modes",
    "de_gcs_mask_unknown_parts",
    "de_gcs_preserve_compound_word",
    "de_gcs_skip_merge_fractions",
]

CAPITALIZATION_FLAGS = [
    "de_force_noun_capitalization",
    "force_proper_noun_capitalization",
    "de_fix_genitive",
]

TABULAR_FLAGS = [
    "add_wordlist_col",
    "wordlist_use_br",
    "anki_markdown_decks",
    "anki_sentence_subdecks",
]


def generate_extraction_matrix() -> List[Dict[str, Any]]:
    """
    Generates a deterministic 16-state parameter matrix across extraction flags.
    Returns 2^4 = 16 permutations.
    """
    matrix = list(itertools.product([True, False], repeat=len(EXTRACTION_FLAGS)))
    return [dict(zip(EXTRACTION_FLAGS, values)) for values in matrix]


def generate_gcs_matrix() -> List[Dict[str, Any]]:
    """
    Generates a deterministic 32-state parameter matrix across GCS flags.
    Returns 2^5 = 32 permutations.
    """
    matrix = list(itertools.product([True, False], repeat=len(GCS_FLAGS)))
    return [dict(zip(GCS_FLAGS, values)) for values in matrix]


def generate_capitalization_matrix() -> List[Dict[str, Any]]:
    """
    Generates a deterministic 8-state parameter matrix across capitalization flags.
    Returns 2^3 = 8 permutations.
    """
    matrix = list(itertools.product([True, False], repeat=len(CAPITALIZATION_FLAGS)))
    return [dict(zip(CAPITALIZATION_FLAGS, values)) for values in matrix]


def generate_tabular_matrix() -> List[Dict[str, Any]]:
    """
    Generates a deterministic 16-state parameter matrix across tabular mapping flags.
    Returns 2^4 = 16 permutations.
    """
    matrix = list(itertools.product([True, False], repeat=len(TABULAR_FLAGS)))
    return [dict(zip(TABULAR_FLAGS, values)) for values in matrix]


# ==============================================================================
# 2. Assertion Tests for Generator Dimensions and Completeness
# ==============================================================================

def test_extraction_matrix_dimensions_and_completeness():
    matrix = generate_extraction_matrix()
    assert len(matrix) == 16, "Extraction matrix must have exactly 16 permutations (2^4)."
    # Verify completeness and no duplicate configurations
    unique_tuples = {tuple(sorted(d.items())) for d in matrix}
    assert len(unique_tuples) == 16, "All configurations in extraction matrix must be unique."
    for item in matrix:
        assert set(item.keys()) == set(EXTRACTION_FLAGS)


def test_gcs_matrix_dimensions_and_completeness():
    matrix = generate_gcs_matrix()
    assert len(matrix) == 32, "GCS matrix must have exactly 32 permutations (2^5)."
    unique_tuples = {tuple(sorted(d.items())) for d in matrix}
    assert len(unique_tuples) == 32, "All configurations in GCS matrix must be unique."
    for item in matrix:
        assert set(item.keys()) == set(GCS_FLAGS)


def test_capitalization_matrix_dimensions_and_completeness():
    matrix = generate_capitalization_matrix()
    assert len(matrix) == 8, "Capitalization matrix must have exactly 8 permutations (2^3)."
    unique_tuples = {tuple(sorted(d.items())) for d in matrix}
    assert len(unique_tuples) == 8, "All configurations in capitalization matrix must be unique."
    for item in matrix:
        assert set(item.keys()) == set(CAPITALIZATION_FLAGS)


def test_tabular_matrix_dimensions_and_completeness():
    matrix = generate_tabular_matrix()
    assert len(matrix) == 16, "Tabular matrix must have exactly 16 permutations (2^4)."
    unique_tuples = {tuple(sorted(d.items())) for d in matrix}
    assert len(unique_tuples) == 16, "All configurations in tabular matrix must be unique."
    for item in matrix:
        assert set(item.keys()) == set(TABULAR_FLAGS)


def test_generator_dimensions_and_completeness_unified():
    """
    Unified scenario test verifying all four generators for mathematical completeness
    without randomness or external dependencies.
    """
    generators = [
        (generate_extraction_matrix, 16, EXTRACTION_FLAGS),
        (generate_gcs_matrix, 32, GCS_FLAGS),
        (generate_capitalization_matrix, 8, CAPITALIZATION_FLAGS),
        (generate_tabular_matrix, 16, TABULAR_FLAGS),
    ]
    for gen_fn, expected_count, expected_keys in generators:
        matrix = gen_fn()
        assert len(matrix) == expected_count
        assert len({tuple(sorted(d.items())) for d in matrix}) == expected_count
        for item in matrix:
            assert set(item.keys()) == set(expected_keys)
