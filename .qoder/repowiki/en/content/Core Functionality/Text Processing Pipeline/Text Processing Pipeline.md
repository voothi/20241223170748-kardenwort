# Text Processing Pipeline

<cite>
**Referenced Files in This Document**   
- [kardenwort_runner.py](file://src/kardenwort/core/kardenwort_runner.py)
- [kardenwort.py](file://src/kardenwort/core/kardenwort.py)
- [config.ini](file://config.ini)
- [lemma_override_de.tsv.template](file://data/de/lemma_override_de.tsv.template)
- [text1.txt](file://tests/source_texts/de/text1.txt)
- [text2.txt](file://tests/source_texts/de/text2.txt)
- [text3.txt](file://tests/source_texts/de/text3.txt)
</cite>

## Table of Contents
1. [Introduction](#introduction)
2. [Core Processing Modes](#core-processing-modes)
3. [Hybrid Sentence Splitting Mechanism](#hybrid-sentence-splitting-mechanism)
4. [Text Processing Pipeline Stages](#text-processing-pipeline-stages)
5. [The kardenwort_runner.py Script](#the-kardenwort_runnerpy-script)
6. [Practical Examples](#practical-examples)
7. [Common Issues and Best Practices](#common-issues-and-best-practices)
8. [Conclusion](#conclusion)

## Introduction
The Kardenwort text processing pipeline is a sophisticated system designed to transform raw text into structured, context-rich flashcards for language learning in Anki. This pipeline leverages natural language processing (NLP) to automate the extraction of vocabulary and sentences, providing a powerful tool for efficient language acquisition. The system is built around two primary processing modes—word extraction and sentence processing—each tailored to different learning objectives. The pipeline's intelligence lies in its ability to adapt its processing strategy based on the input format, using a hybrid sentence splitting mechanism that combines line-by-line processing with grammatical tokenization. Orchestrated by the `kardenwort_runner.py` script, the pipeline handles everything from initialization with NLP models to the final import of cards into Anki, ensuring a seamless and automated workflow.

## Core Processing Modes
Kardenwort operates in two distinct modes, each designed to serve a specific purpose in the language learning process: word extraction for vocabulary cards and sentence processing for contextual cards. These modes are selected via the `--type` command-line argument and represent fundamentally different approaches to text analysis.

### Word Extraction (Vocabulary Cards)
The word extraction mode, activated with `--type word`, is designed to create flashcards focused on individual vocabulary items. In this mode, the pipeline performs a comprehensive analysis of the entire input text to identify and extract unique lemmas—the base forms of words. The process begins with tokenization, where the text is broken down into individual words and punctuation. Each token is then lemmatized using the spaCy library, which applies linguistic rules to reduce inflected forms (e.g., "running," "ran") to their dictionary form ("run"). For German text, this is augmented with advanced features like German Compound Splitting (GCS), which deconstructs long compound words (e.g., "Donaudampfschifffahrtsgesellschaftskapitän") into their constituent parts (e.g., "Donau," "Dampf," "Schiff," etc.). The pipeline then applies user-defined override rules from the `lemma_override.tsv` file to correct any lemmatization errors based on context. The final output is a list of unique lemmas, sorted by frequency and relevance, with each lemma receiving its own flashcard. This card includes the original sentence for context, a list of all words in that sentence, and other metadata, making it ideal for focused vocabulary study.

**Section sources**
- [kardenwort.py](file://src/kardenwort/core/kardenwort.py#L476-L592)
- [kardenwort_runner.py](file://src/kardenwort/core/kardenwort_runner.py#L272)

### Sentence Processing (Contextual Cards)
The sentence processing mode, activated with `--type sentence`, is designed to create flashcards that present full sentences for studying grammar, syntax, and phrase usage in context. Unlike the word extraction mode, which analyzes the entire text holistically, the sentence processing mode treats each line of the input as a discrete unit. The pipeline processes the input files line-by-line, creating one flashcard for each content line from the primary source file. If parallel texts are provided (e.g., a translation), the corresponding lines from the secondary and tertiary files are added to the same card, allowing for direct comparison. This mode is particularly effective for studying subtitles, dialogues, or any text where the line structure is meaningful. The resulting flashcard displays the full source sentence, along with surrounding context (sentences before and after), and the parallel translations. This provides a rich, contextual learning experience that helps users understand how words and phrases are used in real-world language.

**Section sources**
- [kardenwort.py](file://src/kardenwort/core/kardenwort.py#L672-L800)
- [kardenwort_runner.py](file://src/kardenwort/core/kardenwort_runner.py#L272)

## Hybrid Sentence Splitting Mechanism
A key feature of the Kardenwort pipeline is its hybrid sentence splitting mechanism, which intelligently determines how to segment the input text into processing units. This mechanism automatically chooses between two strategies—line-by-line processing and spaCy's grammatical sentence tokenization—based on the format of the input text, ensuring optimal results for different types of content.

### Line-by-Line Processing
Line-by-line processing is triggered when the input text contains at least one newline character (`\n`). In this mode, each line is treated as a complete and independent unit for processing. This approach is ideal for structured text formats where the line break carries semantic meaning, such as subtitles, poetry, or parallel texts. For example, when processing a file with German text on one line and its English translation on the next, the pipeline preserves this correspondence by creating a single flashcard that pairs the two lines. This method ensures that the original structure of the text is maintained, which is crucial for maintaining the integrity of parallel translations and for studying content where the line is the natural unit of meaning.

### Grammatical Sentence Tokenization
Grammatical sentence tokenization is used when the input text is a single block of prose without any newline characters. In this scenario, the pipeline delegates the task of segmentation to spaCy's built-in sentence tokenizer. This NLP component uses a statistical model trained on large corpora to identify sentence boundaries based on punctuation, capitalization, and grammatical structure. For instance, it can correctly split a paragraph like "I went to the store. I bought some milk." into two distinct sentences, even if they are on the same line. This method is essential for processing continuous prose from books, articles, or web pages, where the sentence, not the line, is the fundamental unit of meaning. By using a sophisticated NLP model, Kardenwort achieves a high degree of accuracy in identifying sentence boundaries, which is critical for providing accurate context in the generated flashcards.

**Section sources**
- [kardenwort.py](file://src/kardenwort/core/kardenwort.py#L687-L714)
- [README.md](file://README.md#L286-L294)

## Text Processing Pipeline Stages
The Kardenwort text processing pipeline is a multi-stage process that transforms raw text into a structured TSV file ready for import into Anki. Each stage builds upon the previous one, applying a series of transformations and analyses to extract meaningful linguistic data.

### Initialization with spaCy Models and Dictionaries
The pipeline begins with an initialization phase where all necessary resources are loaded into memory. The `kardenwort_runner.py` script first reads the configuration from `config.ini` to determine the paths to the Python executable, workspace directories, and language-specific resources. It then loads the appropriate spaCy language model (e.g., `de_core_news_lg` for German) which provides the core NLP capabilities for tokenization, lemmatization, and part-of-speech tagging. Simultaneously, it loads auxiliary resources such as the German dictionary file (`german.dic`) for compound word validation and the lemma override rules from the `lemma_override.tsv` file. This initialization ensures that all components are ready before any text processing begins, setting the stage for accurate and consistent analysis.

**Section sources**
- [kardenwort_runner.py](file://src/kardenwort/core/kardenwort_runner.py#L15-L53)
- [kardenwort.py](file://src/kardenwort/core/kardenwort.py#L2-L19)

### Text Ingestion from Various Sources
The pipeline supports multiple methods for ingesting text, providing flexibility for different use cases. Text can be provided as a command-line argument using the `--text` flag, read from a file specified by `--text1-file`, `--text2-file`, or `--text3-file`, passed via an environment variable (`KARDENWORT_INPUT_TEXT`), or piped through standard input (stdin). This versatility allows Kardenwort to be integrated into various workflows, from batch processing files to real-time analysis in dictionary applications like GoldenDict. The input text must be in plain text format with UTF-8 encoding to ensure compatibility with the NLP models and to support a wide range of characters and diacritics.

**Section sources**
- [kardenwort_runner.py](file://src/kardenwort/core/kardenwort_runner.py#L153-L174)
- [kardenwort.py](file://src/kardenwort/core/kardenwort.py#L311-L319)

### Tokenization and Lemmatization with German Compound Splitting
This is the core analytical stage of the pipeline. The text is processed by the spaCy model, which breaks it into tokens and assigns linguistic properties to each. For each token, the pipeline performs lemmatization to find its base form. In German mode, this is enhanced with German Compound Splitting (GCS), which uses a specialized algorithm to decompose compound nouns. The pipeline first checks if the word contains hyphens or if it is a long noun that might be a compound. If so, it applies the GCS algorithm to split the word into its components, lemmatizes each component individually, and then applies the user's override rules to correct any errors. This process is critical for German, where compound words are ubiquitous and their components carry independent meaning.

**Section sources**
- [kardenwort.py](file://src/kardenwort/core/kardenwort.py#L476-L584)
- [lemma_override_de.tsv.template](file://data/de/lemma_override_de.tsv.template#L1-L227)

### Collection and Sorting of Unique Lemmas
After processing all tokens, the pipeline collects the resulting lemmas based on the deduplication scope specified by the `--deduplication-scope` argument. In `global` mode, all lemmas from the entire text are collected into a single set, ensuring each unique lemma appears only once. In `sentence` mode, deduplication is performed within each sentence, allowing the same lemma to appear on multiple cards if it occurs in different sentences. The collected lemmas are then sorted using a frequency index loaded from a CSV file. Known words (those in the frequency list) are placed first, followed by unknown words, which helps prioritize high-frequency vocabulary in the learning process.

**Section sources**
- [kardenwort.py](file://src/kardenwort/core/kardenwort.py#L588-L592)
- [kardenwort.py](file://src/kardenwort/core/kardenwort.py#L295-L309)

### TSV and JSON Metadata Generation
The final stage of the pipeline is the generation of output files. The processed data is formatted into a TSV (Tab-Separated Values) file with a predefined 82-column structure. This structure includes fields for the source sentence, target translations, word lists, audio, images, and numerous other metadata fields designed for the Anki card template. If the `--anki-deck-content` flag is used, a companion JSON file is also generated. This JSON file contains deck descriptions, which are populated with the full source text and translations. These descriptions are automatically imported into Anki, providing valuable context directly within the deck browser.

**Section sources**
- [kardenwort.py](file://src/kardenwort/core/kardenwort.py#L320-L404)
- [kardenwort.py](file://src/kardenwort/core/kardenwort.py#L594-L671)

### Anki Import Orchestration
The `kardenwort_runner.py` script orchestrates the final step by automatically invoking the `anki-csv-importer.py` script. It passes the path to the generated TSV and JSON files, along with arguments for the target deck name and note type. The importer script then uses the AnkiConnect API to create or update the specified deck in Anki, adding all the new cards. This seamless integration eliminates the need for manual file handling, making the entire process from text input to card creation fully automated.

**Section sources**
- [kardenwort_runner.py](file://src/kardenwort/core/kardenwort_runner.py#L211-L259)

## The kardenwort_runner.py Script
The `kardenwort_runner.py` script is the central orchestrator of the entire Kardenwort pipeline. It acts as a wrapper around the core `kardenwort.py` processing script, automating the workflow and handling the integration with Anki. The script begins by loading the configuration from `config.ini`, which defines the paths to the Python executable, the Kardenwort workspace, and the Anki CSV importer workspace. It then parses command-line arguments to determine the processing mode (e.g., `single`, `dual`, `triple`, or `mixed-triple`), the language, and the type of processing. For the `mixed-triple` mode, the script runs the word and sentence processing sequentially, creating a shared hierarchical deck structure. After the core processing script generates the TSV file, the runner script captures the output filename and passes it to the Anki importer, completing the workflow. This script is essential for providing a user-friendly interface to the complex underlying pipeline.

**Section sources**
- [kardenwort_runner.py](file://src/kardenwort/core/kardenwort_runner.py#L262-L364)

## Practical Examples
To illustrate the pipeline in action, consider two practical examples using the test files provided in the repository.

### Example 1: Processing a Single-Line Input
For a single-line input, such as the sentence "Ich stehe morgen früh auf." stored in `text1.txt`, the pipeline would use grammatical sentence tokenization. The `kardenwort_runner.py` script is called with `--type word --mode single --language de`. The spaCy model tokenizes the sentence into ["Ich", "stehe", "morgen", "früh", "auf", "."]. It lemmatizes "stehe" to "stehen" and "auf" to "auf", recognizing "auf" as a separable verb particle. The output TSV file would contain a single row for the lemma "stehen", with the full sentence as context.

### Example 2: Processing a Multi-Line Input
For a multi-line input, such as the three parallel texts in `text1.txt`, `text2.txt`, and `text3.txt`, the pipeline uses line-by-line processing. When called with `--type sentence --mode triple --language de`, the script processes each line as a unit. For line 12, it creates a card with the German sentence "Morgen fährt der neue Donaudampfschifffahrtsgesellschaftskapitän mit seinem Boot donauabwärts ab." in the source field, the Russian translation in the target field, and the literal Ukrainian translation in the tertiary field. The card would also include the surrounding sentences for context.

**Section sources**
- [text1.txt](file://tests/source_texts/de/text1.txt#L1-L14)
- [text2.txt](file://tests/source_texts/de/text2.txt#L1-L14)
- [text3.txt](file://tests/source_texts/de/text3.txt#L1-L14)

## Common Issues and Best Practices
Users of the Kardenwort pipeline should be aware of several common issues and best practices to ensure optimal results.

### Text Encoding and Line-by-Line Correspondence
A critical requirement is that all input files must be encoded in UTF-8. Using a different encoding can result in garbled text and processing errors. For parallel texts, strict line-by-line correspondence is essential. Each line in the source file must have a corresponding translation in the same line of the target file. Any mismatch in line count or order will result in incorrect pairings on the flashcards.

### Performance Considerations for Large Documents
Processing large documents can be resource-intensive. The pipeline loads the entire text into memory and performs NLP analysis on every token. For very large files, this can lead to high memory usage and long processing times. A best practice is to split large documents into smaller, thematic sections (e.g., by chapter or article) before processing. This not only improves performance but also results in more focused and manageable Anki decks.

### Best Practices for Optimal Accuracy
To achieve the highest accuracy, users should actively maintain the `lemma_override.tsv` file. When the pipeline produces an incorrect lemma, the user should add a rule to correct it. Over time, this creates a personalized dictionary that significantly improves the quality of the output. Additionally, using the `--de-gcs` flag with appropriate POS tags (e.g., `--de-gcs-pos-tags "!VERB"`) can prevent over-splitting of verbs while still capturing noun compounds.

**Section sources**
- [README.md](file://README.md#L284)
- [config.ini](file://config.ini#L1-L65)

## Conclusion
The Kardenwort text processing pipeline is a robust and intelligent system for transforming text into effective language learning materials. By combining two distinct processing modes—word extraction for vocabulary study and sentence processing for contextual learning—with a smart hybrid splitting mechanism, it offers a flexible solution for a wide range of input types. The pipeline's stages, from initialization and text ingestion to lemmatization and Anki import, are carefully orchestrated by the `kardenwort_runner.py` script to provide a seamless, automated experience. With attention to best practices regarding text encoding, line correspondence, and performance, users can leverage this powerful tool to accelerate their language acquisition journey.