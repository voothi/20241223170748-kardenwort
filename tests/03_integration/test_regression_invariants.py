import sys
import os
import csv
import json
import io
from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / 'src'))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / '02_unit'))

import kardenwort.core.kardenwort as kw
from kardenwort.core.kardenwort import process_parallel_text_files, get_anki_csv_header
from test_core_invariants import generate_gcs_matrix


class MockMorph:
    def __init__(self, data=None):
        self._data = data or {}
    def get(self, key, default=None):
        return self._data.get(key, default or [])


class MockToken:
    def __init__(self, text, i=0, pos="NOUN", tag="NN", dep="ROOT", head_i=0, is_sent_start=False, like_url=False, like_email=False, case_morph=None):
        self.text = text
        self.lemma_ = text.lower().strip(".,!?")
        if not self.lemma_:
            self.lemma_ = text.lower()
        self.pos_ = pos
        self.tag_ = tag
        self.i = i
        self.dep_ = dep
        self._head_i = head_i
        self.head = self
        self.is_sent_start = is_sent_start
        self.like_url = like_url
        self.like_email = like_email
        self.morph = MockMorph({"Case": case_morph or []})
        self.is_alpha = any(c.isalpha() for c in text)
        
    def __str__(self):
        return self.text


class MockDoc(list):
    def __init__(self, tokens, text):
        super().__init__(tokens)
        self.text = text
        for token in self:
            if 0 <= token._head_i < len(self):
                token.head = self[token._head_i]
                
    @property
    def sents(self):
        class _Span:
            def __init__(self, t): self.text = t
        return [_Span(self.text)]


class MockPipelineNLP:
    def __init__(self, lang='de'):
        self.lang = lang
        
    def __call__(self, text):
        raw_words = text.split()
        tokens = []
        for idx, w in enumerate(raw_words):
            is_start = (idx == 0)
            tokens.append(MockToken(w, i=idx, is_sent_start=is_start))
        return MockDoc(tokens, text)


@pytest.fixture
def mock_nlp(monkeypatch):
    nlp_instance = MockPipelineNLP('de')
    monkeypatch.setattr(kw, 'nlp', nlp_instance, raising=False)
    return nlp_instance


@pytest.fixture
def default_args(tmp_path):
    import argparse
    src_path = tmp_path / "src.txt"
    src_path.write_text("Haus Haus Auto.\nAuto Haus Hund.", encoding="utf-8")
    
    return argparse.Namespace(
        deduplication_scope='global',
        language='de',
        combine_source_words=False,
        combine_source_words_order='contractions_first',
        combine_source_words_prefer_lowercase=True,
        prefer_shortest_form=False,
        strip_headers=None,
        add_header=True,
        wordlist_use_br=False,
        stdout_print_output_basename=False,
        de_gcs=False,
        de_gcs_add_parts_to_wordlist=False,
        de_gcs_pos_tags=['NN', 'NOUN', 'N'],
        de_fix_genitive=False,
        de_gcs_mask_unknown_parts=False,
        de_gcs_preserve_compound_word=False,
        de_gcs_skip_merge_fractions=False,
        de_gcs_only_nouns=True,
        de_gcs_combine_noun_modes=False,
        de_gcs_part_singularization='only-nouns',
        anki_markdown_decks=False,
        anki_create_subdecks=False,
        anki_parent_deck=None,
        anki_deck_content=False,
        anki_sentence_subdecks=False,
        anki_context_use_br=False,
        source_timestamps=[],
        token_mappings_enabled=False,
        token_mappings_lemmatize=False,
        use_simplemma_correction=False,
        simplemma_smart_fallback=False,
        simplemma_after_spacy=False,
        de_force_noun_capitalization=True,
        force_proper_noun_capitalization=True,
        apostrophe_chars="', ’, ‘, `, ´, ʼ",
        type='word',
        text1_file=str(src_path),
        text2_file=None,
        text3_file=None,
        classification_case_sensitive=False,
        tts_destination_lang=None,
        tts_tertiary_lang=None,
    )


