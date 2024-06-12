import logging
import re
from typing import List, Tuple
from sentence_splitter import SentenceSplitter # type: ignore
import requests

from markuptranslator.markuptranslator import Aligner, MarkupTranslator, Tokenizer, Translator
from translate import LindatTranslator


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

import sys
class LindatAligner(Aligner):
    def __init__(self, src_lang: str, tgt_lang: str):
        self.src_lang = src_lang
        self.tgt_lang = tgt_lang
    def align(self, src_batch: List[List[str]], tgt_batch: List[List[str]]) -> List[List[Tuple[int, int]]]:
        src_lang = self.src_lang
        tgt_lang = self.tgt_lang

        url = f'https://lindat.cz/services/text-aligner/align/{src_lang}-{tgt_lang}'
        headers = {
            'Content-Type': 'application/json',
        }
        data = {
            'src_tokens': src_batch,
            'trg_tokens': tgt_batch,
        }
        print("Alignment data", data)
        tgt_lang = self.tgt_lang


        response = requests.post(url, headers=headers, json=data)

        if response.status_code == 200:
            alignment = response.json()["alignment"]
            alignment = [[(int(a[0]), int(a[1])) for a in al] for al in alignment]
            return alignment
        else:
            print(f"Error: {response.status_code}", file=sys.stderr)
            print(response.text, file=sys.stderr)
            raise Exception

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
    args = parser.parse_args()

    translator = LindatTranslator(args.src_lang, args.tgt_lang, args.model)
    aligner = LindatAligner(args.src_lang, args.tgt_lang)
    tokenizer = RegexTokenizer()
    mt = MarkupTranslator(translator, aligner, tokenizer)

    with open(args.input_file) as f_in, open(args.output_file, "w") as f_out:
        input_text = f_in.read()
        print(repr(input_text))
        output = mt.translate(input_text)
        print(repr(output))
        f_out.write(output)
