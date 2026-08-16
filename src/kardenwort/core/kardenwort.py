import sys
import csv
import json
import argparse
from datetime import datetime
import os
import re
from contextlib import redirect_stdout
import io
import json
import tempfile
import atexit
import simplemma
from enum import Enum
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, fields
from typing import Optional, List, Any, Tuple, Dict, Literal, Union, Set, Iterator, Iterable
from types import SimpleNamespace
import configparser

try:
    from german_compound_splitter import comp_split
    GCS_AVAILABLE = True
except ImportError:
    GCS_AVAILABLE = False

# List to hold the paths of temporary files to be cleaned up on exit.
TEMP_FILES_TO_CLEANUP = []
nlp: Optional[Any] = None
simplemma_lang: Optional[str] = None

def _cleanup_temp_files():
    """Remove any temporary files created during execution."""
    for f_path in TEMP_FILES_TO_CLEANUP:
        try:
            os.remove(f_path)
        except OSError:
            pass  # Ignore errors if the file doesn't exist

# Register the cleanup function to be called upon script exit.
atexit.register(_cleanup_temp_files)

# Internal row data keys and mapping sources
KEY_LEMMA = "lemma"
KEY_SOURCE_WORD = "source_word"
KEY_RAW_SOURCE_WORD = "raw_source_word"
KEY_SOURCE_SENTENCE = "source_sentence"
KEY_SOURCE_CONTEXT_LEFT = "source_context_left"
KEY_SOURCE_CONTEXT_RIGHT = "source_context_right"
KEY_TARGET_SENTENCE = "target_sentence"
KEY_TARGET_CONTEXT_LEFT = "target_context_left"
KEY_TARGET_CONTEXT_RIGHT = "target_context_right"
KEY_TERTIARY_SENTENCE = "tertiary_sentence"
KEY_TERTIARY_CONTEXT_LEFT = "tertiary_context_left"
KEY_TERTIARY_CONTEXT_RIGHT = "tertiary_context_right"
KEY_WORDLIST = "wordlist"
KEY_CLOZE = "cloze"
KEY_SENTENCE_INDEX = "sentence_index"
KEY_DECK_NAME = "deck_name"
KEY_SUBTITLE_START_TIME = "subtitle_start_time"
KEY_CLASSIFICATIONS = "classifications"
KEY_CLASSIFICATION_CASE_SENSITIVE = "classification_case_sensitive"
KEY_TTS_SOURCE_PREFIX = "tts_source_"
KEY_TTS_DEST_PREFIX = "tts_dest_"

# Tabular & Anki Field Constants
FIELD_LEMMA = "Lemma"
FIELD_POS_TAG = "PosTag"
FIELD_QUOTATION = "Quotation"
FIELD_WORD_SOURCE = "WordSource"
FIELD_WORD_SOURCE2 = "WordSource2"
FIELD_WORD_SOURCE_INFLECTED_FORM = "WordSourceInflectedForm"
FIELD_WORD_SOURCE_INFLECTED_FORM2 = "WordSourceInflectedForm2"
FIELD_WORD_DESTINATION = "WordDestination"
FIELD_WORD_SOURCE_CONTEXT = "WordSourceContext"
FIELD_SENTENCE_SOURCE_CONTEXT_LEFT = "SentenceSourceContextLeft"
FIELD_SENTENCE_SOURCE = "SentenceSource"
FIELD_SENTENCE_SOURCE_CONTEXT_RIGHT = "SentenceSourceContextRight"
FIELD_SENTENCE_DESTINATION_CONTEXT_LEFT = "SentenceDestinationContextLeft"
FIELD_SENTENCE_DESTINATION = "SentenceDestination"
FIELD_SENTENCE_DESTINATION_CONTEXT_RIGHT = "SentenceDestinationContextRight"
FIELD_SENTENCE_DESTINATION2_CONTEXT_LEFT = "SentenceDestination2ContextLeft"
FIELD_SENTENCE_DESTINATION2 = "SentenceDestination2"
FIELD_SENTENCE_DESTINATION2_CONTEXT_RIGHT = "SentenceDestination2ContextRight"
FIELD_SENTENCE_SOURCE_WORDLIST = "SentenceSourceWordlist"
FIELD_SENTENCE_SOURCE_CLOZE = "SentenceSourceCloze"
FIELD_SENTENCE_SOURCE_REWRITE_AI_SENTENCE_SOURCE = "SentenceSourceRewriteAISentenceSource"
FIELD_SENTENCE_SOURCE_REWRITE_AI_SENTENCE_DESTINATION = "SentenceSourceRewriteAISentenceDestination"
FIELD_WORD_SOURCE_MORPHOLOGY_AI = "WordSourceMorphologyAI"
FIELD_NOTE = "Note"
FIELD_WORD_RUSSIAN = "WordRussian"
FIELD_WORD_UKRAINIAN = "WordUkrainian"
FIELD_WORD_ENGLISH = "WordEnglish"
FIELD_WORD_GERMAN = "WordGerman"
FIELD_WORD_SOURCE_MORPHEME_FIRST = "WordSourceMorphemeFirst"
FIELD_WORD_SOURCE_MORPHEME_FIRST_DEFINITION = "WordSourceMorphemeFirstDefinition"
FIELD_WORD_SOURCE_MORPHEME_SECOND = "WordSourceMorphemeSecond"
FIELD_WORD_SOURCE_MORPHEME_SECOND_DEFINITION = "WordSourceMorphemeSecondDefinition"
FIELD_WORD_SOURCE_MORPHEME_THIRD = "WordSourceMorphemeThird"
FIELD_WORD_SOURCE_MORPHEME_THIRD_DEFINITION = "WordSourceMorphemeThirdDefinition"
FIELD_WORD_SOURCE_MORPHEME_FOURTH = "WordSourceMorphemeFourth"
FIELD_WORD_SOURCE_MORPHEME_FOURTH_DEFINITION = "WordSourceMorphemeFourthDefinition"
FIELD_WORD_SOURCE_MORPHEME_FIFTH = "WordSourceMorphemeFifth"
FIELD_WORD_SOURCE_MORPHEME_FIFTH_DEFINITION = "WordSourceMorphemeFifthDefinition"
FIELD_WORD_SOURCE_IPA = "WordSourceIPA"
FIELD_WORD_SOURCE_SYNONYM_AI = "WordSourceSynonymAI"
FIELD_WORD_SOURCE_DEFINITION_AI_SENTENCE_SOURCE = "WordSourceDefinitionAISentenceSource"
FIELD_WORD_SOURCE_DEFINITION_AI_SENTENCE_DESTINATION = "WordSourceDefinitionAISentenceDestination"
FIELD_WORD_SOURCE_DEFINITION_FIRST = "WordSourceDefinitionFirst"
FIELD_WORD_SOURCE_DEFINITION_FIRST_CLIPPING = "WordSourceDefinitionFirstClipping"
FIELD_WORD_SOURCE_DEFINITION_SECOND = "WordSourceDefinitionSecond"
FIELD_WORD_DESTINATION_DEFINITION_FIRST = "WordDestinationDefinitionFirst"
FIELD_WORD_DESTINATION_DEFINITION_SECOND = "WordDestinationDefinitionSecond"
FIELD_WORD_SOURCE_AUDIO = "WordSourceAudio"
FIELD_SENTENCE_SOURCE_IPA = "SentenceSourceIPA"
FIELD_SENTENCE_SOURCE_AUDIO = "SentenceSourceAudio"
FIELD_IMAGE = "Image"
FIELD_WORD_SOURCE_CLOZE = "WordSourceCloze"
FIELD_WORD_SOURCE_CONTEXT_AI = "WordSourceContextAI"
FIELD_TEXT_SOURCE = "TextSource"
FIELD_TEXT_DESTINATION = "TextDestination"
FIELD_TEXT_SOURCE_URL = "TextSourceURL"
FIELD_SENTENCE_ENGLISH = "SentenceEnglish"
FIELD_SENTENCE_GERMAN = "SentenceGerman"
FIELD_SENTENCE_UKRAINIAN = "SentenceUkrainian"
FIELD_SENTENCE_RUSSIAN = "SentenceRussian"
FIELD_SOURCE = "Source"
FIELD_SOURCE_URL = "SourceURL"
FIELD_SEPARATOR_AUDIO = "SeparatorAudio"
FIELD_SOURCE_EN_GB = "Source-en-GB"
FIELD_SOURCE_EN_US = "Source-en-US"
FIELD_SOURCE_DE_DE = "Source-de-DE"
FIELD_SOURCE_UK_UA = "Source-uk-UA"
FIELD_SOURCE_RU_RU = "Source-ru-RU"
FIELD_DESTINATION_EN_GB = "Destination-en-GB"
FIELD_DESTINATION_EN_US = "Destination-en-US"
FIELD_DESTINATION_DE_DE = "Destination-de-DE"
FIELD_DESTINATION_UK_UA = "Destination-uk-UA"
FIELD_DESTINATION_RU_RU = "Destination-ru-RU"
FIELD_OVERLAPPING = "Overlapping"
FIELD_TOGGLE_ALWAYS_EMPTY_FIELD = "ToggleAlwaysEmptyField"
FIELD_NOTE_ID = "Note ID"
FIELD_AM_ALL_MORPHS = "am-all-morphs"
FIELD_AM_ALL_MORPHS_COUNT = "am-all-morphs-count"
FIELD_AM_UNKNOWN_MORPHS = "am-unknown-morphs"
FIELD_AM_UNKNOWN_MORPHS_COUNT = "am-unknown-morphs-count"
FIELD_AM_HIGHLIGHTED = "am-highlighted"
FIELD_AM_SCORE = "am-score"
FIELD_AM_SCORE_TERMS = "am-score-terms"
FIELD_AM_STUDY_MORPHS = "am-study-morphs"
FIELD_SENTENCE_SOURCE_INDEX = "SentenceSourceIndex"
FIELD_DECK = "Deck"
FIELD_LEITNER_BOX = "LeitnerBox"
FIELD_LEITNER_DUE = "LeitnerDue"
FIELD_DESK_SELECTED = "DeskSelected"
FIELD_CLASSIFICATION_OXFORD = "ClassificationOxford"
FIELD_CLASSIFICATION_GOETHE = "ClassificationGoethe"
FIELD_WORD_DESTINATION_INFLECTED_FORM = "WordDestinationInflectedForm"
FIELD_WORD_SOURCE_AI = "WordSourceAI"
FIELD_WORD_SOURCE_INFLECTED_FORM_AI = "WordSourceInflectedFormAI"

# Standard 90-field default Anki baseline tuple
DEFAULT_ANKI_HEADER = (
    FIELD_QUOTATION, FIELD_WORD_SOURCE, FIELD_WORD_SOURCE2, FIELD_WORD_SOURCE_INFLECTED_FORM,
    FIELD_WORD_SOURCE_INFLECTED_FORM2, FIELD_WORD_DESTINATION, FIELD_WORD_DESTINATION_INFLECTED_FORM,
    FIELD_WORD_SOURCE_CONTEXT, FIELD_SENTENCE_SOURCE_CONTEXT_LEFT, FIELD_SENTENCE_SOURCE,
    FIELD_SENTENCE_SOURCE_CONTEXT_RIGHT, FIELD_SENTENCE_DESTINATION_CONTEXT_LEFT,
    FIELD_SENTENCE_DESTINATION, FIELD_SENTENCE_DESTINATION_CONTEXT_RIGHT,
    FIELD_SENTENCE_DESTINATION2_CONTEXT_LEFT, FIELD_SENTENCE_DESTINATION2,
    FIELD_SENTENCE_DESTINATION2_CONTEXT_RIGHT, FIELD_SENTENCE_SOURCE_WORDLIST,
    FIELD_SENTENCE_SOURCE_CLOZE, FIELD_SENTENCE_SOURCE_REWRITE_AI_SENTENCE_SOURCE,
    FIELD_SENTENCE_SOURCE_REWRITE_AI_SENTENCE_DESTINATION, FIELD_WORD_SOURCE_MORPHOLOGY_AI,
    FIELD_NOTE, FIELD_WORD_RUSSIAN, FIELD_WORD_UKRAINIAN, FIELD_WORD_ENGLISH, FIELD_WORD_GERMAN,
    FIELD_WORD_SOURCE_MORPHEME_FIRST, FIELD_WORD_SOURCE_MORPHEME_FIRST_DEFINITION,
    FIELD_WORD_SOURCE_MORPHEME_SECOND, FIELD_WORD_SOURCE_MORPHEME_SECOND_DEFINITION,
    FIELD_WORD_SOURCE_MORPHEME_THIRD, FIELD_WORD_SOURCE_MORPHEME_THIRD_DEFINITION,
    FIELD_WORD_SOURCE_MORPHEME_FOURTH, FIELD_WORD_SOURCE_MORPHEME_FOURTH_DEFINITION,
    FIELD_WORD_SOURCE_MORPHEME_FIFTH, FIELD_WORD_SOURCE_MORPHEME_FIFTH_DEFINITION,
    FIELD_WORD_SOURCE_IPA, FIELD_WORD_SOURCE_SYNONYM_AI, FIELD_WORD_SOURCE_DEFINITION_AI_SENTENCE_SOURCE,
    FIELD_WORD_SOURCE_DEFINITION_AI_SENTENCE_DESTINATION, FIELD_WORD_SOURCE_DEFINITION_FIRST,
    FIELD_WORD_SOURCE_DEFINITION_FIRST_CLIPPING, FIELD_WORD_SOURCE_DEFINITION_SECOND,
    FIELD_WORD_DESTINATION_DEFINITION_FIRST, FIELD_WORD_DESTINATION_DEFINITION_SECOND,
    FIELD_WORD_SOURCE_AUDIO, FIELD_SENTENCE_SOURCE_IPA, FIELD_SENTENCE_SOURCE_AUDIO, FIELD_IMAGE,
    FIELD_WORD_SOURCE_CLOZE, FIELD_WORD_SOURCE_CONTEXT_AI, FIELD_TEXT_SOURCE, FIELD_TEXT_DESTINATION,
    FIELD_TEXT_SOURCE_URL, FIELD_SENTENCE_ENGLISH, FIELD_SENTENCE_GERMAN, FIELD_SENTENCE_UKRAINIAN,
    FIELD_SENTENCE_RUSSIAN, FIELD_SOURCE, FIELD_SOURCE_URL, FIELD_SEPARATOR_AUDIO, FIELD_SOURCE_EN_GB,
    FIELD_SOURCE_EN_US, FIELD_SOURCE_DE_DE, FIELD_SOURCE_UK_UA, FIELD_SOURCE_RU_RU,
    FIELD_DESTINATION_EN_GB, FIELD_DESTINATION_EN_US, FIELD_DESTINATION_DE_DE,
    FIELD_DESTINATION_UK_UA, FIELD_DESTINATION_RU_RU, FIELD_OVERLAPPING,
    FIELD_TOGGLE_ALWAYS_EMPTY_FIELD, FIELD_NOTE_ID, FIELD_AM_ALL_MORPHS, FIELD_AM_ALL_MORPHS_COUNT,
    FIELD_AM_UNKNOWN_MORPHS, FIELD_AM_UNKNOWN_MORPHS_COUNT, FIELD_AM_HIGHLIGHTED,
    FIELD_AM_SCORE, FIELD_AM_SCORE_TERMS, FIELD_AM_STUDY_MORPHS, FIELD_SENTENCE_SOURCE_INDEX,
    FIELD_DECK, FIELD_LEITNER_BOX, FIELD_LEITNER_DUE, FIELD_DESK_SELECTED,
    FIELD_CLASSIFICATION_OXFORD, FIELD_CLASSIFICATION_GOETHE
)

@dataclass(frozen=True)
class GCSConfig:
    de_gcs: bool = False
    de_gcs_add_parts_to_wordlist: bool = False
    de_gcs_pos_tags: Tuple[str, ...] = ("NN", "NOUN", "N")
    de_fix_genitive: bool = False
    de_gcs_mask_unknown_parts: bool = False
    de_gcs_preserve_compound_word: bool = False
    de_gcs_skip_merge_fractions: bool = False
    de_gcs_only_nouns: bool = True
    de_gcs_combine_noun_modes: bool = False
    de_gcs_part_singularization: Literal["only-nouns", "all", "none"] = "only-nouns"

    @classmethod
    def from_args(cls, args: Any) -> "GCSConfig":
        tags = getattr(args, "de_gcs_pos_tags", ["NN", "NOUN", "N"])
        if isinstance(tags, list):
            tags = tuple(tags)
        return cls(
            de_gcs=getattr(args, "de_gcs", False),
            de_gcs_add_parts_to_wordlist=getattr(args, "de_gcs_add_parts_to_wordlist", False),
            de_gcs_pos_tags=tags,
            de_fix_genitive=getattr(args, "de_fix_genitive", False),
            de_gcs_mask_unknown_parts=getattr(args, "de_gcs_mask_unknown_parts", False),
            de_gcs_preserve_compound_word=getattr(args, "de_gcs_preserve_compound_word", False),
            de_gcs_skip_merge_fractions=getattr(args, "de_gcs_skip_merge_fractions", False),
            de_gcs_only_nouns=getattr(args, "de_gcs_only_nouns", True),
            de_gcs_combine_noun_modes=getattr(args, "de_gcs_combine_noun_modes", False),
            de_gcs_part_singularization=getattr(args, "de_gcs_part_singularization", "only-nouns")
        )

    @classmethod
    def from_kwargs(cls, **kwargs: Any) -> "GCSConfig":
        valid_fields = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in kwargs.items() if k in valid_fields}
        if "de_gcs_pos_tags" in filtered and isinstance(filtered["de_gcs_pos_tags"], list):
            filtered["de_gcs_pos_tags"] = tuple(filtered["de_gcs_pos_tags"])
        return cls(**filtered)

@dataclass(frozen=True)
class AnkiMappingConfig:
    anki_markdown_decks: bool = False
    anki_create_subdecks: bool = False
    anki_parent_deck: Optional[str] = None
    anki_deck_content: Union[bool, List[str], Tuple[str, ...]] = False
    anki_sentence_subdecks: bool = False
    anki_context_use_br: bool = False
    wordlist_use_br: bool = False
    add_header: bool = True
    add_wordlist_col: bool = True
    header: Tuple[str, ...] = DEFAULT_ANKI_HEADER
    field_mapping: Optional[Dict[str, str]] = None

    @classmethod
    def from_args(cls, args: Any, header_override: Optional[List[str]] = None, field_mapping_override: Optional[Dict[str, str]] = None) -> "AnkiMappingConfig":
        hdr = tuple(header_override) if header_override else DEFAULT_ANKI_HEADER
        return cls(
            anki_markdown_decks=getattr(args, "anki_markdown_decks", False),
            anki_create_subdecks=getattr(args, "anki_create_subdecks", False),
            anki_parent_deck=getattr(args, "anki_parent_deck", None),
            anki_deck_content=getattr(args, "anki_deck_content", False),
            anki_sentence_subdecks=getattr(args, "anki_sentence_subdecks", False),
            anki_context_use_br=getattr(args, "anki_context_use_br", False),
            wordlist_use_br=getattr(args, "wordlist_use_br", False),
            add_header=getattr(args, "add_header", True),
            add_wordlist_col=getattr(args, "add_wordlist_col", True),
            header=hdr,
            field_mapping=field_mapping_override
        )

    @classmethod
    def from_ini(cls, path: str, mode: str = "word") -> "AnkiMappingConfig":
        parser = configparser.ConfigParser(allow_no_value=True)
        parser.optionxform = str
        parser.read(path, encoding='utf-8')
        if "anki_fields" in parser:
            raw_fields_dict = dict(parser.items('anki_fields'))
            try:
                [int(k) for k in raw_fields_dict.keys()]
                sorted_keys = sorted(raw_fields_dict.keys(), key=lambda x: int(x))
                header = [raw_fields_dict[k] for k in sorted_keys]
            except (ValueError, TypeError):
                header = list(raw_fields_dict.keys())
        else:
            header = list(DEFAULT_ANKI_HEADER)
            
        mapping_section = f"anki_field_mapping.{mode}"
        field_mapping = dict(parser[mapping_section]) if mapping_section in parser else None
        return cls(header=tuple(header), field_mapping=field_mapping)

@dataclass(frozen=True)
class NLPModelConfig:
    language: str = "de"
    use_simplemma_correction: bool = False
    simplemma_smart_fallback: bool = False
    simplemma_after_spacy: bool = False
    simplemma_pos_aware: bool = False

    @classmethod
    def from_args(cls, args: Any) -> "NLPModelConfig":
        return cls(
            language=getattr(args, "language", "de"),
            use_simplemma_correction=getattr(args, "use_simplemma_correction", False),
            simplemma_smart_fallback=getattr(args, "simplemma_smart_fallback", False),
            simplemma_after_spacy=getattr(args, "simplemma_after_spacy", False),
            simplemma_pos_aware=getattr(args, "simplemma_pos_aware", False)
        )

@dataclass(frozen=True)
class ExtractionConfig:
    language: str = "de"
    deduplication_scope: str = "global"
    combine_source_words: bool = False
    combine_source_words_order: str = "contractions_first"
    combine_source_words_prefer_lowercase: bool = True
    prefer_shortest_form: bool = False
    preserve_composite_tokens: bool = False
    strip_headers: Optional[Union[List[str], Tuple[str, ...], str, bool]] = None
    de_force_noun_capitalization: bool = True
    force_proper_noun_capitalization: bool = True
    apostrophe_chars: str = "', ’, ‘, `, ´, ʼ"
    type: str = "word"
    tts_destination_lang: Optional[str] = None
    tts_tertiary_lang: Optional[str] = None
    classification_case_sensitive: bool = False
    _extra: Optional[Dict[str, Any]] = field(default=None, repr=False, compare=False)

    def __getattr__(self, item: str) -> Any:
        if self._extra and item in self._extra:
            return self._extra[item]
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{item}'")

    @classmethod
    def from_args(cls, args: Any) -> "ExtractionConfig":
        raw_dict = vars(args) if hasattr(args, "__dict__") else dict(getattr(args, "_extra", {}) or {})
        if not raw_dict and isinstance(args, dict):
            raw_dict = args
        valid_field_names = {f.name for f in fields(cls) if f.name != "_extra"}
        explicit_kwargs = {}
        extra_kwargs = {}
        for k, v in raw_dict.items():
            if k in valid_field_names:
                explicit_kwargs[k] = v
            else:
                extra_kwargs[k] = v
        for fname in valid_field_names:
            if fname not in explicit_kwargs and hasattr(args, fname):
                explicit_kwargs[fname] = getattr(args, fname)
        return cls(**explicit_kwargs, _extra=extra_kwargs if extra_kwargs else None)