def run_pipeline_parallel(args, tmp_path, output_filename="out.tsv", source_text=None, target_text_path=None, tertiary_text_path=None, field_mapping=None, **override_kwargs):
    if source_text is None:
        with open(args.text1_file, "r", encoding="utf-8") as f:
            source_text = f.read()
            
    out_path = str(tmp_path / output_filename) if output_filename else None
    header = get_anki_csv_header()
    
    if field_mapping is None:
        field_mapping = {
            "WordSource": "lemma",
            "Quotation": "source_word",
            "SentenceSource": "source_sentence",
            "SentenceSourceWordlist": "wordlist",
            "Deck": "deck_name",
            "Note": "subtitle_start_time",
            "SentenceSourceContextLeft": "source_context_left",
            "SentenceSourceContextRight": "source_context_right",
            "SentenceDestination": "target_sentence",
            "SentenceDestination2": "tertiary_sentence",
            "SentenceSourceIndex": "sentence_index",
        }
        
    override_rules = override_kwargs.pop('lemma_override_rules', {
        'priority1': {}, 'priority1_regex': [], 'priority2': {}, 'priority2_regex': [], 'priority3': {}
    })
    de_dict = override_kwargs.pop('de_dictionary', {"Bundes", "Land", "Verwaltung", "Haus", "Auto", "Hund", "Satz", "Title", "Eins", "Zwei", "Drei", "Vier", "Groß"})

    kwargs = {
        'de_gcs_only_nouns': getattr(args, 'de_gcs_only_nouns', True),
        'de_gcs_combine_noun_modes': getattr(args, 'de_gcs_combine_noun_modes', False),
        'de_fix_genitive': getattr(args, 'de_fix_genitive', False),
        'de_gcs_mask_unknown_parts': getattr(args, 'de_gcs_mask_unknown_parts', False),
        'de_gcs_preserve_compound_word': getattr(args, 'de_gcs_preserve_compound_word', False),
        'de_gcs_skip_merge_fractions': getattr(args, 'de_gcs_skip_merge_fractions', False),
        'classifications': getattr(args, 'classifications', {}),
        'token_mappings': {},
    }
    kwargs.update(override_kwargs)

    process_parallel_text_files(
        source_text=source_text,
        lemma_sort_index={},
        language=getattr(args, 'language', 'de'),
        target_text_path=target_text_path,
        tertiary_text_path=tertiary_text_path,
        sentence_context_size=getattr(args, 'sentence_context_size', 1),
        output_file_path=out_path,
        add_source_word_col=True,
        add_wordlist_col=getattr(args, 'add_wordlist_col', True),
        add_sentence_index_col=True,
        add_header=getattr(args, 'add_header', True),
        wordlist_use_br=getattr(args, 'wordlist_use_br', False),
        stdout_print_output_basename=getattr(args, 'stdout_print_output_basename', False),
        de_gcs=getattr(args, 'de_gcs', False),
        gcs_automaton=getattr(args, 'gcs_automaton', None),
        de_gcs_add_parts_to_wordlist=getattr(args, 'de_gcs_add_parts_to_wordlist', False),
        de_dictionary=de_dict,
        lemma_override_rules=override_rules,
        de_gcs_pos_tags=getattr(args, 'de_gcs_pos_tags', ['NN', 'NOUN', 'N']),
        field_mapping=field_mapping,
        anki_header=header,
        args=args,
        **kwargs
    )
    return out_path


def read_tsv_records(file_path):
    records = []
    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        header = next(reader, None)
        if header is None:
            return []
        for row in reader:
            if any(row):
                records.append(dict(zip(header, row)))
    return records


# ==============================================================================
# Phase 4: process_parallel_text_files Regression Baselines
# ==============================================================================

def test_deduplication_scope_modes(mock_nlp, default_args, tmp_path):
    """
    4.1 Test deduplication_scope='global', 'sentence', and 'none'.
    Verifies record count, ordering, and data structure correctness for each mode.
    """
    # 1. Global scope
    default_args.deduplication_scope = 'global'
    out_global = run_pipeline_parallel(default_args, tmp_path, "out_global.tsv")
    rec_global = read_tsv_records(out_global)
    assert len(rec_global) == 3
    lemmas_global = sorted([r["WordSource"] for r in rec_global])
    assert lemmas_global == ["Auto", "Haus", "Hund"]
    
    # 2. Sentence scope
    default_args.deduplication_scope = 'sentence'
    out_sent = run_pipeline_parallel(default_args, tmp_path, "out_sentence.tsv")
    rec_sent = read_tsv_records(out_sent)
    assert len(rec_sent) == 5
    
    # 3. None scope
    default_args.deduplication_scope = 'none'
    out_none = run_pipeline_parallel(default_args, tmp_path, "out_none.tsv")
    rec_none = read_tsv_records(out_none)
    assert len(rec_none) == 6


