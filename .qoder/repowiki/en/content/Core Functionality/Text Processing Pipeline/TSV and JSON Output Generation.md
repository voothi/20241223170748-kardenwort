# TSV and JSON Output Generation

<cite>
**Referenced Files in This Document**   
- [kardenwort.py](file://src/kardenwort/core/kardenwort.py)
- [kardenwort_runner.py](file://src/kardenwort/core/kardenwort_runner.py)
- [README.md](file://README.md)
- [config.ini.template](file://config.ini.template)
- [20250913163607-die-fischer-kennen-die.single.word.de.tsv](file://tests/cases/text-die-fischer-kennen-die/kardenwort_run_de_w_t_l_anki.cmd/20250913163607-die-fischer-kennen-die.single.word.de.tsv)
- [20250913162418-digitale-bilddaten-und-audiodaten.single.word.de.tsv](file://tests/cases/text-digitale-bilddaten-und-audiodaten/kardenwort_run_de_w_t_l_anki.cmd/20250913162418-digitale-bilddaten-und-audiodaten.single.word.de.tsv)
- [20250913172001-morgen-faehrt-der-neue.triple.sentence.de.tsv](file://tests/cases/text3-morgen-faehrt-der-neue/20250913172001-morgen-faehrt-der-neue.triple.sentence.de.tsv)
</cite>

## Table of Contents
1. [Introduction](#introduction)
2. [82-Column TSV Output Structure](#82-column-tsv-output-structure)
3. [Dynamic Filename Generation](#dynamic-filename-generation)
4. [JSON Metadata Generation for Anki Decks](#json-metadata-generation-for-anki-decks)
5. [Key Functions: get_anki_csv_header and _write_deck_metadata](#key-functions-get_anki_csv_header-and-_write_deck_metadata)
6. [Practical Examples of Generated Files](#practical-examples-of-generated-files)
7. [Common Issues and Troubleshooting](#common-issues-and-troubleshooting)
8. [Best Practices for Customization and Integration](#best-practices-for-customization-and-integration)
9. [Conclusion](#conclusion)

## Introduction
Kardenwort is a powerful command-line utility designed to transform text into structured vocabulary and sentence flashcards for Anki. A core aspect of its functionality is the generation of two complementary output files: a richly-structured 82-column TSV (Tab-Separated Values) file and an optional JSON metadata file. The TSV file contains all the data for individual flashcards, while the JSON file provides descriptive content for Anki decks. This document details the structure, generation, and usage of these outputs, focusing on the dynamic filename system, the role of key functions, and best practices for integration.

**Section sources**
- [README.md](file://README.md#L11-L14)

## 82-Column TSV Output Structure
The primary output of Kardenwort is an 82-column TSV file, meticulously designed to work with a feature-rich Anki card template. Each row in the TSV represents a single flashcard, and the columns are populated with various types of linguistic and contextual data.

The structure is defined by the `get_anki_csv_header` function in `kardenwort.py`. The first 40 columns are dedicated to core card content such as the `Quotation`, `WordSource` (the lemma), `WordSourceInflectedForm` (the original word form), `SentenceSource` (the full sentence), and `SentenceSourceWordlist` (a list of lemmas from the sentence). Columns 41-80 are reserved for TTS (Text-to-Speech) audio fields and deck assignment. The final column, `Deck` (index 81), is used for dynamic deck assignment in Anki.

A critical feature of the TSV structure is the TTS audio field system. The `TTS_FIELD_INDICES` dictionary maps language codes to specific column indices:
- **Source Language TTS**: Columns 59-63 are for the source language (e.g., `en` at index 59, `de` at index 61).
- **Destination Language TTS**: Columns 64-68 are for the destination language (e.g., `en` at index 64, `de` at index 66).

When the `--tts-destination-lang` argument is provided, the script sets the value "1" in the corresponding source and destination TTS columns. This acts as a flag for the Anki template to automatically generate or play audio for that card. For example, if `--tts-destination-lang de` is used, column 61 (`Source-de-DE`) and column 66 (`Destination-de-DE`) will be set to "1" for relevant cards.

**Section sources**
- [kardenwort.py](file://src/kardenwort/core/kardenwort.py#L320-L404)
- [kardenwort.py](file://src/kardenwort/core/kardenwort.py#L51-L50)
- [kardenwort.py](file://src/kardenwort/core/kardenwort.py#L1030-L1039)
- [kardenwort.py](file://src/kardenwort/core/kardenwort.py#L1439-L1448)

## Dynamic Filename Generation
Kardenwort employs a sophisticated system for generating output filenames, combining timestamps, input text content, and processing mode to create unique and descriptive file names. This process is controlled by command-line arguments and the `generate_filename_prefix_from_text` function.

The base filename is determined by the `output_template` configuration in `config.ini`, which by default is `result.{mode}.{suffix}.{language}.tsv`. The `{mode}` placeholder is replaced with the processing mode (e.g., `single`, `triple`), `{suffix}` with `word` or `sentence`, and `{language}` with the source language code (e.g., `de`).

The dynamic elements are added as a prefix to this base name:
1.  **Timestamp**: If `--basename-add-timestamp` is used, a timestamp in the format `YYYYMMDDHHMMSS-` is prepended.
2.  **Text Slug**: If `--basename-add-first-words` is used, a slug is generated from the first few words of the input text. The `generate_filename_prefix_from_text` function processes the text by converting it to lowercase, replacing German umlauts (`ä`, `ö`, `ü`) with their digraphs (`ae`, `oe`, `ue`), and replacing `ß` with `ss`. It then extracts the first `N` alphanumeric words (default is 4) and joins them with hyphens. For example, the text "Die Fischer kennen die Austernbanken" would generate the slug `die-fischer-kennen-die`.

The final filename is constructed by combining these elements. For instance, processing a German text in single-word mode with both timestamp and text slug options would result in a filename like `20250913163607-die-fischer-kennen-die.single.word.de.tsv`.

**Section sources**
- [kardenwort.py](file://src/kardenwort/core/kardenwort.py#L406-L415)
- [kardenwort_runner.py](file://src/kardenwort/core/kardenwort_runner.py#L138-L145)
- [kardenwort.py](file://src/kardenwort/core/kardenwort.py#L1924-L1940)

## JSON Metadata Generation for Anki Decks
When the `--anki-deck-content` argument is used, Kardenwort generates a companion JSON file alongside the TSV output. This JSON file contains descriptive content that is automatically populated into the Anki deck's description field, providing valuable context for the user.

The content of the JSON file is controlled by the values passed to `--anki-deck-content`, which can include:
- `parent-source`: Adds the full source text to the parent deck's description.
- `parent-translations`: Adds the full translation texts to the parent deck's description.
- `subdeck-source`: Adds the source text lines to individual subdeck descriptions.
- `subdeck-translations`: Adds the translation text lines to individual subdeck descriptions.

The `_write_deck_metadata` function is responsible for creating this JSON file. It first determines the parent deck name based on the output filename, processing mode, and `--anki-parent-deck` argument. It then constructs a `deck_descriptions` dictionary. For the parent deck, it combines the source and/or translation texts, separated by `---`. For subdecks (created via `--anki-markdown-decks`), it combines the relevant text lines for each subdeck. The final JSON structure is a simple object with a single key, `deck_descriptions`, which maps deck names to their respective description strings.

**Section sources**
- [kardenwort.py](file://src/kardenwort/core/kardenwort.py#L594-L671)
- [README.md](file://README.md#L73-L74)

## Key Functions: get_anki_csv_header and _write_deck_metadata
Two key functions in `kardenwort.py` are central to the output generation process.

The `get_anki_csv_header` function returns a list of 82 string values, each representing the column name for the TSV output. This list is used as the header row when the TSV file is written if the `--add-header` flag is present. The order and names of these fields are critical for the Anki import process and the card template to function correctly. This function serves as the single source of truth for the TSV schema.

The `_write_deck_metadata` function handles the creation of the JSON metadata file. It takes the command-line arguments, paths, and text content as input. It performs several key tasks:
1.  **Deck Name Resolution**: It determines the correct parent and subdeck names based on the processing mode and arguments.
2.  **Content Aggregation**: It collects the source and translation texts and organizes them according to the `--anki-deck-content` settings.
3.  **JSON Serialization**: It constructs the final JSON object and writes it to a file with the same base name as the TSV file but with a `.json` extension, using UTF-8 encoding to support all characters.

These functions encapsulate the logic for structured output, ensuring consistency and reliability across different runs and configurations.

**Section sources**
- [kardenwort.py](file://src/kardenwort/core/kardenwort.py#L320-L404)
- [kardenwort.py](file://src/kardenwort/core/kardenwort.py#L594-L671)

## Practical Examples of Generated Files
The repository's test cases provide concrete examples of the generated output.

An example of a **word-type TSV file** (`20250913163607-die-fischer-kennen-die.single.word.de.tsv`) contains one row per unique lemma extracted from the input text. Each row has the `Quotation` field populated with the lemma, the `WordSourceInflectedForm` with the original word form, and the `SentenceSource` with the full sentence where the word was found. The `SentenceSourceWordlist` field contains a `<br>`-separated list of all lemmas from that sentence.

An example of a **sentence-type TSV file** (`20250913172001-morgen-faehrt-der-neue.triple.sentence.de.tsv`) contains one row per sentence. The `Quotation` field is empty, and the `SentenceSource` field contains the full sentence. The `SentenceSourceWordlist` field is populated with the lemmas from that sentence.

A corresponding **JSON metadata file** (e.g., `20250913163607-die-fischer-kennen-die.single.word.de.json`) would contain a structure like:
```json
{
  "deck_descriptions": {
    "die-fischer-kennen-die": "Die Fischer kennen die Austernbanken vor der Küste sehr gut und fahren sie gezielt an."
  }
}
```
This JSON file would be generated if `--anki-deck-content parent-source` was used, placing the source text in the description of the parent deck named after the filename.

**Section sources**
- [20250913163607-die-fischer-kennen-die.single.word.de.tsv](file://tests/cases/text-die-fischer-kennen-die/kardenwort_run_de_w_t_l_anki.cmd/20250913163607-die-fischer-kennen-die.single.word.de.tsv)
- [20250913162418-digitale-bilddaten-und-audiodaten.single.word.de.tsv](file://tests/cases/text-digitale-bilddaten-und-audiodaten/kardenwort_run_de_w_t_l_anki.cmd/20250913162418-digitale-bilddaten-und-audiodaten.single.word.de.tsv)
- [20250913172001-morgen-faehrt-der-neue.triple.sentence.de.tsv](file://tests/cases/text3-morgen-faehrt-der-neue/20250913172001-morgen-faehrt-der-neue.triple.sentence.de.tsv)

## Common Issues and Troubleshooting
Several common issues can arise during output generation:

*   **File Encoding Errors**: The system relies on UTF-8 encoding for both input and output. Using a different encoding (e.g., ANSI or UTF-16) can result in garbled text or import failures. Always ensure input text files are saved in UTF-8 format.
*   **Path Resolution Failures**: Incorrect paths in `config.ini` for `kardenwort_workspace` or `importer_workspace` can prevent the runner script from finding the necessary files. Verify that all paths in the configuration are correct and use absolute paths if relative paths are causing issues.
*   **Metadata Formatting Errors**: The `_write_deck_metadata` function may fail to write the JSON file if the output directory does not exist or if there are permission issues. The script will print a warning to stderr in such cases. Ensure the `results` directory exists and is writable.
*   **Missing TTS Fields**: If the `--tts-destination-lang` argument specifies a language code not present in the `TTS_FIELD_INDICES` dictionary (e.g., a typo like `du` instead of `de`), a warning will be printed, and the TTS fields will not be activated. Double-check the language code against the dictionary.
*   **Empty Output Files**: This can occur if the input text is empty, contains no valid words, or if there is a critical error during processing. Check the stderr output for any error messages from the script.

**Section sources**
- [kardenwort.py](file://src/kardenwort/core/kardenwort.py#L667-L670)
- [kardenwort.py](file://src/kardenwort/core/kardenwort.py#L1034-L1040)
- [README.md](file://README.md#L429-L430)

## Best Practices for Customization and Integration
To effectively customize and integrate Kardenwort's output:

1.  **Customize the Output Template**: Modify the `output_template` in `config.ini` to change the default naming scheme. For example, using `{language}.{mode}` as a prefix can help organize files by language.
2.  **Control Filename Length**: Use `--basename-add-first-words N` with a smaller `N` (e.g., 2 or 3) to keep filenames short, especially for long texts.
3.  **Leverage Deck Descriptions**: Use `--anki-deck-content parent-source` to automatically archive the source material within Anki, making it easy to review the original context later.
4.  **Integrate with Downstream Tools**: The predictable TSV structure makes it easy to write scripts that post-process the output. For example, a script could extract all `WordSource` values to create a simple word list, or parse the JSON metadata to generate a table of contents for a study guide.
5.  **Ensure AnkiConnect Compatibility**: Remember that the `--anki-deck-content` feature requires a specific, modified version of the AnkiConnect add-on. Using the standard version will result in the deck descriptions not being updated, even though the JSON file is generated.

**Section sources**
- [config.ini.template](file://config.ini.template)
- [README.md](file://README.md#L143-L149)

## Conclusion
Kardenwort's TSV and JSON output generation system is a robust and flexible mechanism for creating structured language learning data. The 82-column TSV provides a comprehensive data model for flashcards, with a well-defined system for TTS audio activation. The dynamic filename generation ensures unique and informative file names, while the companion JSON metadata enriches Anki decks with contextual information. By understanding the roles of key functions like `get_anki_csv_header` and `_write_deck_metadata`, and following best practices for customization, users can fully leverage this system to create highly effective and personalized study materials.