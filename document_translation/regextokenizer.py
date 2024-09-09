import re
from typing import List
from document_translation.markuptranslator import Tokenizer

class RegexTokenizer(Tokenizer):
    def __init__(self):
        ACCENT = chr(769)
        self.WORD_TOKENIZATION_RULES = re.compile(r"""
        [\w""" + ACCENT + """]+://(?:[a-zA-Z]|[0-9]|[$-_@.&+])+
        |[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+.[a-zA-Z0-9-.]+
        |[0-9]+-[а-яА-ЯіїІЇ'’`""" + ACCENT + r"""]+
        |[+-]?[0-9](?:[0-9,.-]*[0-9])?
        |[\w""" + ACCENT + r"""](?:[\w'’`-""" + ACCENT + r"""]?[\w""" + ACCENT + r"""]+)*
        |[\w""" + ACCENT + r"""].(?:\[\w""" + ACCENT + r"""].)+[\w""" + ACCENT + r"""]?
        |[^\s]
        |[.!?]+
        |-+
        """, re.X | re.U)

    def tokenize(self, string: str) -> List[str]:
        return re.findall(self.WORD_TOKENIZATION_RULES, string)