def test_combine_source_words_and_prefer_shortest(mock_nlp, default_args, tmp_path):
    """
    4.2 Test combine_source_words=True multi-form aggregation via sort_inflected_forms
    and prefer_shortest_form=True replacement.
    """
    text = "Gelaufen ist er.\nLief sie.\n"
    override_rules = {
        'priority1': {}, 'priority1_regex': [],
        'priority2': {
            'Gelaufen': [('Laufen', None)],
            'Lief': [('Laufen', None)],
            'ist': [('sein', None)],
            'er.': [('er', None)],
            'sie.': [('sie', None)],
        },
        'priority2_regex': [], 'priority3': {}
    }
    
    # 1. combine_source_words = True
    default_args.deduplication_scope = 'global'
    default_args.combine_source_words = True
    out_comb = run_pipeline_parallel(default_args, tmp_path, "out_comb.tsv", source_text=text, lemma_override_rules=override_rules)
    recs_comb = read_tsv_records(out_comb)
    laufen_rec = next(r for r in recs_comb if r["WordSource"] == "Laufen")
    assert "Gelaufen" in laufen_rec["Quotation"] and "Lief" in laufen_rec["Quotation"]
    
    # 2. prefer_shortest_form = True
    default_args.combine_source_words = False
    default_args.prefer_shortest_form = True
    out_short = run_pipeline_parallel(default_args, tmp_path, "out_short.tsv", source_text=text, lemma_override_rules=override_rules)
    recs_short = read_tsv_records(out_short)
    laufen_short = next(r for r in recs_short if r["WordSource"] == "Laufen")
    assert laufen_short["Quotation"] == "Lief"


def test_strip_headers_and_translations_alignment(mock_nlp, default_args, tmp_path):
    """
    4.3 Test strip_headers on/off and optional target_text_path / tertiary_text_path presence.
    """
    src = "# Title\nSentence one.\nSentence two."
    tgt = "# Titel\nSatz eins.\nSatz zwei."
    tert = "# Заголовок\nПредложение один.\nПредложение два."
    
    f_tgt = tmp_path / "target.txt"
    f_tgt.write_text(tgt, encoding="utf-8")
    f_tert = tmp_path / "tertiary.txt"
    f_tert.write_text(tert, encoding="utf-8")
    
    default_args.strip_headers = ['all']
    default_args.deduplication_scope = 'sentence'
    out = run_pipeline_parallel(default_args, tmp_path, "out_align.tsv", source_text=src, target_text_path=str(f_tgt), tertiary_text_path=str(f_tert))
    recs = read_tsv_records(out)
    
    title_rec = next(r for r in recs if r["SentenceSource"] == "Title")
    assert title_rec["SentenceDestination"] == "Titel"
    assert title_rec["SentenceDestination2"] == "Заголовок"
    
    sent2_rec = next(r for r in recs if r["SentenceSource"] == "Sentence two.")
    assert "Sentence one." in sent2_rec["SentenceSourceContextLeft"]


@pytest.mark.parametrize("gcs_config", generate_gcs_matrix())
def test_de_gcs_kwargs_combinations(mock_nlp, default_args, tmp_path, gcs_config):
    """
    4.4 Test de_gcs_* kwargs flag combinations across all 32 matrix permutations.
    """
    for k, v in gcs_config.items():
        setattr(default_args, k, v)
    default_args.de_gcs = True
    default_args.gcs_automaton = MagicMock()
    
    src = "Bundeslandverwaltung ist groß."
    
    with patch("kardenwort.core.kardenwort.comp_split", create=True) as mock_split:
        mock_split.dissect.return_value = ["Bundes", "land", "verwaltung"]
        mock_split.merge_fractions.return_value = ["Bundes", "land", "verwaltung"]
        
        out = run_pipeline_parallel(default_args, tmp_path, f"out_gcs_{id(gcs_config)}.tsv", source_text=src)
        recs = read_tsv_records(out)
        lemmas = [r["WordSource"].lower() for r in recs]
        
        assert "land" in lemmas or "verwaltung" in lemmas
        if gcs_config["de_gcs_preserve_compound_word"]:
            assert any("bundeslandverwaltung" in l for l in lemmas)


def test_add_wordlist_col_br_vs_newline(mock_nlp, default_args, tmp_path):
    """
    4.5 Test add_wordlist_col=True with wordlist_use_br=True vs False.
    """
    default_args.add_wordlist_col = True
    src = "Haus Auto Hund."
    
    # 1. wordlist_use_br = True
    default_args.wordlist_use_br = True
    out_br = run_pipeline_parallel(default_args, tmp_path, "out_wl_br.tsv", source_text=src)
    recs_br = read_tsv_records(out_br)
    assert "<br>" in recs_br[0]["SentenceSourceWordlist"]
    
    # 2. wordlist_use_br = False
    default_args.wordlist_use_br = False
    out_nl = run_pipeline_parallel(default_args, tmp_path, "out_wl_nl.tsv", source_text=src)
    recs_nl = read_tsv_records(out_nl)
    assert "\n" in recs_nl[0]["SentenceSourceWordlist"]


