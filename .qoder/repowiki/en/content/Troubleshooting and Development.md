# Troubleshooting and Development

<cite>
**Referenced Files in This Document**   
- [README.md](file://README.md)
- [config.ini](file://config.ini)
- [src/kardenwort/core/kardenwort.py](file://src/kardenwort/core/kardenwort.py)
- [src/kardenwort/core/kardenwort_runner.py](file://src/kardenwort/core/kardenwort_runner.py)
- [data/de/lemma_override_de.tsv](file://data/de/lemma_override_de.tsv)
- [data/en/lemma_override_en.tsv](file://data/en/lemma_override_en.tsv)
- [tests/troubleshooting/test.ipynb](file://tests/troubleshooting/test.ipynb)
- [tests/cases/text3-morgen-faehrt-der-neue/20250913172001-morgen-faehrt-der-neue.triple.sentence.de.tsv](file://tests/cases/text3-morgen-faehrt-der-neue/20250913172001-morgen-faehrt-der-neue.triple.sentence.de.tsv)
</cite>

## Table of Contents
1. [Common Issues and Systematic Debugging](#common-issues-and-systematic-debugging)
2. [Using Jupyter Notebooks for Debugging](#using-jupyter-notebooks-for-debugging)
3. [Analyzing Generated TSV Files](#analyzing-generated-tsv-files)
4. [Using Test Cases for Verification](#using-test-cases-for-verification)
5. [Extending the System](#extending-the-system)
6. [Resources for Further Assistance](#resources-for-further-assistance)

## Common Issues and Systematic Debugging

This section addresses frequent problems encountered when using Kardenwort and provides a structured approach to resolve them. The debugging methodology emphasizes checking log output, verifying file paths, and testing components in isolation.

### Python Environment Setup Errors

A common issue, especially on Windows, is related to the Python version. The README explicitly recommends using **Python 3.9** to avoid compilation issues with dependencies like `spaCy`. Using versions 3.10 or higher may require installing Visual Studio Build Tools. The recommended solution is to install Python 3.9 directly from the Microsoft Store for a hassle-free setup.

The `config.ini` file is crucial for the system's operation. It must be created from the `config.ini.template` file. Key paths in the `[environment]` section, such as `python_executable`, `kardenwort_workspace`, and `importer_workspace`, must point to the correct locations on your system. Relative paths are supported and are calculated from the location of the `config.ini` file, which aids in creating a portable setup.

**Section sources**
- [README.md](file://README.md#L135-L140)
- [config.ini](file://config.ini#L1-L25)

### AnkiConnect Connectivity Issues

Kardenwort relies on the AnkiConnect add-on to import cards into Anki. A frequent cause of failure is that Anki is not running, as AnkiConnect requires the Anki desktop application to be active. Ensure Anki is open before running any Kardenwort scripts.

Furthermore, a specific feature for adding automatic descriptions to Anki decks requires a modified version of AnkiConnect. If you are using the standard AnkiConnect from AnkiWeb, this feature will not work, although all other functionalities will. To use deck descriptions, download and install the modified version from the provided GitHub repository.

**Section sources**
- [README.md](file://README.md#L141-L149)

### spaCy Model Loading Failures

The core functionality of Kardenwort depends on spaCy's language models (`de_core_news_lg` for German and `en_core_web_lg` for English). If these models are not downloaded, the script will fail. After setting up the Python environment, run the following commands to install the models:

```bash
python -m spacy download en_core_web_lg
python -m spacy download de_core_news_lg
```

Failure to download these models will result in an `OSError` when the script attempts to load them. The troubleshooting notebooks in the `tests/troubleshooting/` directory contain code to test the loading of these models, which is a valuable first step in diagnosing this issue.

**Section sources**
- [README.md](file://README.md#L189-L191)
- [tests/troubleshooting/test.ipynb](file://tests/troubleshooting/test.ipynb#L1347-L1450)

### Text Processing Errors

Text processing errors can stem from several sources. The input text must be in UTF-8 encoding. The system uses a hybrid mechanism for sentence splitting: if the input contains newlines, each line is treated as a unit; otherwise, spaCy's sentence tokenizer is used. Ensure your input text is formatted correctly.

A common error occurs when using the pre-configured Windows CMD scripts for multi-line text. These scripts are limited to single-line processing. To process multi-line text (e.g., from GoldenDict), bypass these scripts and call `kardenwort_runner.py` directly with the `--multi-text` flag.

**Section sources**
- [README.md](file://README.md#L286-L299)

## Using Jupyter Notebooks for Debugging

The `tests/troubleshooting/` directory contains a collection of Jupyter notebooks (`.ipynb` files) designed for debugging and experimentation. These notebooks are invaluable tools for isolating and solving problems.

The `test.ipynb` notebook, for example, is dedicated to testing the `german-compound-splitter` library. It contains code to:
1.  Import the `german_compound_splitter` library.
2.  Check for the existence of the `german.dic` dictionary file.
3.  Load the dictionary into an Aho-Corasick automaton.
4.  Perform a deep, recursive split on complex German compound words.

This notebook allows you to experiment with the compound splitting logic independently of the main Kardenwort pipeline. You can modify the `compound_word` variable to test any word and observe how the `dissect` and `merge_fractions` functions work. This is particularly useful for understanding why a specific compound word might not be splitting as expected.

The notebooks are written in a mix of Russian and English comments, but the code itself is in English. They serve as a sandbox for testing individual components, such as spaCy model loading or the manual splitting of words that the library fails to dissect. By running these notebooks, you can verify that each external dependency is functioning correctly before integrating them into the full system.

**Section sources**
- [tests/troubleshooting/test.ipynb](file://tests/troubleshooting/test.ipynb#L1-L800)

## Analyzing Generated TSV Files

The output of Kardenwort is a TSV (Tab-Separated Values) file, which is the primary artifact for debugging text processing issues. These files are located in the `results/` directory and are not automatically deleted, allowing for persistent analysis.

To identify lemmatization or formatting issues, open the TSV file in a spreadsheet application or a text editor with good tabular support. Key columns to inspect include:
- `WordSource`: The lemma (base form) of the word as determined by the system.
- `WordSourceInflectedForm`: The original, inflected form of the word as it appeared in the source text.
- `SentenceSource`: The full sentence from which the word was extracted, providing context.
- `SentenceSourceWordlist`: A list of all unique words found in the source sentence.

By comparing the `WordSource` and `WordSourceInflectedForm`, you can identify incorrect lemmatization. For example, if the inflected form is "Kapitäns" (genitive case) and the lemma is "Kapitäns" instead of "Kapitän", this indicates a failure in the genitive correction logic. The surrounding context in `SentenceSource` helps determine if the error is due to a specific grammatical construction.

The structure of the TSV file, with its 82 columns, is designed for the Anki card template. Fields are dynamically populated, meaning they only appear if they contain data. This can be used to verify if certain features, like TTS fields or morpheme analysis, are being generated as expected.

**Section sources**
- [README.md](file://README.md#L274-L275)
- [src/kardenwort/core/kardenwort.py](file://src/kardenwort/core/kardenwort.py#L320-L404)
- [tests/cases/text3-morgen-faehrt-der-neue/20250913172001-morgen-faehrt-der-neue.triple.sentence.de.tsv](file://tests/cases/text3-morgen-faehrt-der-neue/20250913172001-morgen-faehrt-der-neue.triple.sentence.de.tsv#L1-L3)

## Using Test Cases for Verification

The `tests/cases/` directory contains predefined test cases that can be used to verify the system's behavior. Each subdirectory represents a specific text input, and within it, there are TSV files that are the expected output from running Kardenwort with various configurations.

For instance, the `text3-morgen-faehrt-der-neue` directory contains a TSV file generated from the sentence "Morgen fährt der neue Donaudampfschifffahrtsgesellschaftskapitän mit seinem Boot donauabwärts ab." This case is ideal for testing German compound splitting accuracy. You can run Kardenwort on this text and compare your output to the provided TSV file to ensure that complex words like "Donaudampfschifffahrtsgesellschaftskapitän" are being split and lemmatized correctly.

These test cases serve as a regression suite. After making any changes to the codebase or configuration, re-running these tests ensures that existing functionality has not been broken. They provide a concrete benchmark for the expected output, making it easier to identify and fix regressions.

**Section sources**
- [tests/cases/text3-morgen-faehrt-der-neue/20250913172001-morgen-faehrt-der-neue.triple.sentence.de.tsv](file://tests/cases/text3-morgen-faehrt-der-neue/20250913172001-morgen-faehrt-der-neue.triple.sentence.de.tsv#L1-L3)

## Extending the System

Kardenwort is designed to be extensible. This section provides guidance for developers on how to add new features or modify the processing pipeline.

### Adding Support for New Languages

To add support for a new language, several components must be addressed:
1.  **spaCy Model**: A spaCy language model must be available for the new language.
2.  **Lemma Override File**: Create a new TSV file in the `data/` directory (e.g., `lemma_override_es.tsv` for Spanish) to allow user training.
3.  **Configuration**: Add the new language's data file paths to the `[language_resources]` section of `config.ini`.
4.  **Code Logic**: The core processing logic in `kardenwort.py` may need modifications to handle language-specific rules, such as compound splitting or genitive case correction.

### Modifying the Processing Pipeline

The processing pipeline is defined in the `extract_lemmas_from_sentence` function in `kardenwort.py`. This function controls the flow of text through tokenization, lemmatization, German compound splitting (GCS), and user override rules.

Key areas for modification include:
- **German Compound Splitting Accuracy**: The accuracy of GCS can be tuned using arguments like `--de-gcs-split-mode` (e.g., `combined`) and `--de-gcs-pos-tags`. The system uses the `german-compound-splitter` library, and its performance is heavily dependent on the quality of the `german.dic` dictionary.
- **Lemma Override Rule Effectiveness**: The `load_lemma_override_rules` function processes the `lemma_override.tsv` file. The rules are applied in three priority levels, allowing for context-aware corrections. To improve effectiveness, ensure that the rules are correctly formatted and that the context conditions (e.g., `regex:` patterns) are accurate.

Developers can experiment with the pipeline by modifying the function's logic and using the Jupyter notebooks to test changes in isolation before integrating them into the main codebase.

**Section sources**
- [src/kardenwort/core/kardenwort.py](file://src/kardenwort/core/kardenwort.py#L476-L592)
- [data/de/lemma_override_de.tsv](file://data/de/lemma_override_de.tsv)
- [data/en/lemma_override_en.tsv](file://data/en/lemma_override_en.tsv)

## Resources for Further Assistance

For further assistance, the following resources are available:
- **Development Repositories**: The active development of Kardenwort takes place in dedicated repositories. These contain the latest updates and feature branches before they are merged into the stable public releases.
- **Community Support**: The project's ecosystem is designed to be open and collaborative. Users are encouraged to explore the development repositories and contribute to the project.
- **Documentation**: The `README.md` file is the primary source of documentation, containing detailed installation instructions, usage examples, and explanations of key features and advantages.

**Section sources**
- [README.md](file://README.md#L451-L470)