import logging
import re
from typing import List

from align import LindatAligner
from markuptranslator.markuptranslator import MarkupTranslator, Tokenizer
from translate import LindatTranslator


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
loggers = [logging.getLogger(name) for name in logging.root.manager.loggerDict]
for _logger in loggers:
    _logger.setLevel(logger.level)

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

import argparse
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Translate texts line by line')
    parser.add_argument('input_file', help='Input text file with markup')
    parser.add_argument('src_lang', help='Source language')
    parser.add_argument('tgt_lang', help='Target language')
    parser.add_argument('model', help='Translation model')
    parser.add_argument('output_file', help='Output text file')
    parser.add_argument('--debug', action='store_true', help='Debug mode')
    args = parser.parse_args()

    if args.debug:
        logger.setLevel(logging.DEBUG)
        for _logger in loggers:
            _logger.setLevel(logger.level)

    translator = LindatTranslator(args.src_lang, args.tgt_lang, args.model)
    aligner = LindatAligner(args.src_lang, args.tgt_lang)
    tokenizer = RegexTokenizer()
    mt = MarkupTranslator(translator, aligner, tokenizer)

    with open(args.input_file) as f_in, open(args.output_file, "w") as f_out:
        input_text = f_in.read()
        output = mt.translate(input_text)
        f_out.write(output)
