# Technology Stack

## Core Technologies
- **Python 3.9**: Strongly recommended version to avoid C++ compiler requirements on Windows
- **spaCy**: Primary NLP library for tokenization, lemmatization, and language processing
- **German Compound Splitter**: Specialized library for German compound word decomposition
- **Anki Desktop + AnkiConnect**: Target platform for flashcard import and management

## Key Dependencies
- `spacy` with language models: `en_core_web_lg`, `de_core_news_lg`
- `german_compound_splitter` (from GitHub fork)
- Standard Python libraries: `csv`, `argparse`, `configparser`, `pathlib`
- Windows-specific: `winsound` for completion notifications

## Project Structure
- **Configuration-driven**: Uses `config.ini` for environment and path management
- **Modular architecture**: Core processing (`kardenwort.py`) + Runner (`kardenwort_runner.py`)
- **Language-specific data**: Separate directories for English and German resources
- **TSV output format**: Tab-separated values for Anki import compatibility

## Build & Development Commands

### Environment Setup
```bash
# Create virtual environment (recommended location: parent directory)
python -m venv ../kardenwort-spacy-env

# Activate environment
# Windows PowerShell:
../kardenwort-spacy-env/Scripts/Activate.ps1
# Linux/macOS:
source ../kardenwort-spacy-env/bin/activate

# Install dependencies
pip install -r requirements.txt

# Download spaCy language models
python -m spacy download en_core_web_lg
python -m spacy download de_core_news_lg
```

### Configuration
```bash
# Copy template and configure paths
cp config.ini.template config.ini
# Edit config.ini to set correct paths for your system
```

### Running the Application
```bash
# Basic vocabulary extraction (German)
python src/kardenwort/core/kardenwort_runner.py --type word --mode single --language de

# Sentence cards with dual text files
python src/kardenwort/core/kardenwort_runner.py --type sentence --mode dual --language en

# Mixed mode with hierarchical decks
python src/kardenwort/core/kardenwort_runner.py --mode mixed-triple --language de --anki-markdown-decks --suspend-cards
```

### Testing
- Test cases located in `tests/cases/` with language-specific subdirectories
- Troubleshooting notebooks in `tests/troubleshooting/`
- No automated test runner - manual execution of test scenarios

## File Formats & Conventions
- **Input**: UTF-8 encoded `.txt` files
- **Output**: TSV files with 82-column format + optional JSON metadata
- **Configuration**: INI format with relative path support
- **Override files**: TSV format for lemma corrections (`lemma_override_*.tsv`)
- **Language data**: CSV frequency files and dictionary files per language