ExecutionStrategyConfig = ExtractionConfig

class ExecutionContext:
    """Lifecycle resource manager encapsulating NLP model initialization and temporary files."""
    def __init__(self, nlp_model: Optional[object] = None, simplemma_lang: Optional[str] = None, gcs_automaton: Optional[object] = None, de_dictionary: Optional[Union[Set[str], Dict[str, str], object]] = None):
        self.nlp = nlp_model
        self.simplemma_lang = simplemma_lang
        self.gcs_automaton = gcs_automaton
        self.de_dictionary = de_dictionary
        self.temp_files: List[str] = []
        self._cancelled: bool = False

    def cancel(self) -> None:
        """Sets the cancellation signal to abort ongoing operations cleanly."""
        self._cancelled = True

    def is_cancelled(self) -> bool:
        """Returns True if cancellation has been requested, otherwise False."""
        return self._cancelled

    def add_temp_file(self, file_path: str) -> None:
        """Registers a temporary file path for cleanup upon execution completion."""
        self.temp_files.append(str(file_path))

    def cleanup_temp_files(self) -> None:
        """Removes all temporary files registered within this context."""
        for f_path in list(self.temp_files):
            try:
                os.remove(f_path)
                if f_path in self.temp_files:
                    self.temp_files.remove(f_path)
            except OSError:
                pass

    def close(self) -> None:
        self.cleanup_temp_files()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class OperationalMode(str, Enum):
    """Enumeration of explicit operational routing modes for document processing workflows."""
    PARALLEL_TEXTS = "PARALLEL_TEXTS"
    SINGLE_TEXT = "SINGLE_TEXT"
    PARALLEL_SENTENCES = "PARALLEL_SENTENCES"
    LEMMAS_PER_LINE = "LEMMAS_PER_LINE"


@dataclass
class TabularRecord:
    """Represents a decoupled record unit (table row or line) yielded by an OperationalStrategy."""
    fields: Optional[List[Any]] = None
    row_data: Optional[Dict[str, Any]] = None
    raw_line: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class OperationalStrategy(ABC):
    """Abstract base class for stateless operational strategies decoupling token transformation from file I/O."""
    @abstractmethod
    def execute(self, config: ExtractionConfig, context: ExecutionContext) -> Iterator[TabularRecord]:
        """Execute the transformation strategy yielding iterable tabular records."""
        pass

    def _derive_deck_prefixes(self, config: ExtractionConfig) -> Tuple[str, str]:
        """Centralized derivation of subdeck name and root deck prefix without filesystem I/O."""
        out_path = getattr(config, 'output_file_path', None)
        sub_deck_name = getattr(config, 'sub_deck_name', "")
        root_deck_prefix = getattr(config, 'root_deck_prefix', "")
        if out_path and not sub_deck_name:
            filename_part = str(out_path).replace('\\', '/').split('/')[-1]
            sub_deck_name = filename_part.rsplit('.', 1)[0]
        if not root_deck_prefix and sub_deck_name:
            root_deck_prefix = re.sub(r'\.(word|sentence)', '', sub_deck_name)
        return sub_deck_name, root_deck_prefix


class TSVWriter:
    """Dedicated persistence utility to handle stream output serialization independently from calculation loops."""
    def __init__(
        self,
        output_file_path: Optional[str] = None,
        header: Optional[List[Any]] = None,
        add_header: bool = True,
        delimiter: str = "\t",
        args: Any = None,
        source_text_content: Optional[str] = None,
        target_text_path: Optional[str] = None,
        tertiary_text_path: Optional[str] = None,
        target_text_content: Optional[str] = None,
        tertiary_text_content: Optional[str] = None,
        subdeck_content_map: Optional[Dict[str, Any]] = None,
        stdout_print_output_basename: bool = False
    ):
        self.output_file_path = output_file_path
        self.header = header
        self.add_header = add_header
        self.delimiter = delimiter
        self.args = args
        self.source_text_content = source_text_content
        self.target_text_path = target_text_path
        self.tertiary_text_path = tertiary_text_path
        self.target_text_content = target_text_content
        self.tertiary_text_content = tertiary_text_content
        self.subdeck_content_map = subdeck_content_map
        self.stdout_print_output_basename = stdout_print_output_basename

    def write(self, records: Iterable[TabularRecord]) -> Optional[str]:
        """Serializes iterable records to disk and generates companion deck metadata files."""
        if not self.output_file_path and not getattr(self.args, 'structured_output', False):
            for _ in records:
                pass
            return None

        is_jsonl = getattr(self.args, 'structured_output', False)
        import contextlib
        import io
        import json
        import sys
        
        file_mgr = open(self.output_file_path, "w", newline="", encoding="utf-8") if self.output_file_path else contextlib.nullcontext(sys.stdout)
        
        with file_mgr as tsvfile:
            writer = None
            if not is_jsonl:
                writer = csv.writer(tsvfile, delimiter=self.delimiter)
                if self.header and self.add_header:
                    writer.writerow(self.header)

            for record in records:
                if record.metadata and 'subdeck_content_map' in record.metadata:
                    self.subdeck_content_map = record.metadata['subdeck_content_map']
                
                if is_jsonl:
                    if record.fields is not None and self.header:
                        record_dict = dict(zip(self.header, record.fields))
                        print(json.dumps(record_dict, ensure_ascii=False), file=sys.stdout)
                    elif record.row_data is not None:
                        print(json.dumps(record.row_data, ensure_ascii=False), file=sys.stdout)
                    elif record.raw_line is not None:
                        print(json.dumps({"raw_line": record.raw_line}, ensure_ascii=False), file=sys.stdout)
                    sys.stdout.flush()
                else:
                    if record.fields is not None:
                        writer.writerow(record.fields)
                    elif record.raw_line is not None:
                        tsvfile.write(record.raw_line + "\n")

        if self.args and self.source_text_content is not None and not getattr(self.args, 'lemmas_per_line', False):
            tgt_content = self.target_text_content
            if tgt_content is None and self.target_text_path and os.path.exists(self.target_text_path):
                with open(self.target_text_path, "r", encoding="utf-8") as f:
                    tgt_content = f.read()

            tert_content = self.tertiary_text_content
            if tert_content is None and self.tertiary_text_path and os.path.exists(self.tertiary_text_path):
                with open(self.tertiary_text_path, "r", encoding="utf-8") as f:
                    tert_content = f.read()

            _write_deck_metadata(
                self.args,
                self.output_file_path,
                self.source_text_content,
                tgt_content,
                tert_content,
                self.subdeck_content_map
            )

        return self.output_file_path






def _strip_markdown_header(line):
    """Removes Markdown header prefixes (#, ##, etc.) from a line."""
    match = re.match(r'^(#+)\s+(.*)', line.strip())
    return match.group(2).strip() if match else line

def _format_gcs_component_case(component):
    if not component or len(component) < 2:
        return component
    return component[0] + component[1:].lower()

def load_dictionary(file_path):
    dictionary = set()
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                dictionary.add(line.strip())
    except FileNotFoundError:
        print(f"Dictionary file not found: {file_path}", file=sys.stderr)
    except Exception as e:
        print(f"Error reading dictionary file {file_path}: {e}", file=sys.stderr)
    return dictionary

def parse_prefix_and_path(raw_val):
    """
    Parses a raw string of prefix:path or just path.
    Avoids interpreting Windows drive letters (like C:) as prefixes.
    """
    raw_val = raw_val.strip()
    if ":" in raw_val:
        parts = raw_val.split(":", 1)
        prefix = parts[0].strip()
        if len(prefix) == 1 and prefix.isalpha():
            return "", raw_val
        if len(prefix) <= 5 and "/" not in prefix and "\\" not in prefix:
            return prefix, parts[1].strip()
    return "", raw_val

class CaseAwareClassificationDict(dict):
    def __init__(self, exact_dict, lower_dict):
        super().__init__(exact_dict)
        self.lower_dict = lower_dict

    def __getitem__(self, key):
        try:
            return super().__getitem__(key)
        except KeyError:
            return self.lower_dict[key.lower()]

    def __contains__(self, key):
        return super().__contains__(key) or key.lower() in self.lower_dict

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

def load_classification_dictionaries(classify_args, case_sensitive=True):
    """
    Parses --classify name=path arguments, loads TSV files, skipping headers,
    and returns a nested dict of CaseAwareClassificationDicts.
    """
    classifications = {}
    if not classify_args:
        return classifications
    
    for arg in classify_args:
        if "=" not in arg:
            print(f"Warning: Invalid --classify format '{arg}'. Expected name=path", file=sys.stderr)
            continue
        
        name, prefix_path = arg.split("=", 1)
        name = name.strip()
        prefix_path = prefix_path.strip()
        
        if name not in classifications:
            classifications[name] = ( {}, {} ) # (exact_dict, lower_dict)
            
        prefix, path = parse_prefix_and_path(prefix_path)

        try:
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.reader(f, delimiter="\t")
                first_row = True
                is_oxford = "oxford" in path.lower()
                for row in reader:
                    if not row:
                        continue
                    if first_row:
                        first_row = False
                        if row[0].lower() in ['word', 'lemma', 'headword', 'text']:
                            continue
                    
                    if len(row) >= 1:
                        raw_lemma = row[0].strip()
                        if not case_sensitive:
                            raw_lemma = raw_lemma.lower()
                        
                        val = ""
                        if is_oxford:
                            for cell in reversed(row[1:]):
                                cell_str = cell.strip()
                                if cell_str:
                                    levels = re.findall(r"\b[a-cA-C][1-2]\b", cell_str)
                                    if levels:
                                        val = ", ".join(levels).upper()
                                        break
                            if not val:
                                continue
                        else:
                            for cell in reversed(row[1:]):
                                cell_str = cell.strip()
                                if cell_str:
                                    val = cell_str
                                    break
                            if not val:
                                val = "1"
                        
                        if prefix:
                            val = f"{prefix}:{val}"
                            
                        # Split by comma to support lists of synonyms/variants like "a, an"
                        # Strip any parenthetical annotations like "(money)" or "(not heavy)"
                        lemmas = [re.sub(r"\(.*?\)", "", x).strip() for x in raw_lemma.split(",")]
                        lemmas = [x for x in lemmas if x]
                        
                        exact_dict, lower_dict = classifications[name]
                        for lemma in lemmas:
                            # 1. Exact case dictionary
                            if lemma in exact_dict:
                                if exact_dict[lemma].startswith("3k:"):
                                    continue
                            exact_dict[lemma] = val
                            
                            # 2. Lowercase fallback dictionary
                            lemma_lower = lemma.lower()
                            if lemma_lower in lower_dict:
                                if lower_dict[lemma_lower].startswith("3k:"):
                                    continue
                            lower_dict[lemma_lower] = val
        except FileNotFoundError:
            print(f"Classification dictionary file not found: {path}", file=sys.stderr)
        except Exception as e:
            print(f"Error reading classification dictionary file {path}: {e}", file=sys.stderr)
            
    # Wrap in CaseAwareClassificationDict
    wrapped_classifications = {}
    for name, (exact_dict, lower_dict) in classifications.items():
        wrapped_classifications[name] = CaseAwareClassificationDict(exact_dict, lower_dict)
    return wrapped_classifications

def load_lemma_override_rules(file_path):
    override_rules = {
        'priority1': {},
        'priority1_regex': [],
        'priority2': {},
        'priority2_regex': [],
        'priority3': {}
    }
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter="\t")
            for i, row in enumerate(reader):
                if not row or row[0].startswith('#'):
                    continue

                if len(row) < 3:
                    print(f"Warning: Skipping malformed line {i+1} in {file_path}: expected at least 3 columns.", file=sys.stderr)
                    continue
                
                spacy_lemma_to_match = row[0].strip()
                source_word_to_match_raw = row[1]
                target_lemma = row[2].strip()

                context_condition = None
                if len(row) > 3 and row[3]:
                    context_condition_raw = row[3]
                    if context_condition_raw.startswith('regex:'):
                        context_condition = context_condition_raw
                    else:
                        context_condition = context_condition_raw.strip()

                if not target_lemma or (not spacy_lemma_to_match and not source_word_to_match_raw.strip()):
                    print(f"Warning: Skipping invalid rule on line {i+1} in {file_path}: Target_Lemma (col 3) and at least one of Result_Lemma (col 1) or Original_Word (col 2) must be set.", file=sys.stderr)
                    continue

                override_rule = (target_lemma, context_condition)

                is_source_word_regex = source_word_to_match_raw.startswith('regex:')
                source_word_to_match = source_word_to_match_raw.strip()

                if spacy_lemma_to_match and source_word_to_match:
                    if is_source_word_regex:
                        pattern = source_word_to_match_raw[6:]
                        override_rules['priority1_regex'].append((spacy_lemma_to_match, pattern, override_rule))
                    else:
                        key = (spacy_lemma_to_match, source_word_to_match)
                        if key not in override_rules['priority1']:
                            override_rules['priority1'][key] = []
                        override_rules['priority1'][key].append(override_rule)
                
                elif source_word_to_match:
                    if is_source_word_regex:
                        pattern = source_word_to_match_raw[6:]
                        override_rules['priority2_regex'].append((pattern, override_rule))
                    else:
                        key = source_word_to_match
                        if key not in override_rules['priority2']:
                            override_rules['priority2'][key] = []
                        override_rules['priority2'][key].append(override_rule)
                
                elif spacy_lemma_to_match:
                    key = spacy_lemma_to_match
                    if key not in override_rules['priority3']:
                        override_rules['priority3'][key] = []
                    override_rules['priority3'][key].append(override_rule)

    except FileNotFoundError:
        print(f"Lemma override file not found: {file_path}", file=sys.stderr)
    except Exception as e:
        print(f"Error reading lemma override file {file_path}: {e}", file=sys.stderr)
    return override_rules

def load_token_mappings(file_paths, case_sensitive=False, normalize_apostrophes=True, normalize_spaces=True):
    mappings = {}
    for file_path in file_paths:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f, delimiter="\t")
                for i, row in enumerate(reader):
                    if not row or row[0].startswith('#'):
                        continue
                    if len(row) < 2:
                        continue
                    
                    source_word = row[0].strip()
                    if normalize_apostrophes:
                        source_word = source_word.replace('’', "'").replace('‘', "'").replace('`', "'")
                    if normalize_spaces:
                        source_word = re.sub(r'\s+', '', source_word)
                        
                    if not case_sensitive:
                        source_word = source_word.lower()
                    
                    target_tokens = [t.strip() for t in row[1:] if t.strip()]
                    mappings[source_word] = target_tokens
        except FileNotFoundError:
            print(f"Warning: Token mapping file not found: {file_path}", file=sys.stderr)
        except Exception as e:
            print(f"Error reading token mapping file {file_path}: {e}", file=sys.stderr)
    return mappings

def is_complex_inflected_form(form: str, apostrophe_chars: Optional[Union[str, Tuple[str, ...], List[str], Set[str]]] = None) -> bool:
    if apostrophe_chars:
        if isinstance(apostrophe_chars, str):
            apo_list = [c.strip().strip("'").strip('"') for c in apostrophe_chars.split(',') if c.strip()]
            if any(c in form for c in apo_list if c):
                return True
        elif hasattr(apostrophe_chars, '__iter__'):
            if any(c in form for c in apostrophe_chars):
                return True
    if any(c in form for c in ("'", "’", "‘", "`", "´", "ʼ")):
        return True
    if '-' in form or ' ' in form:
        return True
    if len(form) >= 2 and form.isupper():
        return True
    return any(not c.isalnum() for c in form)

def sort_inflected_forms(
    forms: List[str],
    apostrophe_chars: Optional[Union[str, ExtractionConfig, argparse.Namespace, SimpleNamespace, object]] = None,
    order: str = 'contractions_first',
    prefer_lowercase: bool = True,
    config: Optional[Union[ExtractionConfig, argparse.Namespace, SimpleNamespace, object]] = None
) -> List[str]:
    target = config if config is not None else apostrophe_chars
    if isinstance(target, (ExtractionConfig, argparse.Namespace, SimpleNamespace)) or (hasattr(target, 'combine_source_words_order') and not isinstance(target, str)):
        cfg = ExtractionConfig.from_args(target) if not isinstance(target, ExtractionConfig) else target
        apostrophe_chars = cfg.apostrophe_chars
        order = getattr(cfg, 'combine_source_words_order', order)
        prefer_lowercase = getattr(cfg, 'combine_source_words_prefer_lowercase', prefer_lowercase)
    elif apostrophe_chars is None and config is not None and hasattr(config, 'apostrophe_chars'):
        apostrophe_chars = config.apostrophe_chars

    unique_forms_dict = {}
    for f in forms:
        f_clean = f.strip()
        if not f_clean:
            continue
            
        if prefer_lowercase:
            f_lower = f_clean.lower()
            if f_lower not in unique_forms_dict:
                unique_forms_dict[f_lower] = f_clean
            elif f_clean == f_lower:
                # If we have an uppercase version, override it with the lowercase version!
                unique_forms_dict[f_lower] = f_clean
        else:
            if f_clean not in unique_forms_dict:
                unique_forms_dict[f_clean] = f_clean

    unique_forms = list(unique_forms_dict.values())
    if order == 'contractions_first':
        unique_forms.sort(key=lambda f: (not is_complex_inflected_form(f, apostrophe_chars), -len(f), f.lower()))
    elif order == 'alphabetical':
        unique_forms.sort(key=lambda f: f.lower())
    return unique_forms


def find_token_mappings_in_text(sentence_text, doc, token_mappings, args):
    if not getattr(args, 'token_mappings_enabled', False) or not token_mappings:
        return [], []
        
    mapped_tokens = set()
    results = {} # key: start_token_i, value: match dict
    
    for start_i in range(len(doc)):
        if start_i in mapped_tokens:
            continue
            
        best_match = None
        best_match_end_i = -1
        
        current_text = ""
        for end_i in range(start_i, min(start_i + 5, len(doc))):
            current_text += doc[end_i].text + doc[end_i].whitespace_
            
            candidate = current_text.strip()
            if getattr(args, 'token_mappings_normalize_apostrophes', True):
                candidate = candidate.replace('’', "'").replace('‘', "'").replace('`', "'")
            if getattr(args, 'token_mappings_normalize_spaces', True):
                candidate = re.sub(r'\s+', '', candidate)
            if not getattr(args, 'token_mappings_case_sensitive', False):
                candidate = candidate.lower()
                
            if candidate in token_mappings:
                is_valid = True
                if getattr(args, 'token_mappings_enable_context_disambiguation', True) and len(candidate) <= 2 and candidate.endswith('.'):
                    if end_i + 1 < len(doc):
                        next_tok = doc[end_i+1]
                        if next_tok.text and (next_tok.text[0].isupper() or next_tok.text in ['.', '!', '?']):
                            is_valid = False
                            
                if is_valid:
                    best_match = token_mappings[candidate]
                    best_match_end_i = end_i
                
        if best_match:
            source_word_form = sentence_text[doc[start_i].idx : doc[best_match_end_i].idx + len(doc[best_match_end_i].text)]
            results[start_i] = {
                'start_token_i': start_i,
                'end_token_i': best_match_end_i,
                'source_word': source_word_form,
                'lemmas': best_match
            }
            for i in range(start_i, best_match_end_i + 1):
                mapped_tokens.add(i)
                
    return results, mapped_tokens

def find_matching_override_in_context(rules, context_sentence):
    if not rules:
        return None
    rules_with_context = [r for r in rules if r[1]]
    rule_without_context = next((r for r in rules if not r[1]), None)
    
    for overridden_lemma, context_condition in rules_with_context:
        if context_condition:
            if context_condition.startswith('regex:'):
                context_regex_pattern = context_condition[6:]
                try:
                    if re.search(context_regex_pattern, context_sentence):
                        return overridden_lemma
                except re.error as e:
                    print(f"Warning: Invalid regex in override rule: '{context_regex_pattern}'. Error: {e}", file=sys.stderr)
            else:
                if context_condition in context_sentence:
                    return overridden_lemma
            
    if rule_without_context:
        return rule_without_context[0]
        
    return None

def get_overridden_lemma_for_word(initial_lemma, original_word, override_rules, context_sentence):
    if not override_rules:
        return initial_lemma
    priority1_rules = override_rules.get('priority1', {}).get((initial_lemma, original_word))
    matched_lemma1 = find_matching_override_in_context(priority1_rules, context_sentence)
    if matched_lemma1 is not None:
        return matched_lemma1

    for spacy_lemma_condition, source_word_regex, override_rule in override_rules.get('priority1_regex', []):
        if spacy_lemma_condition == initial_lemma:
            try:
                if re.fullmatch(source_word_regex, original_word):
                    matched_lemma_from_regex1 = find_matching_override_in_context([override_rule], context_sentence)
                    if matched_lemma_from_regex1 is not None:
                        return matched_lemma_from_regex1
            except re.error as e:
                print(f"Warning: Invalid regex original word pattern: '{source_word_regex}'. Error: {e}", file=sys.stderr)

    priority2_rules = override_rules.get('priority2', {}).get(original_word)
    matched_lemma2 = find_matching_override_in_context(priority2_rules, context_sentence)
    if matched_lemma2 is not None:
        return matched_lemma2

    for source_word_regex, override_rule in override_rules.get('priority2_regex', []):
        try:
            if re.fullmatch(source_word_regex, original_word):
                matched_lemma_from_regex2 = find_matching_override_in_context([override_rule], context_sentence)
                if matched_lemma_from_regex2 is not None:
                    return matched_lemma_from_regex2
        except re.error as e:
            print(f"Warning: Invalid regex original word pattern: '{source_word_regex}'. Error: {e}", file=sys.stderr)

    priority3_rules = override_rules.get('priority3', {}).get(initial_lemma)
    matched_lemma3 = find_matching_override_in_context(priority3_rules, context_sentence)
    if matched_lemma3 is not None:
        return matched_lemma3
            
    return initial_lemma