def test_anki_markdown_decks_and_subdeck_stack(mock_nlp, default_args, tmp_path):
    """
    4.6 Test anki_markdown_decks + anki_create_subdecks + anki_parent_deck subdeck stack routing
    and anki_sentence_subdecks per-sentence deck name suffix generation.
    """
    src = "# Chapter One\n## Section One\nDas ist ein Satz."
    default_args.anki_markdown_decks = True
    default_args.anki_create_subdecks = True
    default_args.anki_parent_deck = "GermanVault"
    default_args.anki_sentence_subdecks = True
    default_args.deduplication_scope = 'sentence'
    
    out = run_pipeline_parallel(default_args, tmp_path, "out_decks.tsv", source_text=src)
    recs = read_tsv_records(out)
    
    satz_recs = [r for r in recs if r["SentenceSource"] == "Das ist ein Satz."]
    assert len(satz_recs) > 0
    deck = satz_recs[0]["Deck"]
    assert "GermanVault" in deck
    assert "chapter" in deck.lower() and "section" in deck.lower()
    assert "das-ist" in deck.lower()


def test_anki_deck_content_accumulation(mock_nlp, default_args, tmp_path):
    """
    4.7 Test anki_deck_content=True subdeck content map accumulation.
    """
    src = "# Deck A\nSatz eins in A.\n# Deck B\nSatz eins in B."
    tgt = "# Deck A\nTrans one in A.\n# Deck B\nTrans one in B."
    f_tgt = tmp_path / "tgt.txt"
    f_tgt.write_text(tgt, encoding="utf-8")
    
    default_args.anki_markdown_decks = True
    default_args.anki_create_subdecks = True
    default_args.anki_parent_deck = "Parent"
    default_args.anki_deck_content = ['parent-source', 'subdeck-source', 'subdeck-translations']
    
    out = run_pipeline_parallel(default_args, tmp_path, "out_meta.tsv", source_text=src, target_text_path=str(f_tgt))
    
    meta_path = str(tmp_path / "out_meta.json")
    assert os.path.exists(meta_path)
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
        
    descriptions = meta.get("deck_descriptions", {})
    assert len(descriptions) >= 2
    assert any("Satz eins in A." in val for val in descriptions.values())
    assert any("Trans one in A." in val for val in descriptions.values())


def test_source_timestamps_and_context_join_str(mock_nlp, default_args, tmp_path):
    """
    4.8 Test source_timestamps subtitle time field population and anki_context_use_br join format.
    """
    src = "Eins.\nZwei.\nDrei."
    default_args.source_timestamps = ["00:00:01.000", "00:00:05.000", "00:00:10.000"]
    default_args.deduplication_scope = 'sentence'
    
    # 1. anki_context_use_br = True
    default_args.anki_context_use_br = True
    out = run_pipeline_parallel(default_args, tmp_path, "out_time_br.tsv", source_text=src)
    recs = read_tsv_records(out)
    
    sent2_rec = next(r for r in recs if r["SentenceSource"] == "Zwei.")
    assert sent2_rec["Note"] == "00:00:05.000"
    assert sent2_rec["SentenceSourceContextLeft"] == "Eins."
    assert sent2_rec["SentenceSourceContextRight"] == "Drei."
    
    # Test multiple context sentences joined by <br> vs space
    sent_multi = "Eins.\nZwei.\nDrei.\nVier."
    default_args.source_timestamps = ["t1", "t2", "t3", "t4"]
    default_args.sentence_context_size = 2
    
    out2 = run_pipeline_parallel(default_args, tmp_path, "out_multi_br.tsv", source_text=sent_multi)
    recs2 = read_tsv_records(out2)
    sent3_rec = next(r for r in recs2 if r["SentenceSource"] == "Drei.")
    assert "Eins.<br>Zwei." == sent3_rec["SentenceSourceContextLeft"]
    
    # 2. anki_context_use_br = False (space join)
    default_args.anki_context_use_br = False
    out3 = run_pipeline_parallel(default_args, tmp_path, "out_multi_sp.tsv", source_text=sent_multi)
    recs3 = read_tsv_records(out3)
    sent3_sp = next(r for r in recs3 if r["SentenceSource"] == "Drei.")
    assert "Eins. Zwei." == sent3_sp["SentenceSourceContextLeft"]
