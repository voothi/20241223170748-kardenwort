# Core Functionality

<cite>
**Referenced Files in This Document**   
- [kardenwort_runner.py](file://src/kardenwort/core/kardenwort_runner.py)
- [kardenwort.py](file://src/kardenwort/core/kardenwort.py)
- [README.md](file://README.md)
- [config.ini](file://config.ini)
- [lemma_override_de.tsv.template](file://data/de/lemma_override_de.tsv.template)
- [text1.txt](file://tests/source_texts/de/text1.txt)
- [text2.txt](file://tests/source_texts/de/text2.txt)
- [text3.txt](file://tests/source_texts/de/text3.txt)
- [kardenwort-goldendict-config.txt](file://docs/kardenwort-goldendict-config.txt)
</cite>

## Table of Contents
1. [Introduction](#introduction)
2. [Core Processing Modes](#core-processing-modes)
3. [Hybrid Sentence Splitting Mechanism](#hybrid-sentence-splitting-mechanism)
4. [Text Processing Pipeline](#text-processing-pipeline)
5. [The kardenwort_runner.py Script](#the-kardenwort_runnerpy-script)
6. [Practical Examples](#practical-examples)
7. [Common Issues and Best Practices](#common-issues-and-best-practices)

## Introduction
Kardenwort is an intelligent command-line utility designed to automate the creation of context-rich flashcards for Anki from plain text. Its core functionality revolves around a sophisticated text processing pipeline that deconstructs language, extracts meaningful vocabulary, and structures the output for optimal language learning. This document details the two primary processing modes, the hybrid sentence splitting mechanism, the complete processing pipeline, and the role of the `kardenwort_runner.py` script in orchestrating the workflow.

**Section sources**
- [README.md](file://README.md#L11-L13)

## Core Processing Modes
Kardenwort operates in two distinct modes, each designed for a specific type of language learning card: **vocabulary cards** (word mode) and **contextual cards** (sentence mode). The mode is selected using the `--type` command-line argument.

### Word Extraction Mode (Vocabulary Cards)
The `--type word` mode is designed to create flashcards for studying individual words. Its primary goal is to extract a comprehensive list of unique lemmas (base word forms) from the input text.

**Mechanism:**
1.  The entire input text is analyzed as a single corpus.
2.  The text is tokenized into individual words.
3.  Each token undergoes lemmatization using the spaCy NLP library.
4.  Advanced language-specific processing is applied, such as German Compound Splitting (GCS) to deconstruct long compound words.
5.  The resulting lemmas are deduplicated based on the `--deduplication-scope` setting (global, sentence, or none).
6.  The final list of unique lemmas is sorted, with known words (from a frequency index) appearing before unknown words.
7.  A single row is created for each unique lemma in the output TSV file, containing the lemma, its inflected form, and its original sentence context.

This mode is ideal for building a focused vocabulary list from a chapter of a book or an article, allowing the user to study the core words in isolation with their surrounding context.

**Section sources**
- [README.md](file://README.md#L266-L270)
- [kardenwort.py](file://src/kardenwort/core/kardenwort.py#L476-L592)

### Sentence Processing Mode (Contextual Cards)
The `--type sentence` mode is designed to create flashcards for studying full sentences, phrases, and grammar in context. Its primary goal is to preserve the original structure of the text.

**Mechanism:**
1.  The input text is processed line-by-line. Each non-empty line is treated as a separate unit.
2.  For each line, a single record is created in the output TSV file.
3.  If parallel texts are provided (e.g., source text, translation, and a second translation), the corresponding lines from each file are combined into the same record.
4.  The entire line becomes the `SentenceSource` field on the Anki card.
5.  The surrounding sentences (as defined by `--sentence-context-size`) are added as context.
6.  A list of all unique lemmas found in the source sentence can be included in the `SentenceSourceWordlist` field.

This mode is ideal for studying dialogues, subtitles, or any text where the full sentence structure and its translation are the primary focus.

**Section sources**
- [README.md](file://README.md#L271-L274)
- [kardenwort.py](file://src/kardenwort/core/kardenwort.py#L672-L800)

## Hybrid Sentence Splitting Mechanism
A critical feature of Kardenwort is its ability to automatically determine how to split text into processing units. This hybrid mechanism intelligently chooses between line-by-line processing and grammatical sentence tokenization based on the input format.

### Mechanism
The decision is made based on the presence of newline characters (`\n`) in the input text:
1.  **Line-by-Line Mode:** If the input text contains at least one newline character, Kardenwort treats each line as a complete, independent unit. This is the default behavior for multi-line input files.
2.  **Sentence Tokenization Mode:** If the input text is a single block of text without any newlines, Kardenwort uses the spaCy NLP library's built-in sentence tokenizer to split the text into grammatically correct sentences.

This mechanism ensures that pre-formatted text (like subtitles or parallel texts in separate lines) is processed correctly, while continuous prose from a book or article is split into meaningful sentences for study.

**Section sources**
- [README.md](file://README.md#L286-L291)
- [kardenwort.py](file://src/kardenwort/core/kardenwort.py#L687-L714)

## Text Processing Pipeline
The text processing pipeline is a multi-stage process that transforms raw text into structured data for Anki. The `kardenwort.py` script handles the core stages of this pipeline.

### Stage 1: Initialization
The pipeline begins by loading all necessary resources:
*   **spaCy Models:** The appropriate language model (e.g., `de_core_news_lg` for German) is loaded for tokenization, lemmatization, and part-of-speech tagging.
*   **Dictionaries:** A custom dictionary (e.g., `german.dic`) is loaded to validate the components of split German compound words.
*   **Lemma Override Rules:** The `lemma_override_de.tsv` file is parsed to create a set of user-defined rules for correcting lemmatization errors.
*   **Frequency Index:** A CSV file containing a ranked list of words is loaded to sort lemmas, placing known words before unknown ones.

**Section sources**
- [README.md](file://README.md#L304-L305)
- [kardenwort.py](file://src/kardenwort/core/kardenwort.py#L295-L310)

### Stage 2: Text Ingestion
Text can be ingested from various sources:
*   **Files:** The primary method, using arguments like `--text1-file`, `--text2-file`, and `--text3-file`.
*   **Direct Input:** A text string can be passed directly using the `--text` argument.
*   **Environment Variables:** Text can be provided via the `KARDENWORT_INPUT_TEXT` environment variable.
*   **Standard Input (stdin):** Text can be piped into the script.

The input files must be plain text with UTF-8 encoding. For parallel texts, strict line-by-line correspondence is required.

**Section sources**
- [README.md](file://README.md#L283-L284)
- [kardenwort.py](file://src/kardenwort/core/kardenwort.py#L311-L319)

### Stage 3: Tokenization and Lemmatization with German Compound Splitting
This is the core linguistic analysis stage:
1.  **Tokenization:** The text is split into tokens (words, punctuation).
2.  **Lemmatization:** spaCy converts each token to its base form (lemma).
3.  **German Compound Splitting (GCS):** For German text, if enabled (`--de-gcs`), long compound words are split into their constituent parts using the `german-compound-splitter` library. Each part is then lemmatized and validated against the dictionary.
4.  **Separable Verb Handling:** German verbs with separable prefixes (e.g., "anfangen") are correctly identified and processed.
5.  **Lemma Override Application:** The system applies the user-defined rules from `lemma_override.tsv` to correct any lemmatization errors based on the word and its context.

**Section sources**
- [README.md](file://README.md#L306-L307)
- [kardenwort.py](file://src/kardenwort/core/kardenwort.py#L476-L584)

### Stage 4: Collection and Sorting of Unique Lemmas
After processing each sentence or the entire text:
1.  **Deduplication:** Lemmas are collected and deduplicated based on the `--deduplication-scope` setting.
2.  **Sorting:** The final list of lemmas is sorted. The primary sort key is whether the lemma is present in the frequency index file. Lemmas in the index are listed first, followed by unknown lemmas, both in alphabetical order.

**Section sources**
- [README.md](file://README.md#L307-L308)
- [kardenwort.py](file://src/kardenwort/core/kardenwort.py#L588-L592)

### Stage 5: TSV and JSON Metadata Generation
The processed data is formatted for Anki:
1.  **TSV Generation:** A tab-separated values (TSV) file is created with a predefined 82-column structure. This includes fields for the word, sentence, context, audio, and various metadata.
2.  **JSON Metadata Generation:** If the `--anki-deck-content` argument is used, a companion `.json` file is generated. This file contains descriptions for Anki decks, populated with the full source text and translations, providing rich context within the Anki interface.

**Section sources**
- [README.md](file://README.md#L308-L309)
- [kardenwort.py](file://src/kardenwort/core/kardenwort.py#L660-L671)

### Stage 6: Anki Import Orchestration
The final stage is handled by the `kardenwort_runner.py` script, which acts as an orchestrator:
1.  It calls the `kardenwort.py` script to generate the TSV and JSON files.
2.  It then calls the `anki-csv-importer.py` script, passing the paths to the generated files.
3.  The importer script uses the AnkiConnect API to create or update decks and cards in Anki, based on the data in the TSV file.

**Section sources**
- [README.md](file://README.md#L309-L310)
- [kardenwort_runner.py](file://src/kardenwort/core/kardenwort_runner.py#L211-L259)

## The kardenwort_runner.py Script
The `kardenwort_runner.py` script is the central automation tool that orchestrates the entire workflow. It simplifies the complex command-line arguments of `kardenwort.py` and automates the Anki import process.

**Key Responsibilities:**
*   **Configuration Management:** It reads the `config.ini` file to determine paths to the Python executable, the workspace, and the Anki importer script.
*   **Argument Assembly:** It constructs the full command-line argument list for the `kardenwort.py` script based on user input and configuration defaults.
*   **Workflow Automation:** It executes the `kardenwort.py` script, captures the output filename, and then automatically triggers the Anki import.
*   **Mixed-Mode Processing:** It supports the `--mode mixed-triple` option, which runs both the sentence and word processing modes sequentially, creating a shared hierarchical deck in Anki.
*   **User Experience:** It provides options like `--show-success-message` and `--play-sound-on-completion` to give feedback upon successful execution.

**Section sources**
- [kardenwort_runner.py](file://src/kardenwort/core/kardenwort_runner.py#L262-L364)
- [README.md](file://README.md#L210-L230)

## Practical Examples
The following examples demonstrate the processing of both single-line and multi-line inputs.

### Example 1: Processing a Single-Line Input
This command processes a single German sentence directly from the command line, creating vocabulary cards with compound splitting enabled.

```bash
python src/kardenwort/core/kardenwort_runner.py --type word --mode single --language de --text "Morgen fährt der neue Donaudampfschifffahrtsgesellschaftskapitän ab." --de-gcs
```

**Processing:**
1.  The single-line input triggers the sentence tokenization mode.
2.  The sentence is split into tokens.
3.  The compound word "Donaudampfschifffahrtsgesellschaftskapitän" is split into its components (e.g., "Dampf", "Schiff", "Fahrt", etc.) by GCS.
4.  Each component and the original compound are lemmatized.
5.  A TSV file is generated with one row for each unique lemma, which is then imported into Anki.

**Section sources**
- [README.md](file://README.md#L224-L225)
- [kardenwort-goldendict-config.txt](file://docs/kardenwort-goldendict-config.txt#L79-L99)

### Example 2: Processing a Multi-Line Input with Markdown Headers
This command processes a multi-line text file containing Markdown headers, creating both sentence and word cards in a shared hierarchical deck.

```bash
python src/kardenwort/core/kardenwort_runner.py --mode mixed-triple --language de --anki-markdown-decks --anki-deck-content parent-source --text "# Nachrichten\nIn Deutschland werden Märkte abgesagt."
```

**Processing:**
1.  The multi-line input (separated by `\n`) triggers the line-by-line processing mode.
2.  The `--mode mixed-triple` flag causes the runner to first run in `sentence` mode and then in `word` mode.
3.  The `--anki-markdown-decks` flag parses the `#` header to create a hierarchical deck structure (e.g., `Nachrichten::Nachrichten.sentence.de`).
4.  The `--anki-deck-content parent-source` flag ensures the full source text is added to the parent deck's description in Anki.
5.  Two TSV files are generated and imported, creating a cohesive study set.

**Section sources**
- [README.md](file://README.md#L227-L230)
- [kardenwort-goldendict-config.txt](file://docs/kardenwort-goldendict-config.txt#L205-L229)
- [text.txt](file://tests/source_texts/de/text.txt)

## Common Issues and Best Practices
To ensure optimal performance and accuracy, consider the following common issues and best practices.

### Common Issues
*   **Text Encoding:** All input files must be saved in **UTF-8** encoding. Using other encodings (e.g., ANSI, UTF-16) will result in garbled text and processing errors.
*   **Line-by-Line Correspondence:** When using parallel texts (e.g., source, translation), every line in the first file must have a corresponding line in the second and third files. Mismatched line counts will cause the import to fail or create misaligned cards.
*   **Missing Dependencies:** The `german-compound-splitter` library must be installed for German compound splitting to work. Similarly, the correct spaCy language models must be downloaded.

### Best Practices
*   **Use the `lemma_override.tsv` File:** This is the most powerful way to improve accuracy. When you see a lemmatization error, add a rule to this file. The system will remember the correction for all future processing.
*   **Process Large Documents in Chunks:** For very large documents, processing time can be significant. Consider splitting the text into smaller sections (e.g., by chapter) to improve performance and manageability.
*   **Leverage Markdown Headers:** Use `#` and `##` headers in your source text to automatically create a well-organized, hierarchical deck structure in Anki.
*   **Use the `mixed-triple` Mode:** For new texts, using `--mode mixed-triple` is often the best approach, as it creates both sentence and vocabulary cards in a single, shared deck, providing a comprehensive study set.

**Section sources**
- [README.md](file://README.md#L284-L285)
- [lemma_override_de.tsv.template](file://data/de/lemma_override_de.tsv.template)
- [config.ini](file://config.ini)