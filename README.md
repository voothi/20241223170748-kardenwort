# LinguaCard Creator

![Version](https://img.shields.io/badge/version-v1.0.0-blue)

LinguaCard Creator is a powerful command-line utility designed to accelerate language learning by automatically creating Anki flashcards from any text. It intelligently processes your source material, extracts vocabulary (tokens) and full sentences, and generates a structured file ready for direct import into Anki.

This tool is perfect for language learners who want to build personalized decks from books, articles, subtitles, or any other text they are studying.

## Key Features

-   **Dual Card Types**: Create both vocabulary cards (single words) and sentence cards (full phrases).
-   **Multiple Processing Modes**:
    -   **Single Mode**: Process a single source text (e.g., for monolingual cards).
    -   **Dual Mode**: Process a source text and its translation.
    -   **Triple Mode**: Process a source text and two other versions (e.g., two different translations or a phonetic transcription).
-   **Multi-Language Support**: Currently supports **English (en)** and **German (de)**.
-   **Advanced NLP**: Uses `spaCy` for accurate lemmatization (finding the base form of words).
-   **German Compound Splitting**: Intelligently breaks down long German compound words into their components (e.g., "Donaudampfschifffahrtsgesellschaft" -> "Donau", "Dampf", "Schiff", "Fahrt", "Gesellschaft").
-   **Direct Anki Integration**: Automatically imports the generated cards into your Anki collection using the AnkiConnect add-on.

## How It Works

The workflow is simple and automated:

1.  **Prepare Input**: You provide text files (e.g., `text1.txt` for the source language, `text2.txt` for the translation).
2.  **Run the Script**: Execute a batch file (like `t_batch_de.dual.bat`) to start the process.
3.  **Text Processing**: `token_mix_combined.py` analyzes the text, extracts tokens or sentences, and creates a structured `.tsv` file.
4.  **Anki Import**: The `anki-csv-importer.py` script is automatically called to import the `.tsv` file into Anki, creating a new deck with your cards.

```
[Text Files] -> [LinguaCard Creator] -> [Generated TSV File] -> [Anki Importer] -> [New Anki Deck]
```

## Project Ecosystem

LinguaCard Creator is part of a larger ecosystem of tools designed to work together:

-   **LinguaCard Creator (This Project)**: The core engine for text processing and TSV file generation.
-   [**Anki Template (20241106211123-anki-template)**](https://github.com/user/repo-link) (*link placeholder*): A specialized Anki card template is **required** for the generated files to display correctly. It provides the feature-rich layout shown below.
-   [**Anki CSV Importer (20250401192017-anki-csv-importer)**](https://github.com/user/repo-link) (*link placeholder*): A standalone script that communicates with Anki via AnkiConnect to import the generated TSV files.

## The Anki Card Template

The generated TSV files are designed to be used with a specific, feature-rich Anki template named `basic-20240218092126`. This template organizes the information into a clean, interactive, and powerful layout for effective learning.

![Anki Card Preview](httpsis-is-a-placeholder-for-your-image-url/preview.png)
*(An example of a generated German vocabulary card using the template)*

**Template Features:**

*   **Interactive Collapsible Sections**: Information is grouped into sections like "Source", "Destination", and "AI". You can click on a header to reveal or hide the content, keeping the card uncluttered.
*   **Dynamic Fields**: Fields only appear if they contain data. For example, the "Wordlist" section won't show up if it's empty.
*   **Integrated Audio**: Supports both pre-recorded audio files and automatic text-to-speech (TTS) for words and sentences.
*   **Context Display**: Shows the sentence in its original context (previous and next sentences) to aid comprehension.
*   **Full Word List**: Displays all unique words (lemmas) found in the source sentence.
*   **Cloze Deletion Support**: Advanced support for creating "fill-in-the-blank" style cards from sentences.
*   **Multi-language Translation**: Dedicated sections for different languages (e.g., Ukrainian, English) to show parallel texts.

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
    pip install spacy "german-compound-splitter>=2.0.0"
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
    -   Make sure to change the `--note` parameter value to `"Basic 20240218092126"` to match the imported template name.

## Usage

1.  **Prepare your input files**:
    -   Place your source text in `in/text1.txt`. Each line should correspond to a sentence.
    -   If using `dual` or `triple` mode, place the corresponding translation(s) in `in/text2.txt` and `in/text3.txt`. The line numbers must match `text1.txt`.

    *Example for dual mode:*

    **in/text1.txt (German)**
    ```
    Das ist ein Beispiel.
    Ich lerne Deutsch.
    ```

    **in/text2.txt (English)**
    ```
    This is an example.
    I am learning German.
    ```

2.  **Ensure Anki is running** with the AnkiConnect add-on enabled.

3.  **Run a batch script**:
    Execute one of the provided `.bat` files to start the process. The filename indicates what it does: `t_batch_{language}.{mode}.bat`.

    -   **To create German vocabulary and sentence cards from two text files:**
        ```bash
        t_batch_de.dual.bat
        ```
    -   **To create English vocabulary cards from a single text file:**
        ```bash
        t_batch_en.single.bat
        ```

The script will run, generate a timestamped `.tsv` file in the `out/` directory, and then automatically call the importer. A new deck named after the generated file will appear in Anki.

## Advanced Usage

You can also run the scripts directly from the command line for more control. The main entry point is `t_starter.py`, which then calls `token_mix_combined.py`.

**Example:**
```bash
# Get German token cards in dual mode
python t_starter.py --language de --type token --mode dual

# Get English sentence cards in triple mode
python t_starter.py --language en --type sentence --mode triple
```

## Related Utilities

This project was developed alongside other useful tools. You might find them helpful:

-   `20250212113752-intellifilter`
-   `20250228230803-whisper`
-   `20250311224733-search-py`
-   `deep-translator`
-   `gTTS`
-   and many others.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