def get_overridden_lemma_for_compound_part(initial_lemma, part, original_word, override_rules, context_sentence):
    if not override_rules:
        return initial_lemma
    priority1_rules = override_rules.get('priority1', {}).get((initial_lemma, original_word))
    matched_lemma1 = find_matching_override_in_context(priority1_rules, context_sentence)
    if matched_lemma1 is not None:
        return matched_lemma1

    for spacy_lemma_condition, source_word_regex, override_rule in override_rules.get('priority1_regex', []):
        if spacy_lemma_condition == initial_lemma:
            try:
                if re.fullmatch(source_word_regex, original_word):
                    matched_lemma_from_regex1 = find_matching_override_in_context([override_rule], context_sentence)
                    if matched_lemma_from_regex1 is not None:
                        return matched_lemma_from_regex1
            except re.error as e:
                print(f"Warning: Invalid regex original word pattern: '{source_word_regex}'. Error: {e}", file=sys.stderr)

    priority2_rules = override_rules.get('priority2', {}).get(part)
    matched_lemma2 = find_matching_override_in_context(priority2_rules, context_sentence)
    if matched_lemma2 is not None:
        return matched_lemma2

    for source_word_regex, override_rule in override_rules.get('priority2_regex', []):
        try:
            if re.fullmatch(source_word_regex, original_word):
                matched_lemma_from_regex2 = find_matching_override_in_context([override_rule], context_sentence)
                if matched_lemma_from_regex2 is not None:
                    return matched_lemma_from_regex2
        except re.error as e:
            print(f"Warning: Invalid regex original word pattern: '{source_word_regex}'. Error: {e}", file=sys.stderr)

    priority3_rules = override_rules.get('priority3', {}).get(initial_lemma)
    matched_lemma3 = find_matching_override_in_context(priority3_rules, context_sentence)
    if matched_lemma3 is not None:
        return matched_lemma3
            
    return initial_lemma

def lemmatize_compound_part(part, nlp_model, de_dictionary, args=None):
    if not part:
        return ""

    is_all_caps = part.isupper() and len(part) > 1
    has_internal_caps = any(c.isupper() for c in part[1:])

    if is_all_caps or has_internal_caps:
        return part

    part_document = nlp_model(part)
    if not part_document or len(part_document) == 0:
        return ""

    token = part_document[0]
    
    if token.pos_ not in ["NOUN", "PROPN"]:
        spacy_lemma = token.lemma_
        if args and getattr(args, 'use_simplemma_correction', False):
            return simplemma.lemmatize(part, lang=getattr(args, 'language', 'en'))
        return spacy_lemma
    
    spacy_lemma = token.lemma_.capitalize()
    if args and getattr(args, 'use_simplemma_correction', False):
        spacy_lemma = simplemma.lemmatize(part, lang=getattr(args, 'language', 'en')).capitalize()

    capitalized_part = part.capitalize()

    if spacy_lemma in de_dictionary:
        return spacy_lemma

    if capitalized_part in de_dictionary:
        return capitalized_part

def get_simplemma_input_text(token, args):
    if getattr(args, 'simplemma_after_spacy', False) and hasattr(token, 'lemma_') and getattr(token, 'lemma_', None) is not None:
        base_str = str(token.lemma_)
    else:
        base_str = str(getattr(token, 'text', str(token)))
    
    if getattr(args, 'simplemma_pos_aware', False):
        if getattr(token, 'is_sent_start', False) and getattr(token, 'pos_', '') not in ['NOUN', 'PROPN']:
            return base_str.lower()
    return base_str


def get_simplemma_lemmas(token, lang, args):
    override_lemma = None
    smart_fallback_lemma = None
    if getattr(args, 'use_simplemma_correction', False):
        target_text = get_simplemma_input_text(token, args)
        override_lemma = simplemma.lemmatize(target_text, lang=lang)
    elif getattr(args, 'simplemma_smart_fallback', False):
        target_text = get_simplemma_input_text(token, args)
        smart_fallback_lemma = simplemma.lemmatize(target_text, lang=lang)
    elif getattr(args, 'simplemma_after_spacy', False):
        target_text = get_simplemma_input_text(token, args)
        override_lemma = simplemma.lemmatize(target_text, lang=lang)
    return override_lemma, smart_fallback_lemma


def correct_spacy_lemma(token, de_dictionary, fix_genitive=False, override_lemma=None, smart_fallback_lemma=None):
    if override_lemma is not None:
        spacy_lemma = override_lemma
    elif smart_fallback_lemma is not None:
        spacy_lemma = getattr(token, 'lemma_', None) or str(token)
        adopted = False
        if de_dictionary:
            if spacy_lemma not in de_dictionary and smart_fallback_lemma in de_dictionary:
                spacy_lemma = smart_fallback_lemma
                adopted = True
        if not adopted and getattr(token, 'pos_', '') in ['VERB', 'AUX']:
            token_text = str(getattr(token, 'text', str(token))).lower()
            if spacy_lemma.lower() == token_text and smart_fallback_lemma.lower() != token_text:
                spacy_lemma = smart_fallback_lemma
    else:
        spacy_lemma = getattr(token, 'lemma_', None) or str(token)

    nlp_inst = globals().get('nlp')
    if (fix_genitive and
        nlp_inst and nlp_inst.lang == 'de' and
        getattr(token, 'pos_', '') in ["NOUN", "PROPN"] and
        'Gen' in getattr(getattr(token, 'morph', None), 'get', lambda k, d=None: [])("Case", [])):

        if spacy_lemma.endswith('s') and len(spacy_lemma) > 1:
            lemma_without_genitive_s = spacy_lemma[:-1]
            if lemma_without_genitive_s.capitalize() in de_dictionary:
                return lemma_without_genitive_s

    return spacy_lemma

def find_separable_verb_particle_pairs(document):
    particle_map = {}
    for token in document:
        if token.dep_ == "svp":
            particle_map[token.head.i] = token
    return particle_map

def load_lemma_frequency_index(file_path):
    lemma_index = {}
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            for line_number, line in enumerate(file):
                word = line.strip()
                if word and word not in lemma_index:
                    lemma_index[word] = line_number
    except FileNotFoundError:
        print(f"File not found: {file_path}", file=sys.stderr)
        return {}
    except Exception as e:
        print(f"Error reading file {file_path}: {e}", file=sys.stderr)
        return {}
    return lemma_index

def get_lemma_sort_key(word, lemma_index, language="en", case_sensitive=None):
    language = language or "en"
    if case_sensitive is None:
        case_sensitive = (language == "de")
        
    # 1. Normalize punctuation for lookup
    def get_variations(w):
        vars_set = []
        w_clean = w.strip()
        vars_set.append(w_clean)
        if not case_sensitive:
            vars_set.append(w_clean.lower())
        
        # Replace curly apostrophe with straight, and vice-versa
        w_straight = w_clean.replace("’", "'")
        vars_set.append(w_straight)
        if not case_sensitive:
            vars_set.append(w_straight.lower())
        
        # Remove apostrophes and backticks entirely
        w_no_apo = w_clean.replace("’", "").replace("'", "").replace("`", "")
        vars_set.append(w_no_apo)
        if not case_sensitive:
            vars_set.append(w_no_apo.lower())
        
        seen = set()
        res = []
        for v in vars_set:
            if v not in seen:
                seen.add(v)
                res.append(v)
        return res

    # Check variations of the whole word first
    for var in get_variations(word):
        if var in lemma_index:
            return (False, lemma_index[var], word.lower())

    # 2. Handle subparts by comma, slash, space, or hyphen
    parts = []
    if ',' in word:
        parts = [p.strip() for p in word.split(',') if p.strip()]
    elif '/' in word:
        parts = [p.strip() for p in word.split('/') if p.strip()]
    elif language != "de":
        # Only split by spaces or hyphens for non-German languages
        if ' ' in word:
            parts = [p.strip() for p in word.split(' ') if p.strip()]
        elif '-' in word:
            parts = [p.strip() for p in word.split('-') if p.strip()]

    if parts:
        found_indices = []
        for p in parts:
            for var in get_variations(p):
                if var in lemma_index:
                    found_indices.append(lemma_index[var])
                    break
        if found_indices:
            # Use min rank (highest freq) for alternatives (comma/slash),
            # and max rank (lowest freq component) for phrases (space/hyphen).
            if ',' in word or '/' in word:
                val = min(found_indices)
            else:
                val = max(found_indices)
            return (False, val, word.lower())
            
    # 3. Fallback if not found
    return (True, 0, word.lower())

