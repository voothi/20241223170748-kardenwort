# LinguaCard Creator

![Version](https://img.shields.io/badge/version-v1.0.0-blue)

LinguaCard Creator is a powerful command-line utility designed to accelerate language learning by automatically creating Anki flashcards from any text. It intelligently processes your source material, extracts vocabulary (tokens) and full sentences, and generates a structured file ready for direct import into Anki.

This tool is perfect for language learners who want to build personalized decks from books, articles, subtitles, or any other text they are studying.

## Quick Start

Get your first Anki deck in 5 minutes:

1.  **Prerequisites**: Make sure **Anki Desktop is running** with the [AnkiConnect](https://ankiweb.net/shared/info/2055492159) add-on installed.
2.  **Clone & Setup**: Clone all three required projects and set up the Python environment.
    ```bash
    # Clone repositories
    git clone <url-for-this-repo>
    git clone <url-for-anki-csv-importer-repo>
    git clone <url-for-anki-template-repo>

    # Create and activate virtual environment
    python -m venv venv
    .\venv\Scripts\activate  # Windows

    # Install dependencies
    pip install spacy "german-compound-splitter>=2.0.0" requests
    python -m spacy download de_core_news_lg
    ```
3.  **Import Anki Template**: Import the `basic-20240218092126` note type from the `20241106211123-anki-template` project into Anki.
4.  **Prepare Text**: Open the file `in/text1.txt` and add some German sentences. For example:
    ```
    Die Fischer kennen die Austernbanken vor der Küste sehr gut.
    Sie fahren sie gezielt an.
    ```
5.  **Run**: Execute the batch script.
    ```bash
    t_batch_de.single.bat
    ```
**Done!** Check Anki for a new deck filled with cards created from your text.

## Key Features
*   **Dual Card Types**: Create both vocabulary cards (single words) and sentence cards (full phrases).
*   **Multiple Processing Modes**: `single`, `dual`, and `triple` text processing for monolingual, bilingual, or trilingual contexts.
*   **Multi-Language Support**: Currently supports **English (en)** and **German (de)**.
*   **Advanced NLP**: Uses `spaCy` for accurate lemmatization (finding the base form of words).
*   **German Compound Splitting (GCS)**: Intelligently breaks down long German compound words into their components.
*   **Direct Anki Integration**: Automatically imports the generated cards into your Anki collection using AnkiConnect.
*   **GoldenDict-ng Integration**: Create Anki cards directly from your favorite dictionary application.

---

## Usage Scenarios

You can use LinguaCard Creator in several ways, from simple batch files to direct command-line calls for advanced integration.

### 1. Basic Usage (Using Batch Files)

This is the easiest way to get started.

1.  **Prepare your input files** in the `in/` directory (`text1.txt`, `text2.txt`, etc.).
2.  **Ensure Anki is running** with AnkiConnect.
3.  **Run the appropriate `.bat` script**. The filename indicates its function: `t_batch_{language}.{mode}.bat`.
    *   `t_batch_de.dual.bat`: Creates German cards from `in/text1.txt` and `in/text2.txt`.
    *   `t_batch_en.single.bat`: Creates English cards from `in/text1.txt` only.

### 2. GoldenDict-ng Integration

Instantly create Anki cards from any word or phrase you look up in GoldenDict. This creates a seamless workflow from discovery to study.

![*(GoldenDict-ng Main Window)*](assets\20250829201257.png)


**Setup:**

1.  In GoldenDict-ng, go to `Edit` -> `Dictionaries`.
2.  Go to the **Programs** tab.
3.  Click **Add**, and configure a new program:
    *   **Type**: `Plain Text`
    *   **Enabled**: ☑️
    *   **Name**: `Create Anki Card (DE Token)` (or any name you like)
    *   **Command Line**:
        ```
        U:\voothi\20250825231214-spacy-env\Scripts\python.exe U:\voothi\20241223170748-token-extraction\t_starter.py --language de --type token --mode single --text "%GDWORD%"
        ```
        **Important:** You **must** replace the paths to `python.exe` and `t_starter.py` with the absolute paths on your system.

4.  Click **OK** to save.

**How to Use:**
Now, when you look up a word or highlight a sentence in GoldenDict, a new dictionary tab `Create Anki Card (DE Token)` will appear. Clicking on it will run the script in the background and automatically add the new cards to Anki.

### 3. Advanced Usage (Direct Command-Line)

For maximum flexibility, you can call the scripts directly. The main entry point is `t_starter.py`, which handles both processing and importing.

#### Command-Line Examples

*   **Create German token cards from a single text file:**
    ```bash
    python t_starter.py --language de --type token --mode single --text "Die Fischer kennen die Austernbanken."
    ```

*   **Create English sentence cards from parallel files:**
    ```bash
    # Ensure in/text1.txt and in/text2.txt are populated
    python t_starter.py --language en --type sentence --mode dual
    ```

*   **Create German cards from three files:**
    ```bash
    python t_starter.py --language de --type token --mode triple
    ```

---

## Command-Line Arguments (`token_mix_combined.py`)

Below is a detailed list of all available arguments for the core processing script, `token_mix_combined.py`. These can be passed through `t_starter.py`.

### Core Arguments

| Argument | Description | Example |
| :--- | :--- | :--- |
| `--type` | **(Required)** The type of cards to create. | `token` or `sentence` |
| `--language` | **(Required)** The source language of the text. | `de` or `en` |
| `--mode` | **(Required)** The processing mode based on the number of input files. | `single`, `dual`, `triple` |

### Input & Output

| Argument | Description | Example |
| :--- | :--- | :--- |
| `--text` | Process a string directly instead of a file. For `single` mode only. | `--text "This is a test."` |
| `--text1` | Path to the primary source text file. | `--text1 "in/source.txt"` |
| `--text2` | Path to the second text file (e.g., translation). For `dual`/`triple` modes. | `--text2 "in/target.txt"` |
| `--text3` | Path to the third text file. For `triple` mode only. | `--text3 "in/extra.txt"` |
| `--output` | The path for the output `.tsv` file. | `--output "out/my_deck.tsv"` |
| `--timestamp` | Prepend a `YYYYMMDDHHMMSS-` timestamp to the output filename. | `--timestamp` |
| `--autoname [N]` | Automatically generate part of the filename from the first `N` words of the text (default is 4). | `--autoname 3` |
| `--pipe` | Print the final output filename to standard output. Useful for chaining scripts. | `--pipe` |

### Card Content & Formatting

| Argument | Description | Example |
| :--- | :--- | :--- |
| `--sentence-context-size N` | Number of preceding and succeeding sentences to include as context. | `--sentence-context-size 2` |
| `--include-simple-list` | Include a simple list of all unique words from the source sentence in the `SentenceSourceWordlist` field. | `--include-simple-list` |
| `--with-fields` | Include the header row with all field names in the output TSV file. | `--with-fields` |
| `--with-br` | Use `<br>` tags instead of newlines for the `SentenceSourceWordlist`. | `--with-br` |
| `--two-column-output-to-file` | Add the inflected (original) form of a word to the `WordSourceInflectedForm` field. | `--two-column-output-to-file` |

### German Compound Splitting (GCS) Options

These options are only for `--language de`.

| Argument | Description | Example |
| :--- | :--- | :--- |
| `--gcs` | **Enable** German Compound Splitting. | `--gcs` |
| `--gcs-dictionary` | Path to the dictionary file used by GCS for validation. | `--gcs-dictionary "dicts/german.dic"` |
| `--gcs-include-compound` | Include the original compound word in the card list along with its split parts. | `--gcs-include-compound` |
| `--gcs-combine-noun-modes` | Runs GCS in two modes (splitting on nouns-only and any word type) and merges the results for more comprehensive splitting. | `--gcs-combine-noun-modes` |
| `--gcs-fix-genitive` | Attempts to correct German genitive noun lemmas (e.g., 'Hauses' -> 'Haus'). | `--gcs-fix-genitive` |
| `--gcs-in-wordlist` | Also add the split components to the `SentenceSourceWordlist` field. | `--gcs-in-wordlist` |

---

## Project Ecosystem & Template

(The rest of the README remains the same: Project Ecosystem, The Anki Card Template, Requirements, Installation, License, etc.)

## Project Ecosystem

LinguaCard Creator is part of a larger ecosystem of tools designed to work together:

-   **LinguaCard Creator (This Project)**: The core engine for text processing and TSV file generation.
-   [**Anki Template (20241106211123-anki-template)**](https://github.com/user/repo-link) (*link placeholder*): A specialized Anki card template is **required** for the generated files to display correctly. It provides the feature-rich layout shown below.
-   [**Anki CSV Importer (20250401192017-anki-csv-importer)**](https://github.com/user/repo-link) (*link placeholder*): A standalone script that communicates with Anki via the AnkiConnect add-on to perform the import.

## Related Utilities

The generated TSV files are designed to be used with a specific, feature-rich Anki template named `basic-20240218092126`. This template organizes the information into a clean, interactive, and powerful layout for effective learning.

-   `20250421115831-gtts-player`
-   `20250212113752-intellifilter`
-   `20250228230803-whisper`
-   `20250311224733-search-py`
-   `deep-translator`
-   `gTTS`
-   `argotranslate`
-   `fabric`
-   `piper-tts`
-   `merge_media`
-   `split_media_by_subtitles`
-   and others.

## The Anki Card Template

The generated TSV files are designed to be used with a specific, feature-rich Anki template named `basic-20240218092126`. This template organizes the information into a clean, interactive, and powerful layout for effective learning.

![An example of a generated German vocabulary card using the template](assets/20250829200342.png)
*(Note: To display this image, create an `assets` folder in your repository and place the image file inside.)*

**Template Features:**

*   **Interactive Collapsible Sections**: Information is grouped into sections like "Source", "Destination", and "AI". You can click on a header to reveal or hide the content, keeping the card uncluttered.
*   **Dynamic Fields**: Fields only appear if they contain data. For example, the "Wordlist" section won't show up if it's empty.
*   **Integrated Audio**: Supports both pre-recorded audio files and automatic text-to-speech (TTS) for words and sentences.
*   **Context Display**: Shows the sentence in its original context (previous and next sentences) to aid comprehension.
*   **Full Word List**: Displays all unique words (lemmas) found in the source sentence.

## Requirements

1.  **Python 3.9**: The scripts are tested with Python 3.9. Using newer versions might cause compatibility issues with dependencies.
2.  **Anki Desktop**: The Anki application must be installed and running.
3.  **AnkiConnect Add-on**: You need to install the [AnkiConnect](https://ankiweb.net/shared/info/2055492159) add-on in Anki.
4.  **Git**: To clone the required repositories.

## Installation

1.  **Clone the repositories**:
    It is recommended to clone all three projects into the same parent directory.

    ```bash
    git clone <url-for-this-repo>
    git clone <url-for-anki-csv-importer-repo>
    git clone <url-for-anki-template-repo>
    ```

2.  **Import the Anki Template**:
    Open Anki Desktop and import the note type from the `20241106211123-anki-template` project. This will add the `basic-20240218092126` note type to your collection.

3.  **Set up the Python Virtual Environment**:
    Navigate to the project directory and create a virtual environment.

    ```bash
    # Navigate to your environment directory (e.g., 20250825231214-spacy-env)
    python -m venv venv
    ```

4.  **Activate the Environment**:
    -   On Windows: `.\venv\Scripts\activate`
    -   On macOS/Linux: `source ./venv/bin/activate`

5.  **Install Dependencies**:
    Install the required Python packages.

    ```bash
    pip install spacy "german-compound-splitter>=2.0.0" requests
    ```

6.  **Download SpaCy Models**:
    Download the language models for English and German.

    ```bash
    python -m spacy download en_core_web_lg
    python -m spacy download de_core_news_lg
    ```

## Configuration

Before running the scripts, you need to update the hardcoded paths to match your system setup.

-   **In all `.bat` files** (e.g., `t_batch_de.dual.bat.txt`):
    -   `PYTHON_PATH`: Set this to the path of the Python executable inside your virtual environment.
    -   `WORKSPACE`: Set this to the root directory of the `LinguaCard Creator` project.
-   **In `t_starter.py`**:
    -   Update the paths for `python_path`, `token_workspace`, and `importer_workspace` if you did not clone the projects into the same parent folder.
-   **In `anki-csv-importer.py` (from the importer project)**:
    -   The script is configured to get the note type name (`--note`) as an argument, which is correctly set to `"Basic 20240218092126"` in `t_starter.py`.

## Usage

1.  **Prepare your input files**:
    -   Place your source text in `in/text1.txt`. Each line should correspond to a sentence.
    -   If using `dual` or `triple` mode, place the corresponding translation(s) in `in/text2.txt` and `in/text3.txt`. The line numbers must match `text1.txt`.

2.  **Ensure Anki is running** with the AnkiConnect add-on enabled.

3.  **Run a batch script**:
    Execute one of the provided `.bat` files to start the process.

    -   **To create German vocabulary and sentence cards from two text files:**
        ```bash
        t_batch_de.dual.bat
        ```

The script will run, generate a timestamped `.tsv` file in the `out/` directory, and then automatically call the importer. A new deck named after the generated file will appear in Anki.

## License and Acknowledgements

This project is licensed under the MIT License. See the `LICENSE` file for details.

This project utilizes code from the `anki-csv-importer` project.
-   **Author**: Gulshan Singh
-   **License**: MIT License
-   A copy of the license is included in the header of the `anki-csv-importer.py` file. We are grateful for this contribution to the open-source community.