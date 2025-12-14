# Project Structure & Organization

## Directory Layout
```
kardenwort/
├── src/kardenwort/core/          # Main application code
│   ├── kardenwort.py             # Core text processing engine
│   └── kardenwort_runner.py      # CLI runner and orchestrator
├── data/                         # Language-specific resources
│   ├── de/                       # German language data
│   │   ├── deu-mixed-typical-2011-1m-words.csv
│   │   ├── german.dic
│   │   └── lemma_override_de.tsv
│   └── en/                       # English language data
│       ├── en-news-2023-1m-words.csv
│       └── lemma_override_en.tsv
├── source_texts/                 # Input text files
│   ├── text1.txt
│   ├── text2.txt
│   └── text3.txt
├── results/                      # Generated TSV/JSON output files
├── tests/                        # Test cases and troubleshooting
│   ├── cases/                    # Organized test scenarios
│   ├── source_texts/de/          # German test texts
│   ├── source_texts/en/          # English test texts
│   └── troubleshooting/          # Jupyter notebooks for debugging
├── scripts/run/cmd/              # Windows batch scripts
├── shortcuts/                    # Windows shortcuts for common tasks
├── docs/                         # Documentation and assets
└── config.ini                   # Environment configuration
```

## Code Organization Patterns

### Core Architecture
- **Single Responsibility**: `kardenwort.py` handles text processing, `kardenwort_runner.py` handles orchestration
- **Configuration-Driven**: All paths and settings managed through `config.ini`
- **Language Separation**: Each language has its own data directory with consistent file naming

### File Naming Conventions
- **Source files**: `text1.txt`, `text2.txt`, `text3.txt` (numbered sequence)
- **Output files**: `YYYYMMDDHHMMSS-{first-words}.{mode}.{type}.{language}.tsv`
- **Language data**: `lemma_override_{language}.tsv`, `{language}-{corpus}-words.csv`
- **Config templates**: `*.template` suffix for template files

### Data File Patterns
- **TSV format**: Tab-separated values for all structured data
- **UTF-8 encoding**: Required for all text files
- **Header rows**: Optional but recommended for TSV files
- **Language codes**: ISO 639-1 codes (`en`, `de`)

## Development Conventions

### Import Organization
```python
# Standard library imports first
import sys
import os
import argparse

# Third-party imports
import spacy
import csv

# Conditional imports with fallbacks
try:
    from german_compound_splitter import comp_split
    GCS_AVAILABLE = True
except ImportError:
    GCS_AVAILABLE = False
```

### Error Handling
- Use `sys.stderr` for error messages and debug output
- Graceful degradation when optional dependencies unavailable
- File existence checks before processing
- Cleanup temporary files with `atexit` handlers

### Configuration Management
- Relative paths supported and calculated from `config.ini` location
- Environment-specific sections in config files
- Fallback values for optional configuration keys
- Path resolution using `pathlib.Path` for cross-platform compatibility

### Testing Structure
- Test cases organized by scenario in `tests/cases/`
- Language-specific test data in separate subdirectories
- Jupyter notebooks for interactive debugging and troubleshooting
- No automated test framework - manual execution and validation

## Integration Points
- **Anki ecosystem**: Designed to work with companion importer and template projects
- **GoldenDict integration**: Command-line interface optimized for external tool integration
- **Windows shortcuts**: Pre-configured shortcuts for common operations
- **Batch scripts**: Windows CMD scripts for streamlined execution