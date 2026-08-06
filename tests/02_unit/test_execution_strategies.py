import sys
import os
import inspect
import json
import io
from pathlib import Path
from types import SimpleNamespace
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / 'src'))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'helpers'))

from mock_nlp import MockPipelineNLP, MockToken, MockDoc
import kardenwort.core.kardenwort as kw
from kardenwort.core.kardenwort import (
    ParallelTextsStrategy,
    SingleTextStrategy,
    ParallelSentencesStrategy,
    LemmasPerLineStrategy,
    OperationalStrategy,
    OperationalMode,
    ModeDispatcher,
    TSVWriter,
    TabularRecord,
    ExtractionConfig,
    ExecutionContext,
    OutputFormatter,
)

mock_nlp = MockPipelineNLP("de")


def create_base_args():
    return SimpleNamespace(
        deduplication_scope="global",
        combine_source_words=False,
        combine_source_words_order="contractions_first",
        combine_source_words_prefer_lowercase=True,
        prefer_shortest_form=False,
        strip_headers=["all"],
        language="de",
        sentence_context_size=1,
        add_source_word_col=True,
        add_wordlist_col=False,
        add_sentence_index_col=False,
        add_header=True,
        wordlist_use_br=False,
        stdout_print_output_basename=False,
        de_gcs=False,
        de_gcs_add_parts_to_wordlist=False,
        de_gcs_pos_tags=[],
        de_force_noun_capitalization=True,
        force_proper_noun_capitalization=True,
        de_fix_genitive=False,
        de_gcs_mask_unknown_parts=False,
        de_gcs_preserve_compound_word=False,
        de_gcs_skip_merge_fractions=False,
        de_gcs_only_nouns=True,
        de_gcs_combine_noun_modes=False,
        strip_garbage_characters="",
        anki_markdown_decks=False,
        anki_create_subdecks=False,
        anki_deck_content=["parent-source"],
        anki_sentence_subdecks=False,
        anki_parent_deck=None,
        anki_context_use_br=False,
        field_mapping={},
        anki_header=["lemma", "source_word", "sentence_index", "cloze"],
        header=["lemma", "source_word", "sentence_index", "cloze"],
        type="word",
        lemmas_per_line=False,
        token_mappings={},
        classifications={},
        classification_case_sensitive=False
    )


def test_zero_file_io_in_strategies():
    """Task 3.1: Verify zero file I/O operations remain inside the four Strategy execute() methods."""
    strategies = [
        ParallelTextsStrategy,
        SingleTextStrategy,
        ParallelSentencesStrategy,
        LemmasPerLineStrategy
    ]
    forbidden_tokens = ['open(', 'with open', '.write(', 'os.path']
    for strategy in strategies:
        source = inspect.getsource(strategy.execute)
        for token in forbidden_tokens:
            assert token not in source, f"Forbidden I/O token '{token}' found in {strategy.__name__}.execute()"


def test_single_text_strategy_equivalence(tmp_path, monkeypatch):
    """Task 3.3: Compare SingleTextStrategy output against legacy process_single_text."""
    monkeypatch.setattr(kw, 'nlp', mock_nlp)
    source_text = "Der Hund läuft in den Garten.\nDie Katze schläft auf dem Sofa."
    out_file_legacy = tmp_path / "legacy_single.tsv"
    out_file_strat = tmp_path / "strat_single.tsv"

    args_ns = create_base_args()

    kw.process_single_text(
        source_text, {}, "de", 1,
        str(out_file_legacy), True, False, False,
        True, False, False,
        False, None, False, None, {},
        [], {}, ["lemma", "source_word", "sentence_index", "cloze"], args_ns
    )

    config_dict = vars(args_ns).copy()
    config_dict.update({
        'source_text': source_text,
        'source_text_content': source_text,
        'output_file_path': str(out_file_strat),
    })
    config = ExtractionConfig.from_args(SimpleNamespace(**config_dict))
    ctx = ExecutionContext(nlp_model=mock_nlp, simplemma_lang="de")
    strategy = SingleTextStrategy()
    records = list(strategy.execute(config, ctx))

    writer = TSVWriter(
        output_file_path=str(out_file_strat),
        header=["lemma", "source_word", "sentence_index", "cloze"],
        add_header=True,
        delimiter="\t",
        args=args_ns,
        source_text_content=source_text
    )
    writer.write(records)

    assert out_file_legacy.exists() and out_file_strat.exists()
    assert out_file_legacy.read_text(encoding="utf-8") == out_file_strat.read_text(encoding="utf-8")


