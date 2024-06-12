import logging
import re
from typing import List, Tuple
from sentence_splitter import SentenceSplitter # type: ignore
import requests

from markuptranslator.markuptranslator import Aligner, MarkupTranslator, Tokenizer, Translator


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class LindatTranslator(Translator):
    def __init__(self, src_lang: str, tgt_lang: str, model: str):
        self.src_lang = src_lang
        self.tgt_lang = tgt_lang
        self.model = model
        self.splitter = SentenceSplitter(language=src_lang)
    def translate(self, input_text: str) -> Tuple[List[str], List[str]]:
        url = f"https://lindat.mff.cuni.cz/services/translation/api/v2/models/{self.model}"
        headers = {
            "accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        num_prefix_newlines = 0
        if input_text.startswith("\n"):
            while input_text[num_prefix_newlines] == "\n":
                num_prefix_newlines += 1
            input_text = input_text[num_prefix_newlines:]

        print("LINDAT TRANSLATOR HERE")
        SENT_LEN_LIMIT = 500
        def _sentence_split(text: str):
            output: List[str] = []
            for line in re.split(r"(\n+)", text):
                if not line:
                    continue
                if line.startswith("\n") and output:
                    output[-1] += line
                else:
                    output.extend(self.splitter.split(line))
            return output
        
        def split_to_sent_array(text: str):
            sent_array: List[str] = []
            for sent in _sentence_split(text):
                while len(sent) > SENT_LEN_LIMIT:
                    try:
                        # When sent starts with a space, then sent[0:0] was an empty string,
                        # and it caused an infinite loop. This fixes it.
                        beg = 0
                        while sent[beg] == ' ':
                            beg += 1
                        last_space_idx = sent.rindex(" ", beg, SENT_LEN_LIMIT)
                        sent_array.append(sent[0:last_space_idx])
                        sent = sent[last_space_idx:]
                    except ValueError:
                        # raised if no space found by rindex
                        sent_array.append(sent[0:SENT_LEN_LIMIT])
                        sent = sent[SENT_LEN_LIMIT:]
                sent_array.append(sent)
            return sent_array

        src_sentences = split_to_sent_array(input_text)
        data = {
                "src": self.src_lang,
                "tgt": self.tgt_lang,
                "input_text": input_text,
        }
        print("====")
        tgt_sentences = requests.post(url, headers=headers, data=data).json()
        assert len(src_sentences) == len(tgt_sentences), f"{len(src_sentences)} != {len(tgt_sentences)}"
        if tgt_sentences:
            # if the line was empty or whitespace-only, then discard any potential translation
            new_tgt_sentences: List[str] = []
            for src, tgt in zip(src_sentences, tgt_sentences):
                if re.match(r"^\s+$", src):
                    new_tgt_sentences.append(src)
                else:
                    new_tgt_sentences.append(tgt)
            tgt_sentences = new_tgt_sentences
            # reinsert prefix newlines
            src_sentences[0] = "\n" * num_prefix_newlines + src_sentences[0]
            tgt_sentences[0] = "\n" * num_prefix_newlines + tgt_sentences[0]
            # add spaces after sentence ends
            tgt_sentences = [tgt_sentence + " " if not tgt_sentence.endswith("\n") else tgt_sentence for tgt_sentence in tgt_sentences]
            # remove final newline
            assert tgt_sentences[-1].endswith("\n")
            tgt_sentences[-1] = tgt_sentences[-1][:-1]
        print("")
        print(src_sentences, tgt_sentences)
        return src_sentences, tgt_sentences

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
