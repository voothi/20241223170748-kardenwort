"""Unified NLP mocking primitives for Kardenwort testing suites."""

from typing import List, Dict, Any, Optional

class MockMorph:
    """Simulates spaCy token morphological feature dictionary."""
    def __init__(self, data: Optional[Dict[str, Any]] = None):
        self._data = data or {}

    def get(self, key: str, default: Optional[List[str]] = None) -> List[str]:
        return self._data.get(key, default or [])


class MockToken:
    """Unified mock representation of spaCy's Token object across tests."""
    def __init__(
        self,
        text: str,
        lemma_: Optional[str] = None,
        pos_: str = "NOUN",
        tag_: str = "NN",
        dep_: str = "ROOT",
        i: int = 0,
        head_i: int = 0,
        is_sent_start: bool = False,
        is_alpha: Optional[bool] = None,
        like_url: bool = False,
        like_email: bool = False,
        case_morph: Optional[List[str]] = None,
        idx: Optional[int] = None,
        pos: Optional[str] = None,
        whitespace_: str = " "
    ):
        self.text = text
        # Support POS tags passed directly as positional lemma_ argument in lightweight unit tests
        if lemma_ in ("NOUN", "PROPN", "VERB", "ADJ", "ADV", "PART", "PRON", "DET"):
            pos_ = lemma_
            lemma_ = None
            
        if pos is not None:
            pos_ = pos

        if lemma_ is None:
            cleaned = text.lower().strip(".,!?")
            self.lemma_ = cleaned if cleaned else text.lower()
        else:
            self.lemma_ = lemma_

        self.pos_ = pos_
        self.tag_ = tag_
        self.dep_ = dep_
        self.i = i
        self.idx = idx if idx is not None else i
        self.whitespace_ = whitespace_
        self._head_i = head_i
        self.head = self
        self.is_sent_start = is_sent_start
        self.like_url = like_url
        self.like_email = like_email
        self.morph = MockMorph({"Case": case_morph or []})
        
        if is_alpha is not None:
            self.is_alpha = is_alpha
        else:
            self.is_alpha = any(c.isalpha() for c in text)
        
    def __str__(self) -> str:
        return self.text


class MockDoc(list):
    """Simulates spaCy Doc sequence containing Tokens and Sentence spans."""
    def __init__(self, tokens: List[MockToken], text: str):
        super().__init__(tokens)
        self.text = text
        for token in self:
            if 0 <= getattr(token, "_head_i", -1) < len(self):
                token.head = self[token._head_i]
                
    @property
    def sents(self):
        class _Span:
            def __init__(self, t: str):
                self.text = t
        return [_Span(self.text)]


class MockPipelineNLP:
    """Simulates spaCy Language Pipeline model for integration baseline runners."""
    def __init__(self, lang: str = 'de'):
        self.lang = lang
        
    def __call__(self, text: str) -> MockDoc:
        import re
        tokens = []
        for idx, match in enumerate(re.finditer(r'\S+', text)):
            w = match.group(0)
            is_start = (idx == 0)
            tokens.append(MockToken(w, i=idx, idx=match.start(), is_sent_start=is_start))
        return MockDoc(tokens, text)