def read_text_from_file(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            content = file.read()
            return content.replace('\u200b', '').replace('\u200c', '').replace('\u200d', '').replace('\ufeff', '')
    except FileNotFoundError:
        print(f"File not found: {file_path}", file=sys.stderr); exit(1)
    except Exception as e:
        print(f"Error reading file {file_path}: {e}", file=sys.stderr); exit(1)

def get_anki_csv_header(header_override: Optional[Union[List[str], Tuple[str, ...], object]] = None) -> List[str]:
    if header_override:
        return list(header_override)
    config = AnkiMappingConfig()
    return list(config.header)

def get_field_index_map(header_override: Optional[Union[List[str], Tuple[str, ...], object]] = None) -> Dict[str, int]:
    """Returns a dict mapping each header field name to its 0-based index."""
    return {name: i for i, name in enumerate(get_anki_csv_header(header_override))}

def prepare_row_data(args: Union[ExtractionConfig, argparse.Namespace, SimpleNamespace, object], **kwargs: object) -> Dict[str, object]:
    """Consolidates all possibly mapped data into a single dictionary."""
    row_data = {
        KEY_LEMMA: kwargs.get(KEY_LEMMA, ''),
        KEY_SOURCE_WORD: kwargs.get(KEY_SOURCE_WORD, ''),
        KEY_RAW_SOURCE_WORD: kwargs.get(KEY_RAW_SOURCE_WORD, kwargs.get(KEY_SOURCE_WORD, '')),
        KEY_SOURCE_SENTENCE: kwargs.get(KEY_SOURCE_SENTENCE, ''),
        KEY_SOURCE_CONTEXT_LEFT: kwargs.get(KEY_SOURCE_CONTEXT_LEFT, ''),
        KEY_SOURCE_CONTEXT_RIGHT: kwargs.get(KEY_SOURCE_CONTEXT_RIGHT, ''),
        KEY_TARGET_SENTENCE: kwargs.get(KEY_TARGET_SENTENCE, ''),
        KEY_TARGET_CONTEXT_LEFT: kwargs.get(KEY_TARGET_CONTEXT_LEFT, ''),
        KEY_TARGET_CONTEXT_RIGHT: kwargs.get(KEY_TARGET_CONTEXT_RIGHT, ''),
        KEY_TERTIARY_SENTENCE: kwargs.get(KEY_TERTIARY_SENTENCE, ''),
        KEY_TERTIARY_CONTEXT_LEFT: kwargs.get(KEY_TERTIARY_CONTEXT_LEFT, ''),
        KEY_TERTIARY_CONTEXT_RIGHT: kwargs.get(KEY_TERTIARY_CONTEXT_RIGHT, ''),
        KEY_WORDLIST: kwargs.get(KEY_WORDLIST, ''),
        KEY_CLOZE: kwargs.get(KEY_CLOZE, ''),
        KEY_SENTENCE_INDEX: kwargs.get(KEY_SENTENCE_INDEX, ''),
        KEY_DECK_NAME: kwargs.get(KEY_DECK_NAME, ''),
        KEY_SUBTITLE_START_TIME: kwargs.get(KEY_SUBTITLE_START_TIME, ''),
    }
    
    # Dynamic TTS activation flags
    if getattr(args, 'language', None):
        row_data[f'{KEY_TTS_SOURCE_PREFIX}{getattr(args, "language")}'] = "1"
    if getattr(args, 'tts_destination_lang', None):
        row_data[f'{KEY_TTS_DEST_PREFIX}{getattr(args, "tts_destination_lang")}'] = "1"
        
    classifications = kwargs.get(KEY_CLASSIFICATIONS, {})
    lemma = row_data[KEY_LEMMA]
    case_sensitive = kwargs.get(KEY_CLASSIFICATION_CASE_SENSITIVE, True)
    if isinstance(classifications, dict):
        for c_name, c_dict in classifications.items():
            lookup_lemma = lemma if case_sensitive else getattr(lemma, 'lower', lambda: str(lemma))()
            if lookup_lemma in c_dict:
                row_data[c_name] = c_dict[lookup_lemma]
            
    return row_data


def apply_field_mapping(csv_row, row_data, field_mapping, field_index_map):
    """Applies a field mapping to override csv_row values using row_data.
    
    Args:
        csv_row: The list representing a TSV row (modified in-place).
        row_data: Dict of {internal_name: value} with all available data sources.
        field_mapping: Dict of {anki_field_name: internal_data_source_name} from config.
        field_index_map: Dict of {anki_field_name: column_index}.
    """
    if not field_mapping:
        return
    for field_name, data_source in field_mapping.items():
        if field_name in field_index_map:
            val = row_data.get(data_source, "")
            if field_name == FIELD_QUOTATION and data_source == KEY_SOURCE_WORD:
                val = row_data.get(KEY_RAW_SOURCE_WORD, val)
            csv_row[field_index_map[field_name]] = val
        else:
            print(f"Warning: Unknown field '{field_name}' in anki_field_mapping, skipping.", file=sys.stderr)

def generate_filename_prefix_from_text(text, word_count):
    if not text:
        return ""
    normalized_text = text.lower()
    normalized_text = normalized_text.replace('ä', 'ae').replace('ö', 'oe').replace('ü', 'ue').replace('ß', 'ss')
    words = re.findall(r'[a-z0-9]+', normalized_text)
    prefix_words = words[:word_count]
    if not prefix_words:
        return ""
    return "-".join(prefix_words)

def format_lemma_capitalization(
    token: Union[object, SimpleNamespace],
    initial_lemma: str,
    args_or_config: Optional[Union[ExtractionConfig, argparse.Namespace, SimpleNamespace, object]] = None,
    context: Optional[ExecutionContext] = None
) -> str:
    config = ExtractionConfig.from_args(args_or_config) if not isinstance(args_or_config, ExtractionConfig) and args_or_config is not None else (args_or_config or ExtractionConfig())
    current_nlp = context.nlp if (context and context.nlp is not None) else nlp
    nlp_lang = getattr(current_nlp, 'lang', getattr(config, 'language', 'de'))
    if getattr(token, 'like_url', False) or getattr(token, 'like_email', False):
        return initial_lemma.lower()

    source_token_text = getattr(token, 'text', str(token))
    is_all_caps = source_token_text.isupper() and len(source_token_text) > 1
    has_internal_caps = any(c.isupper() for c in source_token_text[1:])

    if is_all_caps or has_internal_caps:
        return source_token_text
    
    token_pos = getattr(token, 'pos_', '')
    if config.de_force_noun_capitalization and nlp_lang == 'de':
        if token_pos in ["NOUN", "PROPN"]:
            return initial_lemma.capitalize()
    
    if config.force_proper_noun_capitalization:
        if token_pos == "PROPN":
            return initial_lemma.capitalize()

    if getattr(token, 'is_sent_start', False) and token_pos not in ["NOUN", "PROPN"]:
        return initial_lemma

    return initial_lemma

def deduplicate_lemmas(
    candidate_lemmas: Union[List[str], Set[str], Tuple[str, ...], object],
    config: Optional[Union[ExtractionConfig, argparse.Namespace, SimpleNamespace, object]] = None
) -> List[str]:
    if config is not None and not isinstance(config, ExtractionConfig):
        config = ExtractionConfig.from_args(config)
    lemmas_grouped_by_lowercase: Dict[str, Set[str]] = {}
    for lemma in candidate_lemmas:
        if not lemma: continue
        lower_lemma = str(lemma).lower()
        if lower_lemma not in lemmas_grouped_by_lowercase:
            lemmas_grouped_by_lowercase[lower_lemma] = set()
        lemmas_grouped_by_lowercase[lower_lemma].add(str(lemma))
    
    final_lemmas: List[str] = []
    for _, capitalization_variants in lemmas_grouped_by_lowercase.items():
        capitalized_variant = next((v for v in capitalization_variants if v[0].isupper()), None)
        
        if capitalized_variant:
            final_lemmas.append(capitalized_variant)
        elif capitalization_variants:
            final_lemmas.append(list(capitalization_variants)[0])
            
    return final_lemmas

def _lemmatize_mapped_tokens(mapped_lemmas, nlp_model, de_dictionary, lemma_override_rules, args, sentence_text, de_fix_genitive=False):
    if not getattr(args, 'token_mappings_lemmatize', False):
        return mapped_lemmas
        
    result = []
    for l in mapped_lemmas:
        doc = nlp_model(l)
        if len(doc) > 0:
            ltok = doc[0]
            override_lemma, smart_fallback_lemma = get_simplemma_lemmas(ltok, nlp_model.lang, args)
            spacy_lemma = correct_spacy_lemma(ltok, de_dictionary, de_fix_genitive, override_lemma=override_lemma, smart_fallback_lemma=smart_fallback_lemma)
            default_lemma = format_lemma_capitalization(ltok, spacy_lemma, args)
            final_lemma = get_overridden_lemma_for_word(default_lemma, l, lemma_override_rules, sentence_text)
            result.append(final_lemma)
        else:
            result.append(l)
    return result

def parse_markdown_for_branch_headers(all_lines):
    branch_header_indices = set()
    last_header_level = 0
    last_header_index = -1
    for i, line in enumerate(all_lines):
        line = line.strip()
        if line.startswith('#'):
            match = re.match(r'^(#+)', line)
            current_level = len(match.group(1))
            if current_level > last_header_level and last_header_index != -1:
                branch_header_indices.add(last_header_index)
            last_header_level = current_level
            last_header_index = i
    return branch_header_indices


def _extract_mapped_token(match, nlp_model, de_dictionary, lemma_override_rules, args, sentence_text, de_fix_genitive):
    lemmas = _lemmatize_mapped_tokens(
        match['lemmas'], nlp_model, de_dictionary, lemma_override_rules, args, sentence_text, de_fix_genitive
    )
    mapped_sources = {}
    for raw_target_token, lem in zip(match['lemmas'], lemmas):
        combined = sort_inflected_forms([match['source_word'], raw_target_token], config=args)
        if lem in mapped_sources:
            existing = [s.strip() for s in mapped_sources[lem].split(',') if s.strip()]
            existing.extend(combined)
            mapped_sources[lem] = ", ".join(sort_inflected_forms(existing, config=args))
        else:
            mapped_sources[lem] = ", ".join(combined)
    return lemmas, mapped_sources

def retokenize_hyphenated_compounds(doc: Any) -> Any:
    """Retokenize contiguous alphanumeric tokens separated by single hyphens into single composite tokens.
    
    Excludes purely numeric ranges (e.g. '2024-2026'), negative numbers ('-10'),
    and standalone punctuation dashes ('--', '- item', 'A - B').
    """
    if doc is None or not hasattr(doc, 'retokenize') or not hasattr(doc, '__len__'):
        return doc

    spans_to_merge = []
    i = 0
    n = len(doc)
    while i < n:
        if i + 2 < n:
            tok_i = doc[i]
            tok_dash = doc[i + 1]
            if getattr(tok_i, 'whitespace_', ' ') == '' and getattr(tok_dash, 'text', '') == '-' and getattr(tok_dash, 'whitespace_', ' ') == '':
                j = i
                while (
                    j + 2 < n and 
                    getattr(doc[j], 'whitespace_', ' ') == '' and 
                    getattr(doc[j + 1], 'text', '') == '-' and 
                    getattr(doc[j + 1], 'whitespace_', ' ') == ''
                ):
                    j += 2
                
                candidate_tokens = [doc[k] for k in range(i, j + 1, 2)]
                has_alpha = any(any(c.isalpha() for c in getattr(tok, 'text', '')) for tok in candidate_tokens)
                all_valid = all(
                    getattr(tok, 'text', '') and not any(c in ' \t\r\n' for c in getattr(tok, 'text', ''))
                    for tok in candidate_tokens
                )
                all_alnum = all(
                    any(c.isalnum() for c in getattr(tok, 'text', ''))
                    for tok in candidate_tokens
                )

                if has_alpha and all_valid and all_alnum:
                    spans_to_merge.append(doc[i : j + 1])
                    i = j + 1
                    continue
        i += 1

    if spans_to_merge:
        with doc.retokenize() as retokenizer:
            for span in spans_to_merge:
                retokenizer.merge(span)

    return doc

KNOWN_ENTITIES_AND_BRANDS = {
    "chatgpt", "openai", "youtube", "iphone", "ipad", "ipod", "macos", "ios", "watchos",
    "github", "gitlab", "javascript", "typescript", "powershell", "autohotkey",
    "quicktime", "wordpress", "linkedin", "playstation", "tiktok", "whatsapp",
    "deepl", "fedex", "ebay", "paypal", "openspec", "webgl", "opengl", "openal",
    "directx", "vulkan", "scikit", "spacy", "huggingface", "pytorch", "tensorflow",
    "nvidia", "amd", "intel", "microsoft", "google", "apple", "amazon", "meta"
}

def split_camel_case(s: str) -> list:
    """Split camelCase, PascalCase, or uppercase acronym boundaries into constituent words."""
    if not s:
        return []
    parts = re.findall(r'[A-ZА-ЯÄÖÜ0-9]+(?=[A-ZА-ЯÄÖÜ][a-zа-яäöüß])|[A-ZА-ЯÄÖÜ]?[a-zа-яäöüß\'’‘`´ʼ]+[0-9]*|[A-ZА-ЯÄÖÜ0-9]+', s)
    return [p for p in parts if p]

def is_composite_token(text: str) -> bool:
    if not text:
        return False
    if ('/' in text or '\\' in text) and any(c.isalpha() for c in text):
        return True
    if '_' in text and text.strip('_'):
        return True
    if re.search(r'\w\.\w', text) and any(c.isalpha() for c in text):
        return True
    if re.search(r'\w-\w', text) and any(c.isalpha() for c in text):
        return True
    if text.lower() in KNOWN_ENTITIES_AND_BRANDS:
        return False
    if re.search(r'[a-zа-яäöüß][A-ZА-ЯÄÖÜ]|[A-ZА-ЯÄÖÜ]{2,}[a-zа-яäöüß]', text):
        return True
    return False

def _extract_standard_token(
    token, nlp_model, de_dictionary, lemma_override_rules, sentence_text, de_fix_genitive, 
    de_gcs, gcs_automaton, de_gcs_pos_tags, args, separable_verb_map, 
    de_gcs_only_nouns=True,
    de_gcs_combine_noun_modes=False,
    de_gcs_mask_unknown_parts=False,
    de_gcs_preserve_compound_word=False,
    de_gcs_skip_merge_fractions=False,
    preserve_composite_tokens=False
):

    lemmas_for_current_token = []
    source_word_form = token.text
    base_lemma = ""
    
    if token.i in separable_verb_map:
        particle = separable_verb_map[token.i]
        override_lemma, smart_fallback_lemma = get_simplemma_lemmas(token, nlp_model.lang, args)
        base_verb_lemma = correct_spacy_lemma(token, de_dictionary, de_fix_genitive, override_lemma=override_lemma, smart_fallback_lemma=smart_fallback_lemma)
        default_lemma = f"{particle.text.lower()}{base_verb_lemma}".lower()
        source_word_form = f"{token.text} {particle.text}"
    else:
        override_lemma, smart_fallback_lemma = get_simplemma_lemmas(token, nlp_model.lang, args)
        spacy_lemma = correct_spacy_lemma(token, de_dictionary, de_fix_genitive, override_lemma=override_lemma, smart_fallback_lemma=smart_fallback_lemma)
        default_lemma = format_lemma_capitalization(token, spacy_lemma, args)
        
    base_lemma = get_overridden_lemma_for_word(default_lemma, source_word_form, lemma_override_rules, sentence_text)
    if base_lemma and re.match(r'^\d{14}-', base_lemma):
        base_lemma = re.sub(r'^\d{14}-', '', base_lemma)

    was_split = False
    is_explicit_url = token.like_url and (token.text.startswith(('http://', 'https://', 'ftp://', 'www.')) or '://' in token.text)
    is_special_token = is_explicit_url or token.like_email
    preserve_composite = preserve_composite_tokens or getattr(args, 'preserve_composite_tokens', False)

    is_named_entity = (
        getattr(token, 'ent_type_', '') in {'ORG', 'PRODUCT', 'PERSON', 'GPE', 'FAC', 'NORP', 'WORK_OF_ART', 'EVENT'}
        or (getattr(token, 'pos_', '') == 'PROPN' and not any(c in token.text for c in '_/\\.'))
        or token.text.lower() in KNOWN_ENTITIES_AND_BRANDS
        or (de_dictionary and (token.text in de_dictionary or token.text.capitalize() in de_dictionary or token.text.lower() in de_dictionary))
    )
    is_pure_camel = not any(c in token.text for c in '_-\\/:#@.') and is_composite_token(token.text)

    if de_gcs and '-' in token.text and not is_special_token:
        was_split = True
        hyphenated_parts = token.text.split('-')

        if de_gcs_preserve_compound_word or preserve_composite:
            lemmas_for_current_token.append(base_lemma)

        for part in hyphenated_parts:
            part = part.strip()
            if not part or len(part) <= 1: continue

            initial_part_lemma = lemmatize_compound_part(part, nlp_model, de_dictionary, args)
            processed_part_lemma = get_overridden_lemma_for_compound_part(initial_part_lemma, part, token.text, lemma_override_rules, sentence_text)
            if processed_part_lemma:
                lemmas_for_current_token.append(processed_part_lemma)

    elif is_composite_token(token.text) and not is_special_token and not (is_pure_camel and is_named_entity):
        is_path_token = '/' in token.text or '\\' in token.text
        sub_parts = re.split(r'[_.\-/:#@\\]+', token.text)
        extracted_sub_lemmas = []
        part_source_map = {}
        for part in sub_parts:
            part = part.strip("()[]{}:;,.!?'\"`~-<>\\/ \t\r\n")
            if not part or part.isdigit():
                continue
            if part.lower() in KNOWN_ENTITIES_AND_BRANDS or (de_dictionary and (part in de_dictionary or part.capitalize() in de_dictionary or part.lower() in de_dictionary)):
                camel_parts = [part]
            else:
                camel_parts = split_camel_case(part)
            sub_units = camel_parts if len(camel_parts) > 1 else [part]
            for unit in sub_units:
                part_doc = nlp_model(unit)
                for sub_token in part_doc:
                    if not (sub_token.is_alpha or ('-' in sub_token.text and sub_token.text.strip('-')) or any(c.isalpha() for c in sub_token.text)):
                        continue
                    sub_override_lemma, sub_smart_fallback = get_simplemma_lemmas(sub_token, getattr(nlp_model, 'lang', 'en'), args)
                    sub_spacy_lemma = correct_spacy_lemma(sub_token, de_dictionary, de_fix_genitive, override_lemma=sub_override_lemma, smart_fallback_lemma=sub_smart_fallback)
                    sub_default_lemma = format_lemma_capitalization(sub_token, sub_spacy_lemma, args)
                    sub_lemma = get_overridden_lemma_for_word(sub_default_lemma, sub_token.text, lemma_override_rules, sentence_text)
                    if sub_lemma:
                        extracted_sub_lemmas.append(sub_lemma)
                        part_source_map[sub_lemma] = sub_token.text if is_path_token else source_word_form
        if extracted_sub_lemmas:
            was_split = True
            if not is_path_token and (preserve_composite or (de_gcs and de_gcs_preserve_compound_word)):
                lemmas_for_current_token.append(base_lemma)
                part_source_map[base_lemma] = source_word_form
            lemmas_for_current_token.extend(extracted_sub_lemmas)

    elif de_gcs and gcs_automaton and nlp_model.lang == 'de' and not is_special_token and len(token.text) > 3 and (token.pos_ in de_gcs_pos_tags):
        try:
            word_to_split = token.text
            if getattr(args, 'de_gcs_part_singularization', 'only-nouns') == 'none':
                make_singular_flag = False
            elif getattr(args, 'de_gcs_part_singularization', 'only-nouns') == 'all':
                make_singular_flag = True
            else:
                make_singular_flag = (token.pos_ in ['NOUN', 'PROPN'])

            split_components = []
            if de_gcs_combine_noun_modes:
                with redirect_stdout(io.StringIO()):
                    dissection1 = comp_split.dissect(word_to_split, gcs_automaton, make_singular=make_singular_flag, only_nouns=True, mask_unknown=de_gcs_mask_unknown_parts)
                with redirect_stdout(io.StringIO()):
                    dissection2 = comp_split.dissect(word_to_split, gcs_automaton, make_singular=make_singular_flag, only_nouns=False, mask_unknown=de_gcs_mask_unknown_parts)

                if de_gcs_skip_merge_fractions:
                    split_components.extend(dissection1)
                    split_components.extend(dissection2)
                else:
                    split_components.extend(comp_split.merge_fractions(dissection1))
                    split_components.extend(comp_split.merge_fractions(dissection2))

            else:
                with redirect_stdout(io.StringIO()):
                    dissection = comp_split.dissect(word_to_split, gcs_automaton, make_singular=make_singular_flag, only_nouns=de_gcs_only_nouns, mask_unknown=de_gcs_mask_unknown_parts)

                if de_gcs_skip_merge_fractions:
                    split_components = dissection
                else:
                    split_components = comp_split.merge_fractions(dissection)

            if len(split_components) > 1:
                was_split = True
                if de_gcs_preserve_compound_word or preserve_composite:
                    lemmas_for_current_token.append(base_lemma)

                for raw_component in set(split_components):
                    component = raw_component.strip('-')
                    if not component or len(component) < 3: continue

                    initial_part_lemma = lemmatize_compound_part(component, nlp_model, de_dictionary, args)
                    overridden_part_lemma = get_overridden_lemma_for_compound_part(initial_part_lemma, component, token.text, lemma_override_rules, sentence_text)
                    processed_part_lemma = _format_gcs_component_case(overridden_part_lemma)

                    if processed_part_lemma:
                        lemmas_for_current_token.append(processed_part_lemma)
                        
        except Exception as e:
            print(f"Warning: GCS processing failed for '{token.text}': {e}", file=sys.stderr)

    if not was_split:
        lemmas_for_current_token.append(base_lemma)

    mapped_sources = {}
    for lem in lemmas_for_current_token:
        mapped_sources[lem] = part_source_map.get(lem, source_word_form) if 'part_source_map' in locals() else source_word_form
    return lemmas_for_current_token, mapped_sources

def extract_lemmas_from_sentence(
    sentence_text: str,
    lemma_sort_index: Union[Dict[str, int], SimpleNamespace, object],
    nlp_model: Optional[object] = None,
    de_dictionary: Optional[Union[Set[str], Dict[str, str], object]] = None,
    lemma_override_rules: Optional[Dict[str, str]] = None,
    de_gcs_pos_tags: Optional[Union[List[str], Tuple[str, ...], Set[str]]] = None,
    args: Optional[Union[ExtractionConfig, argparse.Namespace, SimpleNamespace, object]] = None,
    context: Optional[ExecutionContext] = None,
    gcs_config: Optional[GCSConfig] = None,
    extraction_config: Optional[ExtractionConfig] = None,
    **kwargs: object
) -> List[str]:
    current_nlp = context.nlp if (context and context.nlp is not None) else nlp_model
    gcs_automaton = context.gcs_automaton if (context and context.gcs_automaton is not None) else kwargs.get('gcs_automaton', None)
    de_dictionary = getattr(context, 'de_dictionary', None) if (context and getattr(context, 'de_dictionary', None) is not None) else de_dictionary

    if gcs_config is None:
        merged_dict = getattr(args, '__dict__', {}).copy() if args is not None else {}
        merged_dict.update(kwargs)
        if de_gcs_pos_tags is not None:
            merged_dict['de_gcs_pos_tags'] = de_gcs_pos_tags
        gcs_config = GCSConfig.from_args(SimpleNamespace(**merged_dict))
        
    if extraction_config is None and args is not None:
        extraction_config = ExtractionConfig.from_args(args)

    de_gcs = gcs_config.de_gcs
    de_gcs_add_parts_to_wordlist = gcs_config.de_gcs_add_parts_to_wordlist
    
    if de_gcs and not de_gcs_add_parts_to_wordlist:
        de_gcs = False

    de_gcs_only_nouns = gcs_config.de_gcs_only_nouns
    de_gcs_combine_noun_modes = gcs_config.de_gcs_combine_noun_modes
    de_fix_genitive = gcs_config.de_fix_genitive
    de_gcs_mask_unknown_parts = gcs_config.de_gcs_mask_unknown_parts
    de_gcs_preserve_compound_word = gcs_config.de_gcs_preserve_compound_word
    de_gcs_skip_merge_fractions = gcs_config.de_gcs_skip_merge_fractions
    preserve_composite_tokens = getattr(extraction_config, 'preserve_composite_tokens', False) if extraction_config is not None else getattr(args, 'preserve_composite_tokens', False)

    sentence_doc = retokenize_hyphenated_compounds(current_nlp(sentence_text))
    final_lemmas = set()

    separable_verb_map = find_separable_verb_particle_pairs(sentence_doc)
    processed_particle_indices = {p.i for p in separable_verb_map.values()}

    token_mappings_matches, mapped_tokens = find_token_mappings_in_text(sentence_text, sentence_doc, kwargs.get('token_mappings', {}), args)

    for token in sentence_doc:
        if token.i in processed_particle_indices:
            continue

        if token.i in mapped_tokens:
            if token.i in token_mappings_matches:
                lemmas_for_current_token, _ = _extract_mapped_token(
                    token_mappings_matches[token.i], current_nlp, de_dictionary, lemma_override_rules, args, sentence_text, de_fix_genitive
                )
            else:
                continue
        else:
            if not (token.is_alpha or ('-' in token.text and token.text.strip('-')) or is_composite_token(token.text)):
                continue
            lemmas_for_current_token, _ = _extract_standard_token(
                token, current_nlp, de_dictionary, lemma_override_rules, sentence_text, de_fix_genitive, 
                de_gcs, gcs_automaton, de_gcs_pos_tags, args, separable_verb_map, 
                de_gcs_only_nouns=de_gcs_only_nouns,
                de_gcs_combine_noun_modes=de_gcs_combine_noun_modes,
                de_gcs_mask_unknown_parts=de_gcs_mask_unknown_parts,
                de_gcs_preserve_compound_word=de_gcs_preserve_compound_word,
                de_gcs_skip_merge_fractions=de_gcs_skip_merge_fractions,
                preserve_composite_tokens=preserve_composite_tokens
            )

        deduplicated_lemmas = deduplicate_lemmas(lemmas_for_current_token, extraction_config)
        for lemma in deduplicated_lemmas:
            final_lemmas.add(lemma)

    lang_code = getattr(extraction_config, 'language', getattr(args, 'language', 'en')) if extraction_config or args else 'en'
    return sorted(list(final_lemmas), key=lambda x: get_lemma_sort_key(x, lemma_sort_index, lang_code))

def _write_deck_metadata(args, output_file_path, source_text_content, target_text_content=None, tertiary_text_content=None, subdeck_content_map=None):
    if not args.anki_deck_content:
        return

    deck_descriptions = {}
    parent_deck_name = ""
    root_deck_prefix = ""

    if args.anki_markdown_decks:
        if args.anki_create_subdecks:
            if args.anki_parent_deck:
                root_deck_prefix = args.anki_parent_deck
            elif output_file_path:
                base_name = os.path.splitext(os.path.basename(output_file_path))[0]
                root_deck_prefix = re.sub(r'\.(word|sentence)', '', base_name)
        parent_deck_name = root_deck_prefix
    else:
        if args.anki_create_subdecks:
            sub_deck_name = os.path.splitext(os.path.basename(output_file_path))[0]
            if args.anki_parent_deck:
                parent_deck_name = args.anki_parent_deck
            else:
                parent_deck_name = re.sub(r'\.(word|sentence)', '', sub_deck_name)
        else:
            parent_deck_name = os.path.splitext(os.path.basename(output_file_path))[0]
    
    if parent_deck_name:
        description_parts = []
        
        if 'parent-source' in args.anki_deck_content and source_text_content:
            normalized_source = source_text_content.replace('\r\n', '\n')
            description_parts.append(normalized_source.strip())

        if 'parent-translations' in args.anki_deck_content:
            if target_text_content and target_text_content.strip():
                normalized_target = target_text_content.replace('\r\n', '\n')
                description_parts.append(normalized_target.strip())
            if tertiary_text_content and tertiary_text_content.strip():
                normalized_tertiary = tertiary_text_content.replace('\r\n', '\n')
                description_parts.append(normalized_tertiary.strip())
        
        if description_parts:
            deck_descriptions[parent_deck_name] = "\n\n---\n\n".join(description_parts)

    if subdeck_content_map and ('subdeck-source' in args.anki_deck_content or 'subdeck-translations' in args.anki_deck_content):
        for deck_name, content_data in subdeck_content_map.items():
            if not deck_name: continue

            if deck_name == parent_deck_name and parent_deck_name in deck_descriptions:
                            continue

            subdeck_description_parts = []
            if 'subdeck-source' in args.anki_deck_content:
                source_part = "\n".join(content_data.get('source_lines', []))
                if source_part: subdeck_description_parts.append(source_part)

            if 'subdeck-translations' in args.anki_deck_content:
                translation1_part = "\n".join(content_data.get('translation1_lines', []))
                if translation1_part: subdeck_description_parts.append(translation1_part)
                
                translation2_part = "\n".join(content_data.get('translation2_lines', []))
                if translation2_part: subdeck_description_parts.append(translation2_part)

            if subdeck_description_parts:
                deck_descriptions[deck_name] = "\n\n---\n\n".join(subdeck_description_parts)

    if not deck_descriptions:
        return

    metadata = {"deck_descriptions": deck_descriptions}
    
    metadata_path = os.path.splitext(output_file_path)[0] + '.json'
    try:
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
    except IOError as e:
        print(f"Warning: Could not write metadata file to {metadata_path}: {e}", file=sys.stderr)

class OutputFormatter(ABC):
    """Abstract base class for polymorphic output formatters cleanly translating stream records to STDOUT."""
    @abstractmethod
    def format(self, records: Iterable[TabularRecord], output_stream: Any = sys.stdout) -> None:
        pass

    @classmethod
    def get_formatter(cls, format_type: Optional[str]) -> "OutputFormatter":
        if format_type == "tsv":
            return TsvFormatter()
        elif format_type == "html":
            return HtmlFormatter()
        elif format_type == "json":
            return JsonFormatter()
        elif format_type == "context":
            return ContextFormatter()
        else:
            return PlainFormatter()


class TsvFormatter(OutputFormatter):
    def format(self, records: Iterable[TabularRecord], output_stream: Any = sys.stdout) -> None:
        for record in records:
            if record.row_data:
                lemma = record.row_data.get(KEY_LEMMA, '')
                source_word = record.row_data.get(KEY_SOURCE_WORD, '')
                print(f"{lemma}\t{source_word}", file=output_stream)
            elif record.fields:
                print("\t".join(str(f) for f in record.fields), file=output_stream)
            elif record.raw_line is not None:
                print(record.raw_line, file=output_stream)


class HtmlFormatter(OutputFormatter):
    def format(self, records: Iterable[TabularRecord], output_stream: Any = sys.stdout) -> None:
        print("<table>", file=output_stream)
        for record in records:
            if record.row_data:
                lemma = record.row_data.get(KEY_LEMMA, '')
                source_word = record.row_data.get(KEY_SOURCE_WORD, '')
                print(f"<tr><td>{lemma}</td><td>{source_word}</td></tr>", file=output_stream)
            elif record.fields and len(record.fields) >= 2:
                print(f"<tr><td>{record.fields[0]}</td><td>{record.fields[1]}</td></tr>", file=output_stream)
            elif record.raw_line is not None:
                print(f"<tr><td>{record.raw_line}</td><td></td></tr>", file=output_stream)
        print("</table>", file=output_stream)


class JsonFormatter(OutputFormatter):
    def format(self, records: Iterable[TabularRecord], output_stream: Any = sys.stdout) -> None:
        data = []
        for record in records:
            if record.row_data:
                data.append(record.row_data)
            elif record.fields:
                data.append(record.fields)
            elif record.raw_line is not None:
                data.append(record.raw_line)
        print(json.dumps(data, ensure_ascii=False, indent=2), file=output_stream)


class PlainFormatter(OutputFormatter):
    def format(self, records: Iterable[TabularRecord], output_stream: Any = sys.stdout) -> None:
        for record in records:
            if record.row_data:
                lemma = record.row_data.get(KEY_LEMMA, '')
                print(lemma, file=output_stream)
            elif record.fields:
                print(str(record.fields[0]), file=output_stream)
            elif record.raw_line is not None:
                print(record.raw_line, file=output_stream)


class ContextFormatter(OutputFormatter):
    def format(self, records: Iterable[TabularRecord], output_stream: Any = sys.stdout) -> None:
        for record in records:
            if record.row_data:
                lemma = record.row_data.get(KEY_LEMMA, '')
                left = record.row_data.get(KEY_SOURCE_CONTEXT_LEFT, '')
                sent = record.row_data.get(KEY_SOURCE_SENTENCE, '')
                right = record.row_data.get(KEY_SOURCE_CONTEXT_RIGHT, '')
                print(lemma, file=output_stream)
                if left:
                    print(left, file=output_stream)
                if sent:
                    print(sent, file=output_stream)
                if right:
                    print(right, file=output_stream)
                print(file=output_stream)


class ParallelTextsStrategy(OperationalStrategy):
    """Stateless transformation strategy for parallel text processing yielding tabular records."""
    def execute(self, config: ExtractionConfig, context: ExecutionContext) -> Iterator[TabularRecord]:
        source_text = getattr(config, 'source_text', "")
        if not source_text and getattr(config, 'source_text_content', None):
            source_text = getattr(config, 'source_text_content', "")
        lemma_sort_index = getattr(config, 'lemma_sort_index', {})
        language = getattr(config, 'language', 'de')
        sentence_context_size = getattr(config, 'sentence_context_size', 1)
        add_source_word_col = getattr(config, 'add_source_word_col', False)
        add_wordlist_col = getattr(config, 'add_wordlist_col', False)
        wordlist_use_br = getattr(config, 'wordlist_use_br', False)
        de_gcs = getattr(config, 'de_gcs', False)
        de_gcs_add_parts_to_wordlist = getattr(config, 'de_gcs_add_parts_to_wordlist', False)
        lemma_override_rules = getattr(config, 'lemma_override_rules', {})
        de_gcs_pos_tags = getattr(config, 'de_gcs_pos_tags', [])
        field_mapping = getattr(config, 'field_mapping', {})
        anki_header = getattr(config, 'anki_header', [])
        if isinstance(anki_header, tuple):
            anki_header = list(anki_header)
        if not anki_header and getattr(config, 'header', None):
            anki_header = list(getattr(config, 'header', []))

        current_nlp = context.nlp if (context and context.nlp) else nlp
        gcs_automaton = context.gcs_automaton if (context and context.gcs_automaton) else getattr(config, 'gcs_automaton', None)
        de_dictionary = context.de_dictionary if (context and context.de_dictionary) else getattr(config, 'de_dictionary', None)

        de_gcs_only_nouns = getattr(config, 'de_gcs_only_nouns', True)
        de_gcs_combine_noun_modes = getattr(config, 'de_gcs_combine_noun_modes', False)
        de_fix_genitive = getattr(config, 'de_fix_genitive', False)
        de_gcs_mask_unknown_parts = getattr(config, 'de_gcs_mask_unknown_parts', False)
        de_gcs_preserve_compound_word = getattr(config, 'de_gcs_preserve_compound_word', False)
        preserve_composite_tokens = getattr(config, 'preserve_composite_tokens', False)
        de_gcs_skip_merge_fractions = getattr(config, 'de_gcs_skip_merge_fractions', False)
        token_mappings_val = getattr(config, 'token_mappings', {})
        classifications_val = getattr(config, 'classifications', {})

        source_text_lines_all = [line.rstrip("\n") for line in source_text.splitlines()] if source_text else []
        target_content_lines_all = []
        tgt_content = getattr(config, 'target_text_content', None)
        if tgt_content:
            target_content_lines_all = [line.rstrip("\n") for line in tgt_content.splitlines()]
        tertiary_content_lines_all = []
        tert_content = getattr(config, 'tertiary_text_content', None)
        if tert_content:
            tertiary_content_lines_all = [line.rstrip("\n") for line in tert_content.splitlines()]

        strip_config = {'source': False, 'translations': False}
        strip_headers = getattr(config, 'strip_headers', None)
        if strip_headers is not None:
            targets = strip_headers if strip_headers else ['all']
            if 'all' in targets or 'source' in targets:
                strip_config['source'] = True
            if 'all' in targets or 'translations' in targets:
                strip_config['translations'] = True

        display_source_lines_all = [_strip_markdown_header(line) for line in source_text_lines_all] if strip_config['source'] else source_text_lines_all
        display_target_lines_all = [_strip_markdown_header(line) for line in target_content_lines_all] if strip_config['translations'] else target_content_lines_all
        display_tertiary_lines_all = [_strip_markdown_header(line) for line in tertiary_content_lines_all] if strip_config['translations'] else tertiary_content_lines_all
        
        display_source_content_lines = [line for line in display_source_lines_all if line.strip()]
        display_target_content_lines = [line for line in display_target_lines_all if line.strip()]
        display_tertiary_content_lines = [line for line in display_tertiary_lines_all if line.strip()]

        lemma_data = {}
        if getattr(config, 'deduplication_scope', 'global') == 'global':
            lemma_data = {'lemmas': {}, 'info': {}, 'raw_source_words': {}}
        else:
            lemma_data = []

        order_cfg = getattr(config, 'combine_source_words_order', 'contractions_first')
        prefer_lowercase_cfg = getattr(config, 'combine_source_words_prefer_lowercase', True)
        apo_str = getattr(config, 'apostrophe_chars', "', ’, ‘, `, ´, ʼ")
        apo_cfg = tuple(c.strip() for c in apo_str.strip('"').split(',') if c.strip())

        subdeck_content_map = {}
        deck_stack = []
        level_stack = []
        header_counter = 1
        sentence_lemmas_cache = {}
        
        branch_header_lines = set()
        sub_deck_name, root_deck_prefix = self._derive_deck_prefixes(config)

        if getattr(config, 'anki_markdown_decks', False):
            branch_header_lines = parse_markdown_for_branch_headers(source_text_lines_all)
            root_prefix_md = ""
            if getattr(config, 'anki_create_subdecks', False):
                if getattr(config, 'anki_parent_deck', None):
                    root_prefix_md = getattr(config, 'anki_parent_deck')
                else:
                    root_prefix_md = root_deck_prefix
            if root_prefix_md:
                deck_stack.append(root_prefix_md)
                level_stack.append(0)

        text_has_headers = any(re.match(r'^(#+)\s+', line.strip()) for line in source_text_lines_all)
        first_real_header_level = 2 
        if text_has_headers:
            for line in source_text_lines_all:
                match = re.match(r'^(#+)', line.strip())
                if match:
                    first_real_header_level = len(match.group(1))
                    break

        content_line_idx = -1
        active_header_line_index = -1
        first_header_encountered = False
        placeholder_deck_created = False
        doc_cache = {}

        for line_index, source_line_raw in enumerate(source_text_lines_all):
            if context and context.is_cancelled():
                break
            if not source_line_raw.strip():
                continue

            lemmas_in_sentence = {}
            source_line_for_analysis = source_line_raw.strip()
            
            if getattr(config, 'anki_markdown_decks', False):
                header_match = re.match(r'^(#+)\s+(.*)', source_line_for_analysis)
                if header_match:
                    first_header_encountered = True
                    active_header_line_index = line_index
                    level = len(header_match.group(1))
                    title = header_match.group(2).strip()
                    sanitized_title = generate_filename_prefix_from_text(title, 5)

                    while level_stack and level_stack[-1] >= level:
                        level_stack.pop()
                        deck_stack.pop()
                    
                    if sanitized_title:
                        deck_stack.append(f"{100000 + header_counter}-{sanitized_title}")
                        level_stack.append(level)
                        header_counter += 1
                    source_line_for_analysis = title
                elif not first_header_encountered and not placeholder_deck_created and text_has_headers:
                    level = first_real_header_level
                    while level_stack and level_stack[-1] >= level:
                        level_stack.pop()
                        deck_stack.pop()

                    title = source_line_for_analysis
                    sanitized_title = generate_filename_prefix_from_text(title, 5)
                    if sanitized_title:
                        deck_stack.append(f"{100000 + header_counter}-{sanitized_title}")
                        level_stack.append(level)
                        header_counter += 1
                    placeholder_deck_created = True
            
            content_line_idx += 1
            source_sentence = source_line_for_analysis
            
            base_deck = "::".join(deck_stack)
            final_deck = base_deck
            if getattr(config, 'anki_markdown_decks', False) and active_header_line_index in branch_header_lines:
                final_deck = f"{base_deck}::{deck_stack[-1]}"
            
            if getattr(config, 'anki_deck_content', False) and final_deck:
                if final_deck not in subdeck_content_map:
                    subdeck_content_map[final_deck] = {'source_lines': [], 'translation1_lines': [], 'translation2_lines': []}
                subdeck_content_map[final_deck]['source_lines'].append(source_line_raw)
                if line_index < len(target_content_lines_all):
                    subdeck_content_map[final_deck]['translation1_lines'].append(target_content_lines_all[line_index])
                if line_index < len(tertiary_content_lines_all):
                    subdeck_content_map[final_deck]['translation2_lines'].append(tertiary_content_lines_all[line_index])

            if getattr(config, 'anki_sentence_subdecks', False):
                sentence_prefix = str(content_line_idx + 1).zfill(6)
                sentence_slug = generate_filename_prefix_from_text(source_sentence, 4)
                if sentence_slug:
                    sentence_deck_name = f"{final_deck}::{sentence_prefix}-{sentence_slug}"
                    final_deck = sentence_deck_name

            if source_sentence not in doc_cache:
                doc_cache[source_sentence] = retokenize_hyphenated_compounds(current_nlp(source_sentence))
            doc = doc_cache[source_sentence]
            
            separable_verb_map = find_separable_verb_particle_pairs(doc)
            processed_particle_indices = {p.i for p in separable_verb_map.values()}
            token_mappings_matches, mapped_tokens = find_token_mappings_in_text(source_sentence, doc, token_mappings_val, config)

            for token in doc:
                if token.i in processed_particle_indices:
                    continue

                mapped_lemma_sources = {}
                if token.i in mapped_tokens:
                    if token.i in token_mappings_matches:
                        lemmas_for_current_token, mapped_sources = _extract_mapped_token(
                            token_mappings_matches[token.i], current_nlp, de_dictionary, lemma_override_rules, config, source_sentence, de_fix_genitive
                        )
                        mapped_lemma_sources.update(mapped_sources)
                    else:
                        continue
                else:
                    if not (token.is_alpha or ('-' in token.text and token.text.strip('-')) or is_composite_token(token.text)):
                        continue
                    lemmas_for_current_token, mapped_sources = _extract_standard_token(
                        token, current_nlp, de_dictionary, lemma_override_rules, source_sentence, de_fix_genitive, 
                        de_gcs, gcs_automaton, de_gcs_pos_tags, config, separable_verb_map, 
                        de_gcs_only_nouns=de_gcs_only_nouns,
                        de_gcs_combine_noun_modes=de_gcs_combine_noun_modes,
                        de_gcs_mask_unknown_parts=de_gcs_mask_unknown_parts,
                        de_gcs_preserve_compound_word=de_gcs_preserve_compound_word,
                        de_gcs_skip_merge_fractions=de_gcs_skip_merge_fractions,
                        preserve_composite_tokens=preserve_composite_tokens
                    )
                    mapped_lemma_sources.update(mapped_sources)

                deduplicated_lemmas = deduplicate_lemmas(lemmas_for_current_token)

                for lemma in deduplicated_lemmas:
                    if not lemma:
                        continue
                    
                    cur_source_word = mapped_lemma_sources.get(lemma, token.text)
                    cur_raw_source_word = token_mappings_matches[token.i]['source_word'] if (token.i in mapped_tokens and token.i in token_mappings_matches) else cur_source_word
                    if getattr(config, 'strip_garbage_characters', ''):
                        cur_source_word = cur_source_word.strip(getattr(config, 'strip_garbage_characters', ''))
                        cur_raw_source_word = cur_raw_source_word.strip(getattr(config, 'strip_garbage_characters', ''))
                    
                    data_entry = {
                        'lemma': lemma,
                        'source_word': cur_source_word,
                        'raw_source_word': cur_raw_source_word,
                        'sentence_index': content_line_idx,
                        'source_sentence': source_sentence,
                        'deck_name': final_deck
                    }

                    if getattr(config, 'deduplication_scope', 'global') == 'global':
                        is_new = lemma not in lemma_data['lemmas']
                        if is_new:
                            lemma_data['lemmas'][lemma] = cur_source_word
                            lemma_data['raw_source_words'][lemma] = cur_raw_source_word
                            lemma_data['info'][lemma] = (content_line_idx, source_sentence, final_deck)
                        elif getattr(config, 'combine_source_words', False):
                            existing_forms = [s.strip() for s in lemma_data['lemmas'][lemma].split(',') if s.strip()]
                            for form in [s.strip() for s in cur_source_word.split(',') if s.strip()]:
                                if form not in existing_forms:
                                    existing_forms.append(form)
                            lemma_data['lemmas'][lemma] = ", ".join(sort_inflected_forms(existing_forms, apo_cfg, order_cfg, prefer_lowercase_cfg))
                            if 'raw_source_words' in lemma_data:
                                existing_raw = [s.strip() for s in lemma_data['raw_source_words'].get(lemma, '').split(',') if s.strip()]
                                for form in [s.strip() for s in cur_raw_source_word.split(',') if s.strip()]:
                                    if form not in existing_raw:
                                        existing_raw.append(form)
                                lemma_data['raw_source_words'][lemma] = ", ".join(sort_inflected_forms(existing_raw, apo_cfg, order_cfg, prefer_lowercase_cfg))
                        elif getattr(config, 'prefer_shortest_form', False) and len(cur_source_word) < len(lemma_data['lemmas'][lemma]):
                            lemma_data['lemmas'][lemma] = cur_source_word
                            lemma_data['raw_source_words'][lemma] = cur_raw_source_word
                            lemma_data['info'][lemma] = (content_line_idx, source_sentence, final_deck)

                    elif getattr(config, 'deduplication_scope', 'global') == 'sentence':
                        if getattr(config, 'combine_source_words', False):
                            if lemma not in lemmas_in_sentence:
                                lemmas_in_sentence[lemma] = data_entry
                            else:
                                existing_forms = [s.strip() for s in lemmas_in_sentence[lemma]['source_word'].split(',') if s.strip()]
                                for form in [s.strip() for s in cur_source_word.split(',') if s.strip()]:
                                    if form not in existing_forms:
                                        existing_forms.append(form)
                                lemmas_in_sentence[lemma]['source_word'] = ", ".join(sort_inflected_forms(existing_forms, apo_cfg, order_cfg, prefer_lowercase_cfg))
                                existing_raw = [s.strip() for s in lemmas_in_sentence[lemma]['raw_source_word'].split(',') if s.strip()]
                                for form in [s.strip() for s in cur_raw_source_word.split(',') if s.strip()]:
                                    if form not in existing_raw:
                                        existing_raw.append(form)
                                lemmas_in_sentence[lemma]['raw_source_word'] = ", ".join(sort_inflected_forms(existing_raw, apo_cfg, order_cfg, prefer_lowercase_cfg))
                        else:
                            dedup_key = (lemma, cur_source_word.lower())
                            if dedup_key not in lemmas_in_sentence:
                                lemmas_in_sentence[dedup_key] = data_entry
                    elif getattr(config, 'deduplication_scope', 'global') == 'none':
                        lemma_data.append(data_entry)

            if getattr(config, 'deduplication_scope', 'global') == 'sentence':
                lemma_data.extend(lemmas_in_sentence.values())

        sorted_items = []
        if getattr(config, 'deduplication_scope', 'global') == 'global':
            sorted_items = sorted(list(lemma_data['lemmas'].keys()), key=lambda word: get_lemma_sort_key(word, lemma_sort_index, language))
        else:
            sorted_items = sorted(lemma_data, key=lambda x: get_lemma_sort_key(x['lemma'], lemma_sort_index, language))

        full_deck_name = ""
        if getattr(config, 'anki_create_subdecks', False) and not getattr(config, 'anki_markdown_decks', False):
            if getattr(config, 'anki_parent_deck', None):
                parent_deck_name = getattr(config, 'anki_parent_deck')
            else:
                parent_deck_name = root_deck_prefix
            if parent_deck_name != sub_deck_name:
                full_deck_name = f"{parent_deck_name}::{sub_deck_name}"
            else:
                full_deck_name = parent_deck_name

        F = get_field_index_map(anki_header) if anki_header else {}
        for item in sorted_items:
            if context and context.is_cancelled():
                break
            csv_row = [""] * len(anki_header) if anki_header else None
            word, source_word_col_val, sentence_index, source_sentence_for_lemmas, deck_name = "", "", -1, "", ""

            if getattr(config, 'deduplication_scope', 'global') == 'global':
                word = item
                sentence_index, source_sentence_for_lemmas, deck_name = lemma_data['info'].get(word, (-1, "", ""))
                if sentence_index == -1:
                    continue
                source_word_col_val = lemma_data['lemmas'].get(word, '')
                raw_source_word_col_val = lemma_data.get('raw_source_words', {}).get(word, source_word_col_val)
            else:
                word = item['lemma']
                sentence_index = item['sentence_index']
                source_sentence_for_lemmas = item['source_sentence']
                deck_name = item['deck_name']
                source_word_col_val = item['source_word']
                raw_source_word_col_val = item.get('raw_source_word', source_word_col_val)

            context_start_index = max(0, sentence_index - sentence_context_size)
            context_end_index = sentence_index + sentence_context_size + 1
            
            source_sentence_for_tsv = display_source_content_lines[sentence_index].strip() if sentence_index < len(display_source_content_lines) else ""
            target_sentence_for_tsv = display_target_content_lines[sentence_index].strip() if sentence_index < len(display_target_content_lines) else ""
            tertiary_sentence_for_tsv = display_tertiary_content_lines[sentence_index].strip() if sentence_index < len(display_tertiary_content_lines) else ""

            current_wordlist = ""
            if add_wordlist_col:
                if source_sentence_for_lemmas not in sentence_lemmas_cache:
                    wordlist_generation_args = {'de_gcs': de_gcs, 'gcs_automaton': gcs_automaton, 'de_gcs_add_parts_to_wordlist': de_gcs_add_parts_to_wordlist, 'classifications': classifications_val, 'token_mappings': getattr(config, 'token_mappings', {})}
                    lemmas = extract_lemmas_from_sentence(source_sentence_for_lemmas, lemma_sort_index, current_nlp, de_dictionary, lemma_override_rules, de_gcs_pos_tags, config, **wordlist_generation_args)
                    sentence_lemmas_cache[source_sentence_for_lemmas] = lemmas
                current_wordlist = "<br>".join(sentence_lemmas_cache[source_sentence_for_lemmas]) if wordlist_use_br else "\n".join(sentence_lemmas_cache[source_sentence_for_lemmas])
            
            CSV_ROW_DECK_VAL = ""
            if getattr(config, 'anki_markdown_decks', False):
                CSV_ROW_DECK_VAL = deck_name
            elif full_deck_name:
                CSV_ROW_DECK_VAL = full_deck_name

            source_timestamps = getattr(config, 'source_timestamps', [])
            subtitle_start_time = source_timestamps[sentence_index] if sentence_index < len(source_timestamps) else ""
            context_join_str = "<br>" if getattr(config, 'anki_context_use_br', False) else " "
            row_data = prepare_row_data(
                config,
                lemma=word,
                source_word=source_word_col_val,
                raw_source_word=raw_source_word_col_val,
                sentence_index=str(sentence_index + 1).zfill(6),
                source_sentence=source_sentence_for_tsv,
                source_context_left=context_join_str.join(line.strip() for line in display_source_content_lines[context_start_index:sentence_index]),
                source_context_right=context_join_str.join(line.strip() for line in display_source_content_lines[sentence_index + 1:context_end_index]),
                target_sentence=target_sentence_for_tsv,
                target_context_left=context_join_str.join(line.strip() for line in display_target_content_lines[context_start_index:sentence_index]),
                target_context_right=context_join_str.join(line.strip() for line in display_target_content_lines[sentence_index + 1:context_end_index]),
                tertiary_sentence=tertiary_sentence_for_tsv,
                tertiary_context_left=context_join_str.join(line.strip() for line in display_tertiary_content_lines[context_start_index:sentence_index]),
                tertiary_context_right=context_join_str.join(line.strip() for line in display_tertiary_content_lines[sentence_index + 1:context_end_index]),
                wordlist=current_wordlist,
                cloze=source_sentence_for_tsv,
                deck_name=CSV_ROW_DECK_VAL,
                subtitle_start_time=subtitle_start_time,
                classifications=classifications_val
            )
            if csv_row is not None:
                apply_field_mapping(csv_row, row_data, field_mapping, F)
            yield TabularRecord(fields=csv_row, row_data=row_data, metadata={'subdeck_content_map': subdeck_content_map})


class SingleTextStrategy(OperationalStrategy):
    """Stateless transformation strategy for single text lexical processing yielding tabular records."""
    def execute(self, config: ExtractionConfig, context: ExecutionContext) -> Iterator[TabularRecord]:
        source_text = getattr(config, 'source_text', "")
        if not source_text and getattr(config, 'source_text_content', None):
            source_text = getattr(config, 'source_text_content', "")
        lemma_sort_index = getattr(config, 'lemma_sort_index', {})
        language = getattr(config, 'language', 'de')
        sentence_context_size = getattr(config, 'sentence_context_size', 1)
        add_wordlist_col = getattr(config, 'add_wordlist_col', False)
        wordlist_use_br = getattr(config, 'wordlist_use_br', False)
        de_gcs = getattr(config, 'de_gcs', False)
        de_gcs_add_parts_to_wordlist = getattr(config, 'de_gcs_add_parts_to_wordlist', False)
        lemma_override_rules = getattr(config, 'lemma_override_rules', {})
        de_gcs_pos_tags = getattr(config, 'de_gcs_pos_tags', [])
        field_mapping = getattr(config, 'field_mapping', {})
        anki_header = getattr(config, 'anki_header', [])
        if isinstance(anki_header, tuple):
            anki_header = list(anki_header)
        if not anki_header and getattr(config, 'header', None):
            anki_header = list(getattr(config, 'header', []))

        current_nlp = context.nlp if (context and context.nlp) else nlp
        gcs_automaton = context.gcs_automaton if (context and context.gcs_automaton) else getattr(config, 'gcs_automaton', None)
        de_dictionary = context.de_dictionary if (context and context.de_dictionary) else getattr(config, 'de_dictionary', None)

        de_gcs_only_nouns = getattr(config, 'de_gcs_only_nouns', True)
        de_gcs_combine_noun_modes = getattr(config, 'de_gcs_combine_noun_modes', False)
        de_fix_genitive = getattr(config, 'de_fix_genitive', False)
        de_gcs_mask_unknown_parts = getattr(config, 'de_gcs_mask_unknown_parts', False)
        de_gcs_preserve_compound_word = getattr(config, 'de_gcs_preserve_compound_word', False)
        preserve_composite_tokens = getattr(config, 'preserve_composite_tokens', False)
        de_gcs_skip_merge_fractions = getattr(config, 'de_gcs_skip_merge_fractions', False)
        token_mappings_val = getattr(config, 'token_mappings', {})
        classifications_val = getattr(config, 'classifications', {})

        is_multiline_from_file = '\n' in source_text.strip()
        source_lines = source_text.splitlines() if is_multiline_from_file else []

        unit_texts = []
        deck_map = {}
        subdeck_content_map = {}
        header_counter = 1
        branch_header_lines = set()
        active_header_line_index = -1
        
        sub_deck_name, root_deck_prefix = self._derive_deck_prefixes(config)

        if getattr(config, 'anki_markdown_decks', False) and is_multiline_from_file:
            branch_header_lines = parse_markdown_for_branch_headers(source_lines)
            deck_stack = []
            level_stack = []
            root_prefix_md = ""
            if getattr(config, 'anki_create_subdecks', False):
                if getattr(config, 'anki_parent_deck', None):
                    root_prefix_md = getattr(config, 'anki_parent_deck')
                else:
                    root_prefix_md = root_deck_prefix
            if root_prefix_md:
                deck_stack.append(root_prefix_md)
                level_stack.append(0)

            text_has_headers = any(re.match(r'^(#+)\s+', line.strip()) for line in source_lines)
            first_real_header_level = 2 
            if text_has_headers:
                for line in source_lines:
                    match = re.match(r'^(#+)', line.strip())
                    if match:
                        first_real_header_level = len(match.group(1))
                        break

            first_header_encountered = False
            placeholder_deck_created = False

            for line_index, line_raw in enumerate(source_lines):
                if context and context.is_cancelled():
                    break
                line = line_raw.strip()
                if not line:
                    continue
                
                header_match = re.match(r'^(#+)\s+(.*)', line)
                if header_match:
                    first_header_encountered = True
                    active_header_line_index = line_index
                    level = len(header_match.group(1))
                    title = header_match.group(2).strip()
                    sanitized_title = generate_filename_prefix_from_text(title, 5)

                    while level_stack and level_stack[-1] >= level:
                        level_stack.pop()
                        deck_stack.pop()

                    if sanitized_title:
                        deck_stack.append(f"{100000 + header_counter}-{sanitized_title}")
                        level_stack.append(level)
                        header_counter += 1
                    line = title
                elif not first_header_encountered and not placeholder_deck_created and text_has_headers:
                    level = first_real_header_level
                    while level_stack and level_stack[-1] >= level:
                        level_stack.pop()
                        deck_stack.pop()

                    title = line
                    sanitized_title = generate_filename_prefix_from_text(title, 5)
                    if sanitized_title:
                        deck_stack.append(f"{100000 + header_counter}-{sanitized_title}")
                        level_stack.append(level)
                        header_counter += 1
                    placeholder_deck_created = True

                base_deck = "::".join(deck_stack)
                final_deck = base_deck
                if active_header_line_index in branch_header_lines:
                    final_deck = f"{base_deck}::{deck_stack[-1]}"

                if getattr(config, 'anki_deck_content', False) and final_deck:
                    if final_deck not in subdeck_content_map:
                        subdeck_content_map[final_deck] = {'source_lines': []}
                    subdeck_content_map[final_deck]['source_lines'].append(line_raw)

                if getattr(config, 'anki_sentence_subdecks', False):
                    sentence_prefix = str(len(unit_texts) + 1).zfill(6)
                    sentence_slug = generate_filename_prefix_from_text(line, 4)
                    if sentence_slug:
                        sentence_deck_name = f"{final_deck}::{sentence_prefix}-{sentence_slug}"
                        final_deck = sentence_deck_name

                deck_map[len(unit_texts)] = final_deck
                unit_texts.append(line)
        else:
            if is_multiline_from_file:
                unit_texts = [line.strip() for line in source_lines if line.strip()]
            else:
                doc = retokenize_hyphenated_compounds(current_nlp(source_text))
                unit_texts = [sent.text for sent in doc.sents]

        strip_config = {'source': False}
        strip_headers = getattr(config, 'strip_headers', None)
        if strip_headers is not None:
            targets = strip_headers if strip_headers else ['all']
            if 'all' in targets or 'source' in targets:
                strip_config['source'] = True

        display_unit_texts = [_strip_markdown_header(unit) for unit in unit_texts] if strip_config['source'] else unit_texts

        lemma_data = {}
        if getattr(config, 'deduplication_scope', 'global') == 'global':
            lemma_data = {'lemmas': {}, 'info': {}, 'raw_source_words': {}}
        else:
            lemma_data = []

        order_cfg = getattr(config, 'combine_source_words_order', 'contractions_first')
        prefer_lowercase_cfg = getattr(config, 'combine_source_words_prefer_lowercase', True)
        apo_str = getattr(config, 'apostrophe_chars', "', ’, ‘, `, ´, ʼ")
        apo_cfg = tuple(c.strip() for c in apo_str.strip('"').split(',') if c.strip())

        doc_cache = {}

        for unit_index, unit_text in enumerate(unit_texts):
            if context and context.is_cancelled():
                break
            lemmas_in_sentence = {}
            if unit_text not in doc_cache:
                doc_cache[unit_text] = retokenize_hyphenated_compounds(current_nlp(unit_text))
            unit_doc = doc_cache[unit_text]

            current_deck = deck_map.get(unit_index, "")
            separable_verb_map = find_separable_verb_particle_pairs(unit_doc)
            processed_particle_indices = {p.i for p in separable_verb_map.values()}
            token_mappings_matches, mapped_tokens = find_token_mappings_in_text(unit_text, unit_doc, token_mappings_val, config)

            for token in unit_doc:
                if token.i in processed_particle_indices:
                    continue

                mapped_lemma_sources = {}
                if token.i in mapped_tokens:
                    if token.i in token_mappings_matches:
                        lemmas_for_current_token, mapped_sources = _extract_mapped_token(
                            token_mappings_matches[token.i], current_nlp, de_dictionary, lemma_override_rules, config, unit_text, de_fix_genitive
                        )
                        mapped_lemma_sources.update(mapped_sources)
                    else:
                        continue
                else:
                    if not (token.is_alpha or ('-' in token.text and token.text.strip('-')) or is_composite_token(token.text)):
                        continue
                    lemmas_for_current_token, mapped_sources = _extract_standard_token(
                        token, current_nlp, de_dictionary, lemma_override_rules, unit_text, de_fix_genitive, 
                        de_gcs, gcs_automaton, de_gcs_pos_tags, config, separable_verb_map, 
                        de_gcs_only_nouns=de_gcs_only_nouns,
                        de_gcs_combine_noun_modes=de_gcs_combine_noun_modes,
                        de_gcs_mask_unknown_parts=de_gcs_mask_unknown_parts,
                        de_gcs_preserve_compound_word=de_gcs_preserve_compound_word,
                        de_gcs_skip_merge_fractions=de_gcs_skip_merge_fractions,
                        preserve_composite_tokens=preserve_composite_tokens
                    )
                    mapped_lemma_sources.update(mapped_sources)

                deduplicated_lemmas = deduplicate_lemmas(lemmas_for_current_token)

                for lemma in deduplicated_lemmas:
                    if not lemma:
                        continue

                    cur_source_word = mapped_lemma_sources.get(lemma, token.text)
                    cur_raw_source_word = token_mappings_matches[token.i]['source_word'] if (token.i in mapped_tokens and token.i in token_mappings_matches) else cur_source_word
                    if getattr(config, 'strip_garbage_characters', ''):
                        cur_source_word = cur_source_word.strip(getattr(config, 'strip_garbage_characters', ''))
                        cur_raw_source_word = cur_raw_source_word.strip(getattr(config, 'strip_garbage_characters', ''))

                    data_entry = {
                        'lemma': lemma,
                        'source_word': cur_source_word,
                        'raw_source_word': cur_raw_source_word,
                        'sentence_index': unit_index,
                        'source_sentence': unit_text,
                        'deck_name': current_deck
                    }

                    if getattr(config, 'deduplication_scope', 'global') == 'global':
                        is_new = lemma not in lemma_data['lemmas']
                        if is_new:
                            lemma_data['lemmas'][lemma] = cur_source_word
                            lemma_data['raw_source_words'][lemma] = cur_raw_source_word
                            lemma_data['info'][lemma] = (unit_index, unit_text, current_deck)
                        elif getattr(config, 'combine_source_words', False):
                            existing_forms = [s.strip() for s in lemma_data['lemmas'][lemma].split(',') if s.strip()]
                            for form in [s.strip() for s in cur_source_word.split(',') if s.strip()]:
                                if form not in existing_forms:
                                    existing_forms.append(form)
                            lemma_data['lemmas'][lemma] = ", ".join(sort_inflected_forms(existing_forms, apo_cfg, order_cfg, prefer_lowercase_cfg))
                            if 'raw_source_words' in lemma_data:
                                existing_raw = [s.strip() for s in lemma_data['raw_source_words'].get(lemma, '').split(',') if s.strip()]
                                for form in [s.strip() for s in cur_raw_source_word.split(',') if s.strip()]:
                                    if form not in existing_raw:
                                        existing_raw.append(form)
                                lemma_data['raw_source_words'][lemma] = ", ".join(sort_inflected_forms(existing_raw, apo_cfg, order_cfg, prefer_lowercase_cfg))
                        elif getattr(config, 'prefer_shortest_form', False) and len(cur_source_word) < len(lemma_data['lemmas'][lemma]):
                            lemma_data['lemmas'][lemma] = cur_source_word
                            lemma_data['raw_source_words'][lemma] = cur_raw_source_word
                            lemma_data['info'][lemma] = (unit_index, unit_text, current_deck)
                            
                    elif getattr(config, 'deduplication_scope', 'global') == 'sentence':
                        if getattr(config, 'combine_source_words', False):
                            if lemma not in lemmas_in_sentence:
                                lemmas_in_sentence[lemma] = data_entry
                            else:
                                existing_forms = [s.strip() for s in lemmas_in_sentence[lemma]['source_word'].split(',') if s.strip()]
                                for form in [s.strip() for s in cur_source_word.split(',') if s.strip()]:
                                    if form not in existing_forms:
                                        existing_forms.append(form)
                                lemmas_in_sentence[lemma]['source_word'] = ", ".join(sort_inflected_forms(existing_forms, apo_cfg, order_cfg, prefer_lowercase_cfg))
                                existing_raw = [s.strip() for s in lemmas_in_sentence[lemma]['raw_source_word'].split(',') if s.strip()]
                                for form in [s.strip() for s in cur_raw_source_word.split(',') if s.strip()]:
                                    if form not in existing_raw:
                                        existing_raw.append(form)
                                lemmas_in_sentence[lemma]['raw_source_word'] = ", ".join(sort_inflected_forms(existing_raw, apo_cfg, order_cfg, prefer_lowercase_cfg))
                        else:
                            dedup_key = (lemma, cur_source_word.lower())
                            if dedup_key not in lemmas_in_sentence:
                                lemmas_in_sentence[dedup_key] = data_entry
                    elif getattr(config, 'deduplication_scope', 'global') == 'none':
                        lemma_data.append(data_entry)

            if getattr(config, 'deduplication_scope', 'global') == 'sentence':
                lemma_data.extend(lemmas_in_sentence.values())

        sorted_items = []
        if getattr(config, 'deduplication_scope', 'global') == 'global':
            sorted_items = sorted(list(lemma_data['lemmas'].keys()), key=lambda word: get_lemma_sort_key(word, lemma_sort_index, language))
        else:
            sorted_items = sorted(lemma_data, key=lambda x: get_lemma_sort_key(x['lemma'], lemma_sort_index, language))
        
        sentence_lemmas_cache = {}

        full_deck_name = ""
        if getattr(config, 'anki_create_subdecks', False) and not getattr(config, 'anki_markdown_decks', False):
            if getattr(config, 'anki_parent_deck', None):
                parent_deck_name = getattr(config, 'anki_parent_deck')
            else:
                parent_deck_name = root_deck_prefix
            if parent_deck_name != sub_deck_name:
                full_deck_name = f"{parent_deck_name}::{sub_deck_name}"
            else:
                full_deck_name = parent_deck_name

        F = get_field_index_map(anki_header) if anki_header else {}
        for item in sorted_items:
            if context and context.is_cancelled():
                break
            csv_row = [""] * len(anki_header) if anki_header else None
            word, source_word_col_val, unit_index, source_sentence_for_lemmas, deck_name = "", "", -1, "", ""

            if getattr(config, 'deduplication_scope', 'global') == 'global':
                word = item
                unit_index, source_sentence_for_lemmas, deck_name = lemma_data['info'].get(word, (-1, "", ""))
                if unit_index == -1:
                    continue
                source_word_col_val = lemma_data['lemmas'].get(word, '')
                raw_source_word_col_val = lemma_data.get('raw_source_words', {}).get(word, source_word_col_val)
            else:
                word = item['lemma']
                unit_index = item['sentence_index']
                source_sentence_for_lemmas = item['source_sentence']
                deck_name = item['deck_name']
                source_word_col_val = item['source_word']
                raw_source_word_col_val = item.get('raw_source_word', source_word_col_val)
            
            source_sentence_for_tsv = display_unit_texts[unit_index].strip() if unit_index < len(display_unit_texts) else ""
            context_start_index = max(0, unit_index - sentence_context_size)
            context_end_index = min(len(display_unit_texts), unit_index + sentence_context_size + 1)
            
            current_wordlist = ""
            if add_wordlist_col:
                if source_sentence_for_lemmas not in sentence_lemmas_cache:
                    wordlist_generation_args = {'de_gcs': de_gcs, 'gcs_automaton': gcs_automaton, 'de_gcs_add_parts_to_wordlist': de_gcs_add_parts_to_wordlist, 'classifications': classifications_val, 'token_mappings': getattr(config, 'token_mappings', {})}
                    lemmas = extract_lemmas_from_sentence(source_sentence_for_lemmas, lemma_sort_index, current_nlp, de_dictionary, lemma_override_rules, de_gcs_pos_tags, config, **wordlist_generation_args)
                    sentence_lemmas_cache[source_sentence_for_lemmas] = lemmas
                current_wordlist = "<br>".join(sentence_lemmas_cache[source_sentence_for_lemmas]) if wordlist_use_br else "\n".join(sentence_lemmas_cache[source_sentence_for_lemmas])

            CSV_ROW_DECK_VAL = ""
            if getattr(config, 'anki_markdown_decks', False):
                CSV_ROW_DECK_VAL = deck_name
            elif full_deck_name:
                CSV_ROW_DECK_VAL = full_deck_name

            source_timestamps = getattr(config, 'source_timestamps', [])
            subtitle_start_time = source_timestamps[unit_index] if unit_index < len(source_timestamps) else ""
            context_join_str = "<br>" if getattr(config, 'anki_context_use_br', False) else " "
            
            left_str = context_join_str.join(u.strip() for u in display_unit_texts[context_start_index:unit_index])
            right_str = context_join_str.join(u.strip() for u in display_unit_texts[unit_index + 1:context_end_index])
            
            row_data = prepare_row_data(
                config,
                lemma=word,
                source_word=source_word_col_val,
                raw_source_word=raw_source_word_col_val,
                source_sentence=source_sentence_for_tsv,
                source_context_left=left_str,
                source_context_right=right_str,
                wordlist=current_wordlist,
                cloze=source_sentence_for_tsv,
                sentence_index=str(unit_index + 1).zfill(6),
                deck_name=CSV_ROW_DECK_VAL,
                subtitle_start_time=subtitle_start_time,
                classifications=classifications_val
            )
            if csv_row is not None:
                apply_field_mapping(csv_row, row_data, field_mapping, F)
            yield TabularRecord(
                fields=csv_row,
                row_data=row_data,
                metadata={'subdeck_content_map': subdeck_content_map}
            )


class ParallelSentencesStrategy(OperationalStrategy):
    """Stateless operational strategy for processing parallel sentences yielding tabular records."""
    def execute(self, config: ExtractionConfig, context: ExecutionContext) -> Iterator[TabularRecord]:
        source_text = getattr(config, 'source_text_content', "")
        if not source_text and getattr(config, 'source_text', None):
            source_text = getattr(config, 'source_text', "")
        lemma_sort_index = getattr(config, 'lemma_sort_index', {})
        language = getattr(config, 'language', 'de')
        sentence_context_size = getattr(config, 'sentence_context_size', 1)
        add_wordlist_col = getattr(config, 'add_wordlist_col', False)
        wordlist_use_br = getattr(config, 'wordlist_use_br', False)
        lemma_override_rules = getattr(config, 'lemma_override_rules', {})
        de_gcs = getattr(config, 'de_gcs', False)
        de_gcs_pos_tags = getattr(config, 'de_gcs_pos_tags', [])
        field_mapping = getattr(config, 'field_mapping', {})
        anki_header = getattr(config, 'anki_header', [])
        if isinstance(anki_header, tuple):
            anki_header = list(anki_header)
        if not anki_header and getattr(config, 'header', None):
            anki_header = list(getattr(config, 'header', []))

        current_nlp = context.nlp if (context and context.nlp) else nlp
        classifications_val = getattr(config, 'classifications', {})

        source_text_lines_all = [line.rstrip("\n") for line in source_text.splitlines()] if source_text else []
        target_content_lines_all = []
        tgt_content = getattr(config, 'target_text_content', None)
        if tgt_content:
            target_content_lines_all = [line.rstrip("\n") for line in tgt_content.splitlines()]
        tertiary_content_lines_all = []
        tert_content = getattr(config, 'tertiary_text_content', None)
        if tert_content:
            tertiary_content_lines_all = [line.rstrip("\n") for line in tert_content.splitlines()]

        strip_config = {'source': False, 'translations': False}
        strip_headers = getattr(config, 'strip_headers', None)
        if strip_headers is not None:
            targets = strip_headers if strip_headers else ['all']
            if 'all' in targets or 'source' in targets:
                strip_config['source'] = True
            if 'all' in targets or 'translations' in targets:
                strip_config['translations'] = True

        display_source_lines_all = [_strip_markdown_header(line) for line in source_text_lines_all] if strip_config['source'] else source_text_lines_all
        display_target_lines_all = [_strip_markdown_header(line) for line in target_content_lines_all] if strip_config['translations'] else target_content_lines_all
        display_tertiary_lines_all = [_strip_markdown_header(line) for line in tertiary_content_lines_all] if strip_config['translations'] else tertiary_content_lines_all
        
        display_source_content_lines = [line for line in display_source_lines_all if line.strip()]
        display_target_content_lines = [line for line in display_target_lines_all if line.strip()]
        display_tertiary_content_lines = [line for line in display_tertiary_lines_all if line.strip()]

        sub_deck_name, root_deck_prefix = self._derive_deck_prefixes(config)

        full_deck_name = ""
        if getattr(config, 'anki_create_subdecks', False) and not getattr(config, 'anki_markdown_decks', False):
            if getattr(config, 'anki_parent_deck', None):
                parent_deck_name = getattr(config, 'anki_parent_deck')
            else:
                parent_deck_name = root_deck_prefix
            if parent_deck_name != sub_deck_name:
                full_deck_name = f"{parent_deck_name}::{sub_deck_name}"
            else:
                full_deck_name = parent_deck_name

        F = get_field_index_map(anki_header) if anki_header else {}
        deck_stack = []
        level_stack = []
        subdeck_content_map = {}
        sentence_lemmas_cache = {}
        header_counter = 1
        branch_header_lines = set()
        if getattr(config, 'anki_markdown_decks', False):
            branch_header_lines = parse_markdown_for_branch_headers(source_text_lines_all)
            root_prefix_md = ""
            if getattr(config, 'anki_create_subdecks', False):
                if getattr(config, 'anki_parent_deck', None):
                    root_prefix_md = getattr(config, 'anki_parent_deck')
                else:
                    root_prefix_md = root_deck_prefix
            if root_prefix_md:
                deck_stack.append(root_prefix_md)
                level_stack.append(0)

        text_has_headers = any(re.match(r'^(#+)\s+', line.strip()) for line in source_text_lines_all)
        first_real_header_level = 2 
        if text_has_headers:
            for line in source_text_lines_all:
                match = re.match(r'^(#+)', line.strip())
                if match:
                    first_real_header_level = len(match.group(1))
                    break
        
        content_line_idx = -1
        active_header_line_index = -1
        first_header_encountered = False
        placeholder_deck_created = False

        for line_index, source_line_raw in enumerate(source_text_lines_all):
            if context and context.is_cancelled():
                break
            if not source_line_raw.strip():
                continue

            source_line_for_analysis = source_line_raw.strip()
            if getattr(config, 'anki_markdown_decks', False):
                header_match = re.match(r'^(#+)\s+(.*)', source_line_for_analysis)
                if header_match:
                    first_header_encountered = True
                    active_header_line_index = line_index
                    level = len(header_match.group(1))
                    title = header_match.group(2).strip()
                    sanitized_title = generate_filename_prefix_from_text(title, 5)

                    while level_stack and level_stack[-1] >= level:
                        level_stack.pop()
                        deck_stack.pop()

                    if sanitized_title:
                        deck_stack.append(f"{100000 + header_counter}-{sanitized_title}")
                        level_stack.append(level)
                        header_counter += 1
                    source_line_for_analysis = title
                elif not first_header_encountered and not placeholder_deck_created and text_has_headers:
                    level = first_real_header_level
                    while level_stack and level_stack[-1] >= level:
                        level_stack.pop()
                        deck_stack.pop()

                    title = source_line_for_analysis
                    sanitized_title = generate_filename_prefix_from_text(title, 5)
                    if sanitized_title:
                        deck_stack.append(f"{100000 + header_counter}-{sanitized_title}")
                        level_stack.append(level)
                        header_counter += 1
                    placeholder_deck_created = True

            base_deck = "::".join(deck_stack)
            final_deck_for_content = base_deck
            if active_header_line_index in branch_header_lines:
                final_deck_for_content = f"{base_deck}::{deck_stack[-1]}"

            if getattr(config, 'anki_deck_content', False) and final_deck_for_content:
                if final_deck_for_content not in subdeck_content_map:
                    subdeck_content_map[final_deck_for_content] = {'source_lines': [], 'translation1_lines': [], 'translation2_lines': []}
                subdeck_content_map[final_deck_for_content]['source_lines'].append(source_line_raw)
                if line_index < len(target_content_lines_all):
                    subdeck_content_map[final_deck_for_content]['translation1_lines'].append(target_content_lines_all[line_index])
                if line_index < len(tertiary_content_lines_all):
                    subdeck_content_map[final_deck_for_content]['translation2_lines'].append(tertiary_content_lines_all[line_index])

            content_line_idx += 1
            if content_line_idx >= len(display_source_content_lines):
                break

            csv_row = [""] * len(anki_header) if anki_header else None
            source_sentence = display_source_content_lines[content_line_idx].strip()
            target_sentence = display_target_content_lines[content_line_idx].strip() if content_line_idx < len(display_target_content_lines) else ""
            tertiary_sentence = display_tertiary_content_lines[content_line_idx].strip() if content_line_idx < len(display_tertiary_content_lines) else ""
            
            context_start_index = max(0, content_line_idx - sentence_context_size)
            context_end_index = content_line_idx + sentence_context_size + 1

            current_wordlist = ""
            if add_wordlist_col:
                source_sentence_for_lemmas = source_text_lines_all[line_index]
                if source_sentence_for_lemmas not in sentence_lemmas_cache:
                    wordlist_generation_args = {'de_gcs': de_gcs, 'gcs_automaton': None, 'classifications': getattr(config, 'classifications', {}), 'token_mappings': getattr(config, 'token_mappings', {})}
                    lemmas = extract_lemmas_from_sentence(source_sentence_for_lemmas, lemma_sort_index, current_nlp, None, lemma_override_rules, de_gcs_pos_tags, config, **wordlist_generation_args)
                    sentence_lemmas_cache[source_sentence_for_lemmas] = lemmas
                current_wordlist = "<br>".join(sentence_lemmas_cache[source_sentence_for_lemmas]) if wordlist_use_br else "\n".join(sentence_lemmas_cache[source_sentence_for_lemmas])

            final_deck_for_card = ""
            if getattr(config, 'anki_markdown_decks', False):
                final_deck_for_card = "::".join(deck_stack)
                if active_header_line_index in branch_header_lines:
                    final_deck_for_card = f"{final_deck_for_card}::{deck_stack[-1]}"
                
                if getattr(config, 'anki_sentence_subdecks', False):
                    sentence_prefix = str(content_line_idx + 1).zfill(6)
                    sentence_slug = generate_filename_prefix_from_text(source_sentence, 4)
                    if sentence_slug:
                        sentence_deck_name = f"{final_deck_for_card}::{sentence_prefix}-{sentence_slug}"
                        final_deck_for_card = sentence_deck_name
            elif full_deck_name:
                final_deck_for_card = full_deck_name

            source_timestamps = getattr(config, 'source_timestamps', [])
            subtitle_start_time = source_timestamps[content_line_idx] if content_line_idx < len(source_timestamps) else ""
            context_join_str = "<br>" if getattr(config, 'anki_context_use_br', False) else " "
            row_data = prepare_row_data(
                config,
                source_sentence=source_sentence,
                source_context_left=context_join_str.join(line.strip() for line in display_source_content_lines[context_start_index:content_line_idx]),
                source_context_right=context_join_str.join(line.strip() for line in display_source_content_lines[content_line_idx + 1:context_end_index]),
                target_sentence=target_sentence,
                target_context_left=context_join_str.join(line.strip() for line in display_target_content_lines[context_start_index:content_line_idx]),
                target_context_right=context_join_str.join(line.strip() for line in display_target_content_lines[content_line_idx + 1:context_end_index]),
                tertiary_sentence=tertiary_sentence,
                tertiary_context_left=context_join_str.join(line.strip() for line in display_tertiary_content_lines[context_start_index:content_line_idx]),
                tertiary_context_right=context_join_str.join(line.strip() for line in display_tertiary_content_lines[content_line_idx + 1:context_end_index]),
                wordlist=current_wordlist,
                cloze=source_sentence,
                sentence_index=str(content_line_idx + 1).zfill(6),
                deck_name=final_deck_for_card,
                subtitle_start_time=subtitle_start_time,
                classifications=classifications_val
            )

            if csv_row is not None:
                apply_field_mapping(csv_row, row_data, field_mapping, F)
            yield TabularRecord(fields=csv_row, row_data=row_data, metadata={'subdeck_content_map': subdeck_content_map})


class LemmasPerLineStrategy(OperationalStrategy):
    """Stateless transformation strategy for extracting line-by-line lemmas without persistence concerns."""
    def execute(self, config: ExtractionConfig, context: ExecutionContext) -> Iterator[TabularRecord]:
        source_text_content = getattr(config, 'source_text_content', "")
        source_lines = source_text_content.splitlines() if source_text_content else []
        lemma_sort_index = getattr(config, 'lemma_sort_index', {})
        de_dictionary = context.de_dictionary if (context and context.de_dictionary) else getattr(config, 'de_dictionary', None)
        lemma_override_rules = getattr(config, 'lemma_override_rules', {})
        current_nlp = context.nlp if (context and context.nlp) else nlp

        for line in source_lines:
            if context and context.is_cancelled():
                break
            line_str = line.strip()
            if not line_str:
                yield TabularRecord(raw_line="")
                continue
            lemmas = extract_lemmas_from_sentence(
                line_str, lemma_sort_index, current_nlp, de_dictionary,
                lemma_override_rules, [], config, de_gcs=False
            )
            output_line = " ".join(lemmas)
            yield TabularRecord(raw_line=output_line)


class ModeDispatcher:
    """Immutable mode dispatcher routing operational modes directly to standalone strategy handlers."""
    def __init__(self):
        self._strategies: Dict[OperationalMode, OperationalStrategy] = {
            OperationalMode.PARALLEL_TEXTS: ParallelTextsStrategy(),
            OperationalMode.SINGLE_TEXT: SingleTextStrategy(),
            OperationalMode.PARALLEL_SENTENCES: ParallelSentencesStrategy(),
            OperationalMode.LEMMAS_PER_LINE: LemmasPerLineStrategy(),
        }

    def get_strategy(self, mode: Union[OperationalMode, str, Any]) -> OperationalStrategy:
        if isinstance(mode, str):
            try:
                mode = OperationalMode(mode)
            except ValueError:
                pass
        if mode not in self._strategies:
            raise ValueError(f"Unknown or unregistered operational mode: {mode}")
        return self._strategies[mode]

    def dispatch(self, mode: Union[OperationalMode, str, Any], config: ExtractionConfig, context: ExecutionContext) -> Iterator[TabularRecord]:
        strategy = self.get_strategy(mode)
        return strategy.execute(config, context)


def main():
    import configparser
    from pathlib import Path

    # --- Auto-lite redirection check ---
    config_path = Path(__file__).resolve().parent.parent.parent.parent / 'config.ini'
    auto_lite_mode = False
    config_use_simplemma = False
    if config_path.exists():
        config = configparser.ConfigParser(allow_no_value=True)
        config.read(config_path, encoding='utf-8')
        if 'optimization' in config and config.getboolean('optimization', 'auto_lite_mode', fallback=False):
            auto_lite_mode = True
        for sec in ['settings', 'lemmatization']:
            if config.has_section(sec):
                for opt in ['use_simplemma_correction', 'simplemma_after_spacy', 'simplemma_pos_aware', 'simplemma_smart_fallback']:
                    if config.has_option(sec, opt) and config.getboolean(sec, opt, fallback=False):
                        config_use_simplemma = True

    if auto_lite_mode:
        input_text = ""
        if len(sys.argv) == 2 and not sys.argv[1].startswith('-'):
            input_text = sys.argv[1]
        elif "--text" in sys.argv:
            text_idx = sys.argv.index("--text")
            if text_idx + 1 < len(sys.argv):
                input_text = sys.argv[text_idx + 1]

        if input_text:
            cleaned = input_text.strip()
            # Intercept only if it's a single word, no file output is requested, and GCS/Simplemma are not requested
            if (cleaned and " " not in cleaned and "\n" not in cleaned and "\t" not in cleaned and 
                "--output-file" not in sys.argv and "--stdout-print-output-basename" not in sys.argv and
                "--de-gcs" not in sys.argv and "--use-simplemma-correction" not in sys.argv and
                "--simplemma-after-spacy" not in sys.argv and "--simplemma-pos-aware" not in sys.argv and
                "--simplemma-smart-fallback" not in sys.argv and
                not config_use_simplemma):
                lang = ""
                if "--language" in sys.argv:
                    lang_idx = sys.argv.index("--language")
                    if lang_idx + 1 < len(sys.argv):
                        lang = sys.argv[lang_idx + 1]
                
                has_html_format = False
                original_argv = sys.argv[:]
                if "--stdout-format" in original_argv:
                    fmt_idx = original_argv.index("--stdout-format")
                    if fmt_idx + 1 < len(original_argv) and original_argv[fmt_idx + 1] == "html":
                        has_html_format = True
                
                sys.argv = [original_argv[0]]
                if lang:
                    sys.argv.append(f"--langs={lang}")
                sys.argv.append(cleaned)
                
                try:
                    import contextlib
                    import kardenwort_lite
                    
                    f = io.StringIO()
                    f.reconfigure = lambda *args, **kwargs: None
                    with contextlib.redirect_stdout(f):
                        kardenwort_lite.main()
                        
                    lemma = f.getvalue()
                    
                    if has_html_format:
                        print(f"<table>\n<tr><td>{lemma}</td><td>{cleaned}</td></tr>\n</table>\n", end="")
                    else:
                        print(lemma, end="")
                    sys.exit(0)
                except ImportError:
                    sys.argv = original_argv
                    pass # Fall back to heavy mode if lite script is missing

    # --- End Auto-lite check ---
    import spacy

    parser = argparse.ArgumentParser(
        description="Extract and process words or sentences from text.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    input_output_group = parser.add_argument_group('Input & Output')
    processing_mode_group = parser.add_mutually_exclusive_group(required=True)
    processing_mode_group.add_argument("--type", choices=["word", "sentence", "sort-frequency"], help="Specify the processing type: 'word' for word extraction, 'sentence' for parallel sentence processing, 'sort-frequency' to sort lemmas from stdin by frequency.")
    processing_mode_group.add_argument("--lemmas-per-line", action="store_true", help="Process each line of text1-file to output a single line of frequency-sorted lemmas.")
    input_output_group.add_argument("--language", default="de", choices=["de", "en"], help="The language of the text to be processed.")
    input_output_group.add_argument("--tts-destination-lang", default="ru", help="The destination language for TTS field activation (e.g., 'ru', 'en').")
    input_output_group.add_argument("--text", help="A single string of input text to process. Mutually exclusive with --text1-file.")
    input_output_group.add_argument("--text1-file", help="Path to the primary input text file.")
    input_output_group.add_argument("--text2-file", help="Path to a parallel (translated) text file.")
    input_output_group.add_argument("--text3-file", help="Path to a third parallel text file.")
    input_output_group.add_argument("--output-file", help="Path to the output file. If not provided, results are printed to standard output.")
    input_output_group.add_argument("--multi-text", action="store_true", help="Parse input from --text or stdin as up to three texts separated by '---'.")
    input_output_group.add_argument("--subtitle-timestamps-file", help="Path to the sidecar subtitle timestamps file.")
    data_files_group = parser.add_argument_group('Data Files')
    data_files_group.add_argument("--lemma-index-file", default="", help="Path to a CSV file with lemmas, used for frequency-based sorting of the output.")
    data_files_group.add_argument("--lemma-override-file", help="Path to a TSV file that defines rules for correcting specific lemma results.")
    data_files_group.add_argument("--de-dictionary-file", default="german.dic", help="Path to the dictionary file for German-specific operations.")
    data_files_group.add_argument("--classify", action="append", help="Classification dictionary in format name=path.tsv. Can be specified multiple times.")
    data_files_group.add_argument("--disable-classification", action="store_true", help="Disable loading classifications from config.ini.")
    
    parser.add_argument("--use-simplemma-correction", action="store_true", help="Apply simplemma as an unconditional override after SpaCy processing.")
    parser.add_argument("--simplemma-after-spacy", action="store_true", help="Sequential post-processing mode where Simplemma evaluates SpaCy derived lemma.")
    parser.add_argument("--simplemma-pos-aware", action="store_true", help="Lower-case input string passed to Simplemma at sentence start if not a noun or proper noun.")
    parser.add_argument("--simplemma-smart-fallback", action="store_true", help="Evaluate Simplemma solely when SpaCy returns an unreduced inflected verb or an unverified dictionary lemma.")

    filename_group = parser.add_argument_group('Output Filename Generation')
    filename_group.add_argument("--basename-add-timestamp", action="store_true", help="Prepend the output filename with a 'YYYYMMDDHHMMSS' timestamp.")
    filename_group.add_argument("--basename-add-first-words", nargs='?', type=int, const=4, default=None, help="Automatically generate part of the filename from the first N words of the text. Defaults to 4 words if no number is given.")
    filename_group.add_argument("--stdout-print-output-basename", action="store_true", help="Print the basename of the generated output file to stdout. Useful for scripting.")

    output_format_group = parser.add_argument_group('Output Content & Formatting')
    output_format_group.add_argument("--wordlist-use-br", action="store_true", help="Use HTML <br> tags instead of newlines as separators in the wordlist column. Automatically enabled if wordlist is in the mapping.")
    output_format_group.add_argument("--anki-context-use-br", action="store_true", help="Use HTML <br> tags instead of spaces as separators in context columns.")
    output_format_group.add_argument("--add-header", action="store_true", default=True, help="Prepend the output file with the full Anki CSV header.")
    output_format_group.add_argument("--sentence-context-size", type=int, default=1, help="The number of sentences to include before and after the source sentence as context.")
    output_format_group.add_argument("--anki-create-subdecks", action="store_true", help="Automatically generate a parent deck and sub-decks for Anki based on the output filename.")
    output_format_group.add_argument("--anki-markdown-decks", action="store_true", help="Parse Markdown headers in source text to create a hierarchical deck structure in Anki.")
    output_format_group.add_argument("--anki-sentence-subdecks", action="store_true", help="Create a final subdeck level for each sentence. Requires --anki-markdown-decks.")
    output_format_group.add_argument("--anki-parent-deck", help="Manually specify the parent deck name, overriding the auto-generated one. Requires --anki-create-subdecks.")
    output_format_group.add_argument("--anki-deck-content", nargs='+', choices=['parent-source', 'parent-translations', 'subdeck-source', 'subdeck-translations'], help="Adds content to the Anki deck description. 'parent-source': adds full source text to parent deck. 'subdeck-source': adds relevant source text part to each subdeck.")
    output_format_group.add_argument(
        "--strip-headers",
        nargs='*',
        choices=['all', 'source', 'translations'],
        help="Strip Markdown headers (#) from text fields in the final TSV output. 'all': strip from source and translations. 'source': only from source. 'translations': only from translations. If the flag is present without arguments, it defaults to 'all'."
    )
    output_format_group.add_argument(
        "--anki-field-mapping",
        type=str,
        default=None,
        help="JSON string mapping Anki field names to internal data source names. "
             "Used to customize which data populates which field in the output TSV. "
             "Example: '{\"WordSourceAI\": \"source_word\", \"Quotation\": \"lemma\"}'"
    )
    output_format_group.add_argument(
        "--anki-csv-header",
        type=str,
        default=None,
        help="JSON string list of Anki field names for CSV header and order."
    )
    stdout_group = parser.add_argument_group('Standard Output (STDOUT) Arguments (used only if --output is not specified)')
    output_format_group.add_argument("--stdout-format", choices=['list', 'context', 'tsv', 'html'], default='list', 
                               help="Select the output format for STDOUT if --output-file is not specified.\n"
                                    "'list' (default): A simple, one-lemma-per-line list.\n"
                                    "'context': Lemmas with full sentence context.\n"
                                    "'tsv': A two-column list (lemma, source word) separated by a tab.\n"
                                    "'html': The two-column list formatted as an HTML table.")

    lemmatization_group = parser.add_argument_group('Lemmatization Control')
    lemmatization_group.add_argument("--force-proper-noun-capitalization", action="store_true", help="Force capitalization of proper noun lemmas (PROPN).")
    lemmatization_group.add_argument("--deduplication-scope", choices=['global', 'sentence', 'none'], default='global', help="Set the scope for lemma deduplication. 'global': unique lemmas across the entire text. 'sentence': unique lemmas within each sentence. 'none': no duplication, one entry per word occurrence.")
    lemmatization_group.add_argument("--prefer-shortest-form", action="store_true", help="When deduplicating globally, prefer the shortest word form of a lemma, even if it appears later in the text. Default is to keep the first occurrence.")
    lemmatization_group.add_argument("--preserve-composite-tokens", action="store_true", help="Keep the whole composite token / hyphenated compound lemma in addition to decomposed sub-lemmas.")
    lemmatization_group.add_argument("--combine-source-words", action="store_true", help="When deduplicating globally, combine different source word forms for the same lemma by separating them with a comma. Default is to keep only one.")
    lemmatization_group.add_argument("--combine-source-words-order", choices=['contractions_first', 'occurrence', 'alphabetical'], default=None, help="Set order for combined inflected forms when --combine-source-words is enabled.")
    lemmatization_group.add_argument("--apostrophe-chars", default="', ’, ‘, `, ´, ʼ", help="Comma-separated list of apostrophe characters for complex form detection.")
    lemmatization_group.add_argument("--strip-garbage-characters", default=None, help="Characters to strip from the beginning and end of extracted source words (e.g., garbage hyphens).")

    
    token_mappings_group = parser.add_argument_group('Token Mappings Control')
    token_mappings_group.add_argument("--token-mappings-enabled", action="store_true", help="Enable token mappings overriding config.")
    token_mappings_group.add_argument("--disable-token-mappings", action="store_true", help="Disable token mappings overriding config.")
    token_mappings_group.add_argument("--lemmatize-mapped-tokens", action="store_true", dest="token_mappings_lemmatize_cli", help="Lemmatize mapped tokens overriding config.")

    
    de_group = parser.add_argument_group('German Language Specific Arguments')
    de_group.add_argument("--de-fix-genitive", action="store_true", help="[German] Corrects genitive noun lemmas (e.g., 'Hauses' -> 'Haus') by checking against the dictionary.")
    de_group.add_argument("--de-force-noun-capitalization", action="store_true", help="[German only] Force capitalization of all noun lemmas (NOUN, PROPN) as per German orthography rules. Overrides --force-proper-noun-capitalization for German.")

    gcs_group = parser.add_argument_group('German Compound Splitting (GCS)')
    gcs_group.add_argument("--de-gcs", action="store_true", help="Enable German Compound Splitting (GCS).")
    gcs_group.add_argument(
        "--de-gcs-pos-tags", 
        nargs='+', 
        default=['NOUN', 'PROPN', 'ADV', 'ADJ'],
        help='''Specify which Part-of-Speech tags to apply splitting to.

  Default: NOUN PROPN ADV ADJ

  This argument operates in two main modes:

  1. INCLUSION MODE (default behavior):
     List the specific tags you want to process.
     Example: --de-gcs-pos-tags NOUN PROPN ADJ

  2. EXCLUSION MODE:
     Prefix tags with '!' to process all tags except the ones specified.
     Example: --de-gcs-pos-tags !VERB !AUX
     (This splits everything except verbs and auxiliary verbs)

  PRECEDENCE RULE:
     If even one tag is prefixed with '!', the mode switches to exclusion.
     Any tags listed without '!' in the same command will be ignored.
     For instance, '--de-gcs-pos-tags NOUN !VERB' is treated as just '!VERB'.

  SPECIAL KEYWORD:
     ALL - A shortcut to process all available tags.

  Available Tags (Universal Dependencies):
    ADJ   - Adjective (Adjektiv; e.g., groß, alt, schön)
    ADP   - Adposition (Präposition; e.g., in, zu, auf, mit)
    ADV   - Adverb (Adverb; e.g., schnell, sehr, hier)
    AUX   - Auxiliary verb (Hilfsverb; e.g., sein, haben, werden, können)
    CCONJ - Coordinating Conjunction (Konjunktion; e.g., und, aber, oder)
    DET   - Determiner (Artikel/Demonstrativpronomen; e.g., der, eine, dieser)
    INTJ  - Interjection (Interjektion; e.g., ach, hallo, oje)
    NOUN  - Noun (Nomen/Substantiv; e.g., Haus, Tisch, Buch)
    NUM   - Numeral (Numerale; e.g., eins, zwei, 100)
    PART  - Particle (Partikel; e.g., nicht, zu bei Infinitiv, ja)
    PRON  - Pronoun (Pronomen; e.g., ich, du, er, sie)
    PROPN - Proper Noun (Eigenname; e.g., Peter, Berlin, Google)
    PUNCT - Punctuation (Interpunktion; e.g., ., ,, ?, !)
    SCONJ - Subordinating Conjunction (Subjunktion; e.g., dass, weil, wenn)
    SYM   - Symbol (Symbol; e.g., €, %%, §)
    VERB  - Verb (Verb; e.g., gehen, sagen, machen)
    X     - Other (Sonstiges; e.g., Fremdwörter, Tippfehler)'''
    )
    gcs_group.add_argument("--de-gcs-split-mode", choices=['only-nouns', 'any', 'combined'], default='only-nouns', help="[GCS] Set the splitting mode: 'only-nouns' (safe), 'any' (aggressive), or 'combined'.")
    gcs_group.add_argument("--de-gcs-mask-unknown-parts", action="store_true", help="[GCS] Mask word parts not found in the dictionary during splitting.")
    gcs_group.add_argument("--de-gcs-part-singularization", choices=['only-nouns', 'all', 'none'], default='only-nouns', help="[GCS] Controls singularization of compound parts.")
    gcs_group.add_argument("--de-gcs-preserve-compound-word", action="store_true", help="[GCS] Keep the original compound word in the lemma list along with its parts.")
    gcs_group.add_argument("--de-gcs-add-parts-to-wordlist", action="store_true", help="[GCS] Add split compound parts to the sentence wordlist. Requires --add-wordlist-col.")
    gcs_group.add_argument("--de-gcs-skip-merge-fractions", action="store_true", help="[GCS] Disable merging of components, outputting raw parts from dissection.")

    parser.add_argument("--json-ipc", action="store_true", dest="structured_output", help="Alias for --structured-output.")
    parser.add_argument("--structured-output", action="store_true", dest="structured_output", help="Emit JSON/JSONL output instead of plain text, enabling structured IPC communication.")
    
    args = parser.parse_args()
    
    if hasattr(args, 'text') and args.text:
        args.text = args.text.replace('\u200b', '').replace('\u200c', '').replace('\u200d', '').replace('\ufeff', '')
        
    # Initialize defaults
    args.frequency_case_sensitive = (args.language == 'de')
    args.classification_case_sensitive = True
    if not hasattr(args, 'token_mappings_enabled'):
        args.token_mappings_enabled = False
    args.token_mappings_case_sensitive = False
    args.token_mappings_normalize_apostrophes = True
    args.token_mappings_normalize_spaces = True
    args.token_mappings_enable_context_disambiguation = True
    args.token_mappings_lemmatize = getattr(args, 'token_mappings_lemmatize_cli', False)
    args.token_mappings_files = []

    # Load Classifications and Case Sensitivity from Config
    config_path_classify = Path(__file__).resolve().parent.parent.parent.parent / 'config.ini'
    if config_path_classify.exists() and not args.disable_classification:
        import configparser
        cfg = configparser.ConfigParser(allow_no_value=True)
        cfg.read(config_path_classify, encoding='utf-8')
        
        # Load case sensitivity settings
        if cfg.has_section('case_sensitivity'):
            freq_opt = f'frequency_{args.language}'
            class_opt = f'classification_{args.language}'
            if cfg.has_option('case_sensitivity', freq_opt):
                args.frequency_case_sensitive = cfg.getboolean('case_sensitivity', freq_opt)
            if cfg.has_option('case_sensitivity', class_opt):
                args.classification_case_sensitive = cfg.getboolean('case_sensitivity', class_opt)
                
        if cfg.has_section('classification') and cfg.getboolean('classification', 'enabled', fallback=False):
            if cfg.has_option('classification', f'dictionaries_{args.language}'):
                dicts = cfg.get('classification', f'dictionaries_{args.language}', fallback='')
            else:
                dicts = cfg.get('classification', 'dictionaries', fallback='')
            if dicts:
                if args.classify is None:
                    args.classify = []
                for d in dicts.split(','):
                    d = d.strip()
                    if not d: continue
                    if '=' in d:
                        name, prefix_path = d.split('=', 1)
                        prefix, rel_path = parse_prefix_and_path(prefix_path)
                        kw_ws = cfg.get('environment', 'kardenwort_workspace', fallback='./')
                        ws_path = (config_path_classify.parent / kw_ws).resolve()
                        full_path = ws_path / rel_path.strip()
                        classify_val = f"{prefix}:{full_path}" if prefix else str(full_path)
                        args.classify.append(f"{name.strip()}={classify_val}")
                        
        # Read combine_source_words and combine_source_words_order
        if not args.combine_source_words:
            if cfg.has_section('lemmatization') and cfg.has_option('lemmatization', 'combine_source_words'):
                args.combine_source_words = cfg.getboolean('lemmatization', 'combine_source_words')
            elif cfg.has_section('settings') and cfg.has_option('settings', 'combine_source_words'):
                args.combine_source_words = cfg.getboolean('settings', 'combine_source_words')

        if not getattr(args, 'preserve_composite_tokens', False):
            if cfg.has_section('lemmatization') and cfg.has_option('lemmatization', 'preserve_composite_tokens'):
                args.preserve_composite_tokens = cfg.getboolean('lemmatization', 'preserve_composite_tokens')
            elif cfg.has_section('settings') and cfg.has_option('settings', 'preserve_composite_tokens'):
                args.preserve_composite_tokens = cfg.getboolean('settings', 'preserve_composite_tokens')

        # Read simplemma correction options from config
        if not getattr(args, 'use_simplemma_correction', False):
            if cfg.has_section('settings') and cfg.has_option('settings', 'use_simplemma_correction'):
                args.use_simplemma_correction = cfg.getboolean('settings', 'use_simplemma_correction')
            elif cfg.has_section('lemmatization') and cfg.has_option('lemmatization', 'use_simplemma_correction'):
                args.use_simplemma_correction = cfg.getboolean('lemmatization', 'use_simplemma_correction')

        if not getattr(args, 'simplemma_after_spacy', False):
            if cfg.has_section('settings') and cfg.has_option('settings', 'simplemma_after_spacy'):
                args.simplemma_after_spacy = cfg.getboolean('settings', 'simplemma_after_spacy')
            elif cfg.has_section('lemmatization') and cfg.has_option('lemmatization', 'simplemma_after_spacy'):
                args.simplemma_after_spacy = cfg.getboolean('lemmatization', 'simplemma_after_spacy')

        if not getattr(args, 'simplemma_pos_aware', False):
            if cfg.has_section('settings') and cfg.has_option('settings', 'simplemma_pos_aware'):
                args.simplemma_pos_aware = cfg.getboolean('settings', 'simplemma_pos_aware')
            elif cfg.has_section('lemmatization') and cfg.has_option('lemmatization', 'simplemma_pos_aware'):
                args.simplemma_pos_aware = cfg.getboolean('lemmatization', 'simplemma_pos_aware')

        if not getattr(args, 'simplemma_smart_fallback', False):
            if cfg.has_section('settings') and cfg.has_option('settings', 'simplemma_smart_fallback'):
                args.simplemma_smart_fallback = cfg.getboolean('settings', 'simplemma_smart_fallback')
            elif cfg.has_section('lemmatization') and cfg.has_option('lemmatization', 'simplemma_smart_fallback'):
                args.simplemma_smart_fallback = cfg.getboolean('lemmatization', 'simplemma_smart_fallback')

        if not getattr(args, 'combine_source_words_order', None):
            if cfg.has_section('token_mappings') and cfg.has_option('token_mappings', 'combine_source_words_order'):
                args.combine_source_words_order = cfg.get('token_mappings', 'combine_source_words_order').strip().lower()
            elif cfg.has_section('lemmatization') and cfg.has_option('lemmatization', 'combine_source_words_order'):
                args.combine_source_words_order = cfg.get('lemmatization', 'combine_source_words_order').strip().lower()
            elif cfg.has_section('settings') and cfg.has_option('settings', 'combine_source_words_order'):
                args.combine_source_words_order = cfg.get('settings', 'combine_source_words_order').strip().lower()
            else:
                args.combine_source_words_order = 'contractions_first'

        if getattr(args, 'combine_source_words_prefer_lowercase', None) is None:
            if cfg.has_section('token_mappings') and cfg.has_option('token_mappings', 'combine_source_words_prefer_lowercase'):
                args.combine_source_words_prefer_lowercase = cfg.getboolean('token_mappings', 'combine_source_words_prefer_lowercase')
            elif cfg.has_section('lemmatization') and cfg.has_option('lemmatization', 'combine_source_words_prefer_lowercase'):
                args.combine_source_words_prefer_lowercase = cfg.getboolean('lemmatization', 'combine_source_words_prefer_lowercase')
            elif cfg.has_section('settings') and cfg.has_option('settings', 'combine_source_words_prefer_lowercase'):
                args.combine_source_words_prefer_lowercase = cfg.getboolean('settings', 'combine_source_words_prefer_lowercase')
            else:
                args.combine_source_words_prefer_lowercase = True

        if getattr(args, 'strip_garbage_characters', None) is None:
            if cfg.has_section('lemmatization') and cfg.has_option('lemmatization', 'strip_garbage_characters'):
                args.strip_garbage_characters = cfg.get('lemmatization', 'strip_garbage_characters').strip('"')
            elif cfg.has_section('settings') and cfg.has_option('settings', 'strip_garbage_characters'):
                args.strip_garbage_characters = cfg.get('settings', 'strip_garbage_characters').strip('"')
            else:
                args.strip_garbage_characters = ''
                
        if '--apostrophe-chars' not in sys.argv:
            if cfg.has_section('token_mappings') and cfg.has_option('token_mappings', 'apostrophe_chars'):
                args.apostrophe_chars = cfg.get('token_mappings', 'apostrophe_chars')
            elif cfg.has_section('lemmatization') and cfg.has_option('lemmatization', 'apostrophe_chars'):
                args.apostrophe_chars = cfg.get('lemmatization', 'apostrophe_chars')
            elif cfg.has_section('settings') and cfg.has_option('settings', 'apostrophe_chars'):
                args.apostrophe_chars = cfg.get('settings', 'apostrophe_chars')



        if getattr(args, 'disable_token_mappings', False):
            args.token_mappings_enabled = False
        else:
            if cfg.has_section('token_mappings') and cfg.getboolean('token_mappings', 'enabled', fallback=False):
                args.token_mappings_enabled = True

        if getattr(args, 'token_mappings_enabled', False):
            if cfg.has_section('token_mappings'):
                args.token_mappings_case_sensitive = cfg.getboolean('token_mappings', 'case_sensitive', fallback=False)
                args.token_mappings_normalize_apostrophes = cfg.getboolean('token_mappings', 'normalize_apostrophes', fallback=True)
                args.token_mappings_normalize_spaces = cfg.getboolean('token_mappings', 'normalize_spaces', fallback=True)
                args.token_mappings_enable_context_disambiguation = cfg.getboolean('token_mappings', 'enable_context_disambiguation', fallback=True)
                if not getattr(args, 'token_mappings_lemmatize_cli', False):
                    args.token_mappings_lemmatize = cfg.getboolean('token_mappings', 'lemmatize_mapped_tokens', fallback=False)
                
                mappings_files = cfg.get('token_mappings', args.language, fallback='')
                if mappings_files:
                    for mf in mappings_files.split(','):
                        mf = mf.strip()
                        if not mf: continue
                        kw_ws = cfg.get('environment', 'kardenwort_workspace', fallback='./')
                        ws_path = (config_path_classify.parent / kw_ws).resolve()
                        args.token_mappings_files.append(str(ws_path / mf))

    if args.type == "sort-frequency":
        lemma_index = load_lemma_frequency_index(args.lemma_index_file)
        input_words = []
        for line in sys.stdin:
            word = line.strip()
            if word:
                input_words.append(word)
        sorted_words = sorted(
            input_words,
            key=lambda w: get_lemma_sort_key(w, lemma_index, getattr(args, 'language', 'en'))
        )
        for w in sorted_words:
            print(w)
        sys.exit(0)
    
    source_timestamps = []
    if getattr(args, 'subtitle_timestamps_file', None):
        try:
            with open(args.subtitle_timestamps_file, 'r', encoding='utf-8') as f_time:
                source_timestamps = [line.strip() for line in f_time]
        except Exception as e:
            print(f"Warning: Could not read subtitle timestamps file {args.subtitle_timestamps_file}: {e}", file=sys.stderr)
    args.source_timestamps = source_timestamps
    
    if args.multi_text:
        if args.text1_file:
            print("Warning: --multi-text is ignored when --text1-file is provided.", file=sys.stderr)
        else:
            input_text_combined = ""
            if args.text:
                input_text_combined = args.text
            elif not sys.stdin.isatty():
                input_text_combined = sys.stdin.read()

            if input_text_combined:
                parts = re.split(r'\s*---\s*', input_text_combined.strip())
                text_blocks = parts[:3]
                file_arg_names = ['text1_file', 'text2_file', 'text3_file']

                for i, arg_name in enumerate(file_arg_names):
                    text_content = text_blocks[i] if i < len(text_blocks) else ""
                    
                    fd, path = tempfile.mkstemp(suffix='.txt', text=True)
                    with os.fdopen(fd, 'w', encoding='utf-8') as tmp:
                        tmp.write(text_content)
                    
                    setattr(args, arg_name, path)
                    TEMP_FILES_TO_CLEANUP.append(path)
                
                args.text = None
            else:
                print("Warning: --multi-text was specified but no input received from --text or stdin.", file=sys.stderr)

    ALL_POS_TAGS = {'ADJ', 'ADP', 'ADV', 'AUX', 'CCONJ', 'DET', 'INTJ', 'NOUN', 
                    'NUM', 'PART', 'PRON', 'PROPN', 'PUNCT', 'SCONJ', 'SYM', 'VERB', 'X'}

    raw_user_tags = args.de_gcs_pos_tags or []
    user_tags = [tag.strip() for item in raw_user_tags for tag in re.split(r'[\s,]+', str(item)) if tag.strip()]
    has_negation = any(tag.startswith('!') for tag in user_tags)
    gcs_target_pos_tags = set()

    if has_negation:
        excluded_tags = {tag[1:] for tag in user_tags if tag.startswith('!')}
        gcs_target_pos_tags = ALL_POS_TAGS - excluded_tags
    elif 'ALL' in user_tags:
        gcs_target_pos_tags = ALL_POS_TAGS
    else:
        gcs_target_pos_tags = set(user_tags)

    args.de_gcs_pos_tags = list(gcs_target_pos_tags)

    if args.de_gcs and args.language != 'de':
        print("Warning: GCS is designed for German language (--language de). The --de-gcs flag will be ignored.", file=sys.stderr)
        args.de_gcs = False
    if args.de_gcs_add_parts_to_wordlist and not args.de_gcs:
        print("Error: --de-gcs-add-parts-to-wordlist requires --de-gcs to be enabled.", file=sys.stderr); exit(1)
    if args.de_gcs_preserve_compound_word and not args.de_gcs:
        print("Error: --de-gcs-preserve-compound-word requires --de-gcs to be enabled.", file=sys.stderr); exit(1)

    global nlp
    nlp = spacy.load("de_core_news_lg" if args.language == "de" else "en_core_web_lg")

    lemma_override_rules = load_lemma_override_rules(args.lemma_override_file) if args.lemma_override_file else {}
    token_mappings = {}
    if getattr(args, 'token_mappings_enabled', False) and getattr(args, 'token_mappings_files', None):
        token_mappings = load_token_mappings(
            args.token_mappings_files,
            case_sensitive=getattr(args, 'token_mappings_case_sensitive', False),
            normalize_apostrophes=getattr(args, 'token_mappings_normalize_apostrophes', True),
            normalize_spaces=getattr(args, 'token_mappings_normalize_spaces', True)
        )

    gcs_automaton = None
    global de_dictionary
    de_dictionary = set()
    if args.language == 'de':
        de_dictionary = load_dictionary(args.de_dictionary_file)
        if not de_dictionary:
             print("Warning: German dictionary for validation is empty or not loaded.", file=sys.stderr)

        if args.de_gcs:
            if not GCS_AVAILABLE:
                print("Error: 'german-compound-splitter' library not installed. Please run 'pip install german-compound-splitter'.", file=sys.stderr); exit(1)
            if not os.path.exists(args.de_dictionary_file):
                print(f"Error: GCS dictionary file '{args.de_dictionary_file}' not found!", file=sys.stderr); exit(1)
            try:
                with redirect_stdout(io.StringIO()):
                    gcs_automaton = comp_split.read_dictionary_from_file(args.de_dictionary_file)
            except Exception as e:
                print(f"Error loading GCS dictionary: {e}", file=sys.stderr); exit(1)

    lemma_index = load_lemma_frequency_index(args.lemma_index_file)
    classifications = load_classification_dictionaries(
        getattr(args, 'classify', None),
        case_sensitive=getattr(args, 'classification_case_sensitive', True)
    )
    processed_output_file = None
    final_output_path = args.output_file

    source_text_for_filename = ""
    if args.text1_file:
        try:
            with open(args.text1_file, 'r', encoding='utf-8') as f:
                source_text_for_filename = f.read(1024)
        except Exception as e:
            print(f"Warning: Could not read {args.text1_file} for autonaming: {e}", file=sys.stderr)
    elif args.text:
         source_text_for_filename = args.text


    if args.output_file and (args.basename_add_timestamp or args.basename_add_first_words is not None):
        timestamp_id = datetime.now().strftime('%Y%m%d%H%M%S')
        output_directory, filename = os.path.dirname(args.output_file) or '.', os.path.basename(args.output_file)

        if args.basename_add_first_words is not None:
            filename_prefix = generate_filename_prefix_from_text(source_text_for_filename, args.basename_add_first_words)
            if filename_prefix:
                extension_dot_position = filename.find('.')
                file_extension = filename[extension_dot_position:] if extension_dot_position != -1 else ""
                new_filename = f"{timestamp_id}-{filename_prefix}{file_extension}"
            else:
                 new_filename = f"{timestamp_id}-{filename}"
            final_output_path = os.path.join(output_directory, new_filename)
        elif args.basename_add_timestamp:
            new_filename = f"{timestamp_id}-{filename}"
            final_output_path = os.path.join(output_directory, new_filename)
    
    # --- Parse Anki Field Mapping and Header ---
    field_mapping = {}
    anki_header = []

    if args.anki_csv_header:
        try:
            anki_header = json.loads(args.anki_csv_header)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON for --anki-csv-header: {e}", file=sys.stderr)
            sys.exit(1)
    elif final_output_path:
        print("Error: --anki-csv-header is required when writing to an output file. The core engine no longer uses hardcoded defaults for unambiguousness.", file=sys.stderr)
        sys.exit(1)

    if args.anki_field_mapping:
        try:
            field_mapping = json.loads(args.anki_field_mapping)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON for --anki-field-mapping: {e}", file=sys.stderr)
            sys.exit(1)
    elif final_output_path:
        print("Error: --anki-field-mapping is required when writing to an output file. The core engine no longer uses hardcoded defaults for unambiguousness.", file=sys.stderr)
        sys.exit(1)
    # -------------------------------------------
    
    # --- Derive legacy flags from mapping ---
    data_sources_needed = set(field_mapping.values())
    add_wordlist_col = "wordlist" in data_sources_needed
    add_sentence_index_col = "sentence_index" in data_sources_needed
    add_source_word_col = "source_word" in data_sources_needed
    # ----------------------------------------

    mode = None
    input_text = ""
    target_text_content = None
    tertiary_text_content = None

    if args.lemmas_per_line:
        if not args.text1_file:
            print("Error: --text1-file is required for --lemmas-per-line mode.", file=sys.stderr); exit(1)
        if not final_output_path:
            print("Error: --output-file is required for --lemmas-per-line mode.", file=sys.stderr); exit(1)
        mode = OperationalMode.LEMMAS_PER_LINE
        if os.path.exists(args.text1_file):
            input_text = read_text_from_file(args.text1_file)
    elif args.type == "word":
        if args.text1_file:
            input_text = read_text_from_file(args.text1_file)
        elif args.text:
            input_text = args.text
        elif 'KARDENWORT_INPUT_TEXT' in os.environ:
            input_text = os.environ['KARDENWORT_INPUT_TEXT']
        elif not sys.stdin.isatty():
            input_text = sys.stdin.read()

        if not input_text and not args.text2_file:
            print("Error: No input provided. Use --text, --text1-file, environment variable, or pipe data via stdin.", file=sys.stderr); exit(1)

        if args.text2_file:
            if not input_text and args.text1_file:
                input_text = read_text_from_file(args.text1_file)
            if os.path.exists(args.text2_file):
                with open(args.text2_file, "r", encoding="utf-8") as f2:
                    target_text_content = f2.read()
            if args.text3_file and os.path.exists(args.text3_file):
                with open(args.text3_file, "r", encoding="utf-8") as f3:
                    tertiary_text_content = f3.read()
            mode = OperationalMode.PARALLEL_TEXTS
        else:
            if not input_text:
                print("Error: No input provided for single text processing.", file=sys.stderr); exit(1)
            mode = OperationalMode.SINGLE_TEXT
    elif args.type == "sentence":
        if any([args.de_gcs, args.de_gcs_mask_unknown_parts]):
            print("Warning: GCS-related flags are only applicable for --type word and will be ignored.", file=sys.stderr)
        if not args.text1_file or not args.text2_file:
            print("Error: --text1-file and --text2-file must be specified for sentence mode.", file=sys.stderr); exit(1)
        try:
            input_text = read_text_from_file(args.text1_file)
            if args.text2_file and os.path.exists(args.text2_file):
                with open(args.text2_file, "r", encoding="utf-8") as f2:
                    target_text_content = f2.read()
            if args.text3_file and os.path.exists(args.text3_file):
                with open(args.text3_file, "r", encoding="utf-8") as f3:
                    tertiary_text_content = f3.read()
        except IOError as e:
            print(f"Error reading files: {e}", file=sys.stderr); sys.exit(1)
        mode = OperationalMode.PARALLEL_SENTENCES
    else:
        raise ValueError(f"Cannot resolve operational mode for execution type '{args.type}'")

    processing_options = {
        'token_mappings': token_mappings,
        'de_gcs_only_nouns': (getattr(args, 'de_gcs_split_mode', 'only-nouns') == 'only-nouns'),
        'de_gcs_combine_noun_modes': (getattr(args, 'de_gcs_split_mode', 'only-nouns') == 'combined'),
        'de_fix_genitive': getattr(args, 'de_fix_genitive', False),
        'de_gcs_mask_unknown_parts': getattr(args, 'de_gcs_mask_unknown_parts', False),
        'de_gcs_preserve_compound_word': getattr(args, 'de_gcs_preserve_compound_word', False),
        'preserve_composite_tokens': getattr(args, 'preserve_composite_tokens', False),
        'de_gcs_skip_merge_fractions': getattr(args, 'de_gcs_skip_merge_fractions', False),
        'classification_case_sensitive': getattr(args, 'classification_case_sensitive', True),
        'classifications': classifications,
        'lemma_override_rules': lemma_override_rules,
        'gcs_automaton': gcs_automaton,
        'de_dictionary': de_dictionary,
        'source_text': input_text,
        'source_text_content': input_text,
        'target_text_content': target_text_content,
        'tertiary_text_content': tertiary_text_content,
        'lemma_sort_index': lemma_index,
        'add_wordlist_col': add_wordlist_col,
        'add_sentence_index_col': add_sentence_index_col,
        'add_source_word_col': add_source_word_col,
        'field_mapping': field_mapping,
        'anki_header': anki_header,
        'output_file_path': final_output_path,
        'target_text_path': getattr(args, 'text2_file', None),
        'tertiary_text_path': getattr(args, 'text3_file', None)
    }

    cfg_dict = vars(args).copy() if hasattr(args, '__dict__') else {}
    cfg_dict.update(processing_options)
    config = ExtractionConfig.from_args(SimpleNamespace(**cfg_dict))

    exec_ctx = ExecutionContext(
        nlp_model=nlp,
        simplemma_lang=getattr(args, 'language', 'de'),
        gcs_automaton=gcs_automaton,
        de_dictionary=de_dictionary
    )

    dispatcher = ModeDispatcher()
    records_generator = dispatcher.dispatch(mode, config, exec_ctx)

    processed_output_file = None
    if not final_output_path and mode == OperationalMode.SINGLE_TEXT and not getattr(args, 'structured_output', False):
        formatter = OutputFormatter.get_formatter(getattr(args, 'stdout_format', None))
        formatter.format(records_generator, sys.stdout)
    else:
        writer = TSVWriter(
            output_file_path=final_output_path,
            header=anki_header,
            add_header=getattr(args, 'add_header', True) and bool(anki_header) and mode != OperationalMode.LEMMAS_PER_LINE,
            delimiter="\t",
            args=args,
            source_text_content=input_text,
            target_text_path=getattr(args, 'text2_file', None),
            tertiary_text_path=getattr(args, 'text3_file', None),
            target_text_content=target_text_content,
            tertiary_text_content=tertiary_text_content,
            stdout_print_output_basename=getattr(args, 'stdout_print_output_basename', False)
        )
        processed_output_file = writer.write(records_generator)

    if args.stdout_print_output_basename and processed_output_file:
        print(os.path.basename(processed_output_file), file=sys.stdout)

if __name__ == "__main__":
    is_structured = "--structured-output" in sys.argv or "--json-ipc" in sys.argv
    if is_structured:
        from kardenwort.core.errors import setup_structured_logging, StructuredError, ErrorCode
        setup_structured_logging()
        try:
            main()
        except SystemExit as e:
            if e.code != 0:
                msg = str(e.code) if e.code else "Unknown exit code"
                err = StructuredError(ErrorCode.ERR_UNHANDLED_EXCEPTION, f"Process exited with {msg}")
                err.exit()
            else:
                sys.exit(0)
        except Exception as e:
            err = StructuredError(ErrorCode.ERR_UNHANDLED_EXCEPTION, str(e))
            err.exit()
    else:
        main()