import pytest
import argparse
from dataclasses import FrozenInstanceError
from kardenwort.core.kardenwort import (
    ExtractionConfig,
    ExecutionStrategyConfig,
    GCSConfig,
    AnkiMappingConfig,
    ExecutionContext
)

def test_3_2_extraction_config_round_trip_265_args():
    """Verify ExtractionConfig.from_args round-trip fidelity across 265 properties."""
    simulated_args = {f"arg_property_{i}": f"val_{i}" for i in range(265)}
    simulated_args["language"] = "de"
    simulated_args["output_format"] = "anki-tsv"
    simulated_args["de_force_noun_capitalization"] = True

    mock_namespace = argparse.Namespace(**simulated_args)
    config = ExtractionConfig.from_args(mock_namespace)

    for k, v in simulated_args.items():
        assert getattr(config, k) == v

    with pytest.raises(FrozenInstanceError):
        config.language = "en"


def test_3_2_anki_mapping_config_90_field_baseline():
    """Verify AnkiMappingConfig loads the 90-field baseline intact."""
    config = AnkiMappingConfig()
    assert len(config.header) == 90
    assert "Quotation" in config.header
    assert "WordSource2" in config.header
    assert "ClassificationOxford" in config.header

    with pytest.raises(FrozenInstanceError):
        config.header = ("Changed",)


def test_3_2_gcs_config_immutability_and_factories():
    """Verify GCSConfig factory constructors and immutability."""
    gcs = GCSConfig.from_kwargs(de_gcs=True, de_gcs_part_singularization="all")
    assert gcs.de_gcs is True
    assert gcs.de_gcs_part_singularization == "all"
    with pytest.raises(FrozenInstanceError):
        gcs.de_gcs = False


def test_5_5_translation_layer_orchestration_contract():
    """Simulate raw kardenwort_runner.py input and assert all 265 properties correctly map onto ExecutionStrategyConfig."""
    raw_inputs = {f"cli_flag_{j}": j for j in range(265)}
    raw_inputs["type"] = "word"
    raw_inputs["apostrophe_chars"] = "'"
    
    mock_runner_namespace = argparse.Namespace(**raw_inputs)
    strategy_config = ExecutionStrategyConfig.from_args(mock_runner_namespace)
    
    assert isinstance(strategy_config, ExtractionConfig)
    for k, v in raw_inputs.items():
        assert getattr(strategy_config, k) == v
