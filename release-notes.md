# Release Notes

## [v2.0.4] - 2026-03-04

### Added
- **Smoke Tests**: Introduced a new suite of fast, high-level sanity checks (`test_smoke.py`) for basic script operability and quick text extraction verification.

### Changed
- **Comprehensive Test Suite Refactoring**: Migrated existing `unittest` tests to `pytest`, utilizing fixtures and parameterization for improved maintainability.
- **Deep Integration Verification**: Refactored integration tests to dynamically discover test cases and perform bit-for-bit TSV/JSON verification (normalized for timestamps). Includes strict validation of field order (`WordSource` index 1, `SentenceSource` index 9) and frequency-based sorting in `SentenceSourceWordlist`.
- **Test Restructuring**: Reorganized the `tests/` directory hierarchy into distinct `unit`, `integration`, and `smoke` subdirectories, making the codebase easier to navigate.

### Fixed
- **Runner Argument Precedence**: Fixed a bug in `kardenwort_runner.py` where command-line arguments for input files were being ignored in favor of `config.ini` defaults.
- **Core Unit Test Coverage**: Added rigorous unit testing around core lexical logic (`kardenwort.py`), including the `extract_lemmas_from_sentence` function, error pathways, and exception handling. Increased direct unit coverage of the core linguistic processing file by ~5x.
- **Integration Test Robustness**: Removed brittle hardcoded column index checks in integration tests and instead implemented dynamic evaluation driven by `config.ini`.

## [v2.0.0] - 2026-03-03

### Added
- **Configuration Migration**: Migrated legacy command-line arguments (`--wordlist-use-br`, `--add-header`) to `config.ini` for better maintainability. CLI arguments now act as overrides for centralized defaults.
- **Automated Extraction Logic**: Refactored the core engine to automatically detect and enable extraction logic (e.g., wordlist generation, sentence indexing, inflected form capture) based on the `anki_field_mapping` in `config.ini`.
- **Baseline Integration Tests**: Developed an automated integration test suite (`tests/test_integration.py`) to verify multi-language `mixed-triple` mode extraction against `tests/source_texts/`.
- **Improved Runner Coordination**: Updated `kardenwort_runner.py` to synchronize configuration across the entire pipeline, ensuring seamless data flow from text to Anki.

### Changed
- **Repository Hygiene**: Deleted obsolete and redundant directories `.kiro`, `.qoder`, and `./a` (archive).
- **Environment Safety**: Finalized `.gitignore` patterns and removed `config.ini` from the Git cache to prevent leaking local environment paths while preserving `config.ini.template`.

### Fixed
- **Configuration Consistency**: Resolved internal discrepancies between command-line argument parsers and configuration file readers, establishing a strict and predictable parameter priority.

## [v1.52.2] - 2026-02-21

### Added
- **Simplified Anki Field Configuration**: You can now define Anki fields in `config.ini` as a simple unnumbered list. The system automatically handles order based on line position.
- **Improved Field Parser**: Updated `kardenwort_runner.py` to support value-less keys in `[anki_fields]`, making it easier to reorder or add fields without manual re-numbering.

### Fixed
- **Restored GoldenDict Integration**: Fixed a regression in `kardenwort.py` where Anki headers were strictly required even for STDOUT output modes. Direct queries for lemmas (HTML/TSV/List) now work correctly without additional arguments.
- **Robustness**: Ensured `kardenwort.py` only enforces strict Anki configuration when an output file is explicitly requested.


## [v1.50.2] - 2026-02-21

### Added
- **Strict Configuration Enforcement**: The script now strictly validates that Anki-related configuration sections (`[anki_fields]`, `[anki_field_mapping.*]`) are present in `config.ini`, preventing accidental misconfigurations.
- **Improved Field Population**: Refactored the internal data pipeline (`prepare_row_data`) to ensure all context and translation fields are captured and available for mapping in both word and sentence modes.
- **Enhanced Documentation**: Updated `config.ini.template` with comprehensive documentation for all available data sources and example mappings.

### Fixed
- **Missing Translations Regression**: Restored translation and context fields in word extraction mode that were missing in the initial refactor.
- **NameError Fixes**: Resolved several `NameError` exceptions related to `sentence_lemmas_cache` and `context_end_index`.
- **Anki Importer Warnings**: Ensured `Quotation` fields are always populated in sentence mode to prevent importer warnings about empty identity fields.


## [v1.48.2] - 2026-02-20

### Added
- **Flexible Field Mapping**: Users can now map any Anki field name to internal data sources via `config.ini` using `[anki_field_mapping.word]` and `[anki_field_mapping.sentence]` sections.
- **Automated Testing Suite**: Introduced a comprehensive unit testing framework in `tests/` with initial coverage for core mapping logic.
- **New Fields**: Added `WordSourceAI` and `WordSourceInflectedFormAI` to the default Anki CSV header.

### Changed
- **Internal Refactor**: Transitioned from hard-coded column indices to a robust name-based lookup system for CSV generation.
- **Improved Config Handling**: The runner now preserves casing in configuration keys to support case-sensitive Anki field names.

### Fixed
- **Import Error**: Fixed a broken import in `src/kardenwort/__init__.py` that prevented the project from being used as a standard Python package.
- **Indentation Bug**: Fixed a logic error in `kardenwort.py`'s `main()` function that affected `mixed-triple` mode processing.

## [v1.46.2] - 2026-02-14

### Added
- **Anki CSV Export Enhancement**: Added `WordDestinationInflectedForm` field (Column 83) to support advanced destination highlighting in Anki templates.
- **Sync with Templates**: Full compatibility with Kardenwort Anki Templates v1.46.2 highlighting logic.

### Changed
- **CSV Row Logic**: Updated internal row generation to support the expanded 83-column format.
