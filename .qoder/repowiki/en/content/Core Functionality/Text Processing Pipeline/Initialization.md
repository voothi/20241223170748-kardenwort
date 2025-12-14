# Initialization

<cite>
**Referenced Files in This Document**   
- [kardenwort_runner.py](file://src/kardenwort/core/kardenwort_runner.py)
- [kardenwort.py](file://src/kardenwort/core/kardenwort.py)
- [config.ini](file://config.ini)
- [config.ini.template](file://config.ini.template)
- [lemma_override_de.tsv](file://data/de/lemma_override_de.tsv)
- [lemma_override_en.tsv](file://data/en/lemma_override_en.tsv)
</cite>

## Table of Contents
1. [Configuration Loading and Path Resolution](#configuration-loading-and-path-resolution)
2. [Language Model Initialization](#language-model-initialization)
3. [German Compound Splitter (GCS) Setup](#german-compound-splitter-gcs-setup)
4. [Lemma Frequency Index and Sorting](#lemma-frequency-index-and-sorting)
5. [Lemma Override Rules Processing](#lemma-override-rules-processing)
6. [Practical Configuration Examples](#practical-configuration-examples)
7. [Common Initialization Issues](#common-initialization-issues)
8. [Performance Considerations](#performance-considerations)

## Configuration Loading and Path Resolution

The initialization phase of Kardenwort's text processing pipeline begins with the `kardenwort_runner.py` script, which orchestrates the entire setup process. The script's primary responsibility is to load configuration from the `config.ini` file and resolve critical paths for the Python interpreter, workspace, and importer components.

The `load_config()` function in `kardenwort_runner.py` first locates the `config.ini` file by traversing up from the script's parent directory. If the configuration file is not found, the script provides a clear error message instructing users to copy the `config.ini.template` file and fill in the required paths. This template serves as a comprehensive guide for setting up the environment correctly.

Once the configuration file is located, the script reads the `[environment]` section to extract three essential paths:
- `python_executable`: The path to the Python interpreter, which can be either absolute or relative to the configuration file
- `kardenwort_workspace`: The main workspace directory for the Kardenwort project
- `importer_workspace`: The workspace directory for the Anki CSV importer script

The script intelligently resolves relative paths by calculating them from the location of the `config.ini` file, ensuring portability across different systems. This approach allows users to maintain a self-contained project structure where the virtual environment can be colocated with the project files.

The configuration system also supports different operating systems, with examples provided for both Windows (using forward slashes or double backslashes) and Linux/macOS (using standard Unix paths). This cross-platform compatibility ensures that the pipeline can be initialized consistently regardless of the underlying operating system.

**Section sources**
- [kardenwort_runner.py](file://src/kardenwort/core/kardenwort_runner.py#L15-L53)
- [config.ini](file://config.ini#L1-L26)
- [config.ini.template](file://config.ini.template#L1-L26)

## Language Model Initialization

After configuration loading, the pipeline initializes the core natural language processing components, primarily the spaCy language models for German and English. The model selection is determined by the `--language` argument passed to the script, with "de" for German and "en" for English.

The initialization occurs in the `kardenwort.py` script, where the `spacy.load()` function is called with the appropriate model identifier:
- For German (`--language de`), the pipeline loads the `de_core_news_lg` model
- For English (`--language en`), the pipeline loads the `en_core_web_lg` model

These large models provide comprehensive linguistic analysis capabilities, including tokenization, part-of-speech tagging, dependency parsing, and lemmatization. The choice of large models ensures high accuracy in text processing, particularly for complex linguistic phenomena like compound word splitting in German.

The model loading process is wrapped in error handling to provide informative feedback if the required models are not installed. Users are directed to install the missing models using the `python -m spacy download` command. This proactive error handling helps prevent cryptic failures during initialization.

The language model is stored in a global variable `nlp`, making it accessible throughout the processing pipeline. This singleton pattern ensures that the model is loaded only once, conserving memory and improving performance when processing multiple texts.

**Section sources**
- [kardenwort.py](file://src/kardenwort/core/kardenwort.py#L1886-L1887)
- [kardenwort_runner.py](file://src/kardenwort/core/kardenwort_runner.py#L70-L87)

## German Compound Splitter (GCS) Setup

When processing German text, the pipeline can optionally initialize the German Compound Splitter (GCS) automaton, a specialized component designed to handle the complex compound word structures characteristic of the German language. The GCS is enabled through the `--de-gcs` command-line flag.

The GCS setup involves several key steps:
1. **Library Availability Check**: The script first checks if the `german-compound-splitter` library is installed by attempting to import it. If the library is not available, an error message directs users to install it via pip.
2. **Dictionary Loading**: The GCS requires a dictionary file (specified by `dictionary_file_de` in the configuration) to identify valid word components. The script verifies that this file exists before proceeding.
3. **Automaton Construction**: Using the `comp_split.read_dictionary_from_file()` function, the script constructs an Aho-Corasick automaton from the dictionary. This efficient data structure enables rapid pattern matching for compound word splitting.

The GCS configuration supports several advanced options that control its behavior:
- `--de-gcs-split-mode`: Determines the aggressiveness of splitting (only-nouns, any, or combined)
- `--de-gcs-pos-tags`: Specifies which part-of-speech tags to apply splitting to, with support for inclusion and exclusion modes
- `--de-gcs-preserve-compound-word`: Keeps the original compound word in addition to its split components
- `--de-gcs-add-parts-to-wordlist`: Adds split components to the output wordlist

These configuration options provide fine-grained control over the compound splitting process, allowing users to balance between comprehensive analysis and output conciseness.

**Section sources**
- [kardenwort.py](file://src/kardenwort/core/kardenwort.py#L1899-L1908)
- [kardenwort_runner.py](file://src/kardenwort/core/kardenwort_runner.py#L123-L134)

## Lemma Frequency Index and Sorting

The initialization process includes loading a lemma frequency index used for sorting processed words. This index is a CSV file containing lemmas ranked by their frequency in a large corpus, with more common words appearing earlier in the file.

The frequency index is specified in the `config.ini` file under the `[language_resources]` section:
- `lemma_file_de`: Path to the German lemma frequency file
- `lemma_file_en`: Path to the English lemma frequency file

The pipeline loads this index into a dictionary where each lemma is mapped to its line number (position) in the file. During text processing, this index is used to sort extracted lemmas by frequency, ensuring that more common vocabulary appears first in the output. This sorting behavior supports language learning priorities, where high-frequency words are typically learned before less common ones.

The sorting algorithm implements a three-tiered approach:
1. Lemmas present in the frequency index are sorted by their index position
2. Lemmas not found in the index are sorted alphabetically
3. A case-insensitive comparison is used as a final tiebreaker

This sophisticated sorting ensures that the output is both linguistically meaningful and consistently ordered, providing a predictable experience for users.

**Section sources**
- [kardenwort_runner.py](file://src/kardenwort/core/kardenwort_runner.py#L76-L77)
- [kardenwort.py](file://src/kardenwort/core/kardenwort.py#L1910)
- [config.ini](file://config.ini#L55-L56)

## Lemma Override Rules Processing

A critical aspect of the initialization phase is the loading and processing of user-defined lemma override rules from TSV files. These rules allow users to customize the lemmatization behavior for specific words or patterns, overriding the default spaCy lemmatization.

The override rules are loaded from files specified in the configuration:
- `override_file_de`: Path to the German lemma override file
- `override_file_en`: Path to the English lemma override file

The `load_lemma_override_rules()` function parses these TSV files into a structured dictionary with three priority levels:
- **Priority 1**: Rules that match both the spaCy lemma and the original word form
- **Priority 2**: Rules that match only the original word form
- **Priority 3**: Rules that match only the spaCy lemma

Each rule can also include an optional context condition that must be present in the sentence for the rule to apply. This context can be a simple substring or a regular expression pattern prefixed with "regex:".

The override system implements a cascading priority logic:
1. Priority 1 rules are checked first, providing the most specific control
2. If no Priority 1 rule matches, Priority 2 rules are evaluated
3. Finally, Priority 3 rules serve as a fallback for broader lemma corrections

This hierarchical approach allows users to create precise, context-sensitive lemmatization rules while maintaining a sensible fallback mechanism. For example, the German override file includes rules to correct plural forms (e.g., "Anhänge" → "Anhang") and handle special cases like genitive forms.

**Section sources**
- [kardenwort_runner.py](file://src/kardenwort/core/kardenwort_runner.py#L77)
- [kardenwort.py](file://src/kardenwort/core/kardenwort.py#L74-L144)
- [lemma_override_de.tsv](file://data/de/lemma_override_de.tsv)
- [lemma_override_en.tsv](file://data/en/lemma_override_en.tsv)

## Practical Configuration Examples

The `config.ini` file provides several practical examples of how configuration values directly affect initialization behavior. For instance, the `python_executable` path determines which Python environment is used, allowing users to specify virtual environments for dependency isolation.

The workspace paths enable flexible project organization:
- Setting `kardenwort_workspace = ./` configures the current directory as the workspace
- The `importer_workspace` can point to a separate repository, facilitating modular development

Language resource configuration demonstrates how different processing profiles can be created:
- The German pipeline can be configured to use different lemma frequency files (e.g., news-based vs. mixed-typical corpora)
- Dictionary files can be customized to include domain-specific vocabulary

Command-line arguments passed through the configuration system enable various processing modes:
- `--type word` vs `--type sentence` determines whether word extraction or sentence processing is performed
- `--mode single`, `dual`, or `triple` controls how many input texts are processed
- `--de-gcs` enables compound splitting for German text

These configuration options can be combined to create specialized processing workflows, such as generating Anki flashcards with compound word components or creating vocabulary lists sorted by frequency.

**Section sources**
- [config.ini](file://config.ini)
- [kardenwort_runner.py](file://src/kardenwort/core/kardenwort_runner.py#L56-L176)

## Common Initialization Issues

Several common issues can occur during the initialization phase, primarily related to configuration and resource availability:

**Missing Configuration Files**: If `config.ini` is not found, the script provides a clear error message and instructions to copy the template file. This prevents silent failures and guides users through proper setup.

**Incorrect Path Resolution**: Relative paths in the configuration must be specified correctly relative to the `config.ini` file location. Users often encounter issues when moving the project directory without updating paths or when using incorrect path separators on different operating systems.

**Model Loading Failures**: The most frequent initialization error occurs when the required spaCy models are not installed. The error message specifically directs users to install the missing models using the `spacy download` command.

**GCS Library Issues**: When the `german-compound-splitter` library is not installed, the script fails with a clear error message indicating the required pip installation command.

**File Permission Problems**: On some systems, the script may encounter permission issues when trying to read configuration files or write to output directories, particularly in restricted environments.

**Resource Path Errors**: Incorrect paths to dictionary files or lemma frequency files can cause initialization to fail, with specific error messages indicating which file was not found.

These issues are addressed through comprehensive error handling and user-friendly error messages that guide troubleshooting and resolution.

**Section sources**
- [kardenwort_runner.py](file://src/kardenwort/core/kardenwort_runner.py#L17-L20)
- [kardenwort.py](file://src/kardenwort/core/kardenwort.py#L1900-L1908)

## Performance Considerations

The initialization phase involves several performance-critical operations that impact the overall efficiency of the text processing pipeline:

**Model Loading Time**: Loading the large spaCy models (`de_core_news_lg` and `en_core_web_lg`) represents the most significant initialization cost. These models can take several seconds to load due to their size (typically hundreds of megabytes). To mitigate this, the pipeline loads the model only once and reuses it for multiple processing tasks.

**Memory Usage**: The language models and GCS automaton consume substantial memory. The large spaCy models require several hundred megabytes of RAM, while the GCS automaton's memory footprint depends on the size of the dictionary file.

**Disk I/O**: Reading configuration files, lemma frequency indices, and dictionary files involves disk operations that can impact initialization speed, particularly on systems with slow storage.

**Startup Optimization**: The pipeline could benefit from lazy loading strategies, where components are loaded only when needed, rather than all at initialization. For example, the GCS automaton could be initialized only when the `--de-gcs` flag is used.

**Caching**: Implementing caching for frequently accessed resources like the lemma frequency index could improve performance for repeated processing tasks.

**Parallel Initialization**: Some initialization tasks, such as loading multiple language models, could potentially be parallelized to reduce overall startup time.

Best practices for managing language resources include keeping the workspace directory on fast storage, ensuring sufficient system memory, and using virtual environments to maintain consistent dependency versions.

**Section sources**
- [kardenwort.py](file://src/kardenwort/core/kardenwort.py#L1886-L1887)
- [kardenwort_runner.py](file://src/kardenwort/core/kardenwort_runner.py#L15-L53)