def test_lemmas_per_line_strategy_equivalence(tmp_path, monkeypatch):
    """Task 3.3: Compare LemmasPerLineStrategy against legacy process_lemmas_per_line."""
    monkeypatch.setattr(kw, 'nlp', mock_nlp)
    in_file = tmp_path / "input.txt"
    in_file.write_text("Der schnelle Hund.\nDie Katze.", encoding="utf-8")
    
    out_file_legacy = tmp_path / "legacy_lpl.txt"
    out_file_strat = tmp_path / "strat_lpl.txt"
    
    args_ns = create_base_args()
    args_ns.lemmas_per_line = True
    kw.process_lemmas_per_line(str(in_file), str(out_file_legacy), {}, None, {}, args_ns)

    source_content = in_file.read_text(encoding="utf-8")
    config_dict = vars(args_ns).copy()
    config_dict.update({'source_text_content': source_content})
    config = ExtractionConfig.from_args(SimpleNamespace(**config_dict))
    ctx = ExecutionContext(nlp_model=mock_nlp, simplemma_lang="de")
    strategy = LemmasPerLineStrategy()
    records = list(strategy.execute(config, ctx))

    writer = TSVWriter(output_file_path=str(out_file_strat), args=args_ns, source_text_content=source_content)
    writer.write(records)

    assert out_file_legacy.read_text(encoding="utf-8") == out_file_strat.read_text(encoding="utf-8")


def test_tsv_writer_metadata_generation(tmp_path):
    """Task 3.4: Verify that _write_deck_metadata is triggered correctly by TSVWriter."""
    source_text = "Der Test."
    out_file = tmp_path / "test_deck.tsv"
    meta_file = tmp_path / "test_deck.json"

    args_ns = create_base_args()
    writer = TSVWriter(
        output_file_path=str(out_file),
        header=["lemma", "source_word"],
        add_header=True,
        args=args_ns,
        source_text_content=source_text
    )
    writer.write([TabularRecord(fields=["Hund", "Hunden"])])

    assert out_file.exists()
    assert meta_file.exists()
    meta_content = json.loads(meta_file.read_text(encoding="utf-8"))
    assert isinstance(meta_content, dict)


def test_output_formatters():
    """Task 2.4 / 3.3: Test polymorphic OutputFormatter hierarchy."""
    records = [
        TabularRecord(row_data={'lemma': 'Hund', 'source_word': 'Hunden', 'source_sentence': 'Hier sind Hunden.'})
    ]
    
    tsv_out = io.StringIO()
    OutputFormatter.get_formatter('tsv').format(records, tsv_out)
    assert "Hund\tHunden" in tsv_out.getvalue()
    
    html_out = io.StringIO()
    OutputFormatter.get_formatter('html').format(records, html_out)
    assert "<table>" in html_out.getvalue() and "<tr><td>Hund</td><td>Hunden</td></tr>" in html_out.getvalue()
    
    json_out = io.StringIO()
    OutputFormatter.get_formatter('json').format(records, json_out)
    data = json.loads(json_out.getvalue())
    assert len(data) == 1 and data[0]['lemma'] == 'Hund'


def test_mode_dispatcher_and_cancellation():
    """Verify ModeDispatcher routing and ExecutionContext cancellation."""
    dispatcher = ModeDispatcher()
    strat = dispatcher.get_strategy(OperationalMode.SINGLE_TEXT)
    assert isinstance(strat, SingleTextStrategy)

    with pytest.raises(ValueError):
        dispatcher.get_strategy("INVALID_MODE")

    ctx = ExecutionContext(simplemma_lang="de")
    ctx.cancel()
    assert ctx.is_cancelled() is True
