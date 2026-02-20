# Release Notes

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
