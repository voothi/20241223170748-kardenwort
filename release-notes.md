# Release Notes

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
