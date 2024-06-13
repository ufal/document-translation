import re
import sys
from typing import List, Tuple
import requests
import argparse

from sentence_splitter import SentenceSplitter # type: ignore

from batch_request import BatchRequest
from markuptranslator.markuptranslator import Translator

class LindatTranslator(Translator):
    def __init__(self, src_lang: str, tgt_lang: str, model: str):
        self.src_lang = src_lang
        self.tgt_lang = tgt_lang
        self.model = model
        self.splitter = SentenceSplitter(language=src_lang)
        def _send_batch(batch: List[str]) -> List[Tuple[str, str]]:
            text = "\n".join(batch) + "\n"
            src_sentences, tgt_sentences = self.translate_request(text)
            return list(zip(src_sentences, tgt_sentences))
        self.batch_request = BatchRequest(20000, _send_batch, lambda x: len((x+"\n").encode()))
    
    def translate(self, input_text: str) -> Tuple[List[str], List[str]]:
        lines = input_text.splitlines()
        sentences = self.batch_request.batch_process(lines)
        # unzip the sentences
        src_sentences, tgt_sentences = zip(*sentences)
        src_sentences, tgt_sentences = list(src_sentences), list(tgt_sentences)

        # remove final newline if there was none
        if not input_text.endswith("\n"):
            src_sentences[-1] = src_sentences[-1][:-1]
            tgt_sentences[-1] = tgt_sentences[-1][:-1]

        return src_sentences, tgt_sentences
    
    def sentences_to_text(self, sentences: List[str]) -> str:
        return " ".join(sentences).replace("\n ", "\n")

    def translate_request(self, input_text: str) -> Tuple[List[str], List[str]]:
        num_prefix_newlines = 0
        if input_text.startswith("\n"):
            while input_text[num_prefix_newlines] == "\n":
                num_prefix_newlines += 1
            input_text = input_text[num_prefix_newlines:]
        
        assert input_text.endswith("\n")
        input_text = input_text[:-1]

        # adjusted code from lindat frontend ====
        # TODO: adjust Charles Translator API to return the source sentence splits,
        #       so that we do not have to reconstruct it here
        SENT_LEN_LIMIT = 500
        def split_to_sent_array(text: str) -> List[str]:
            charlimit = SENT_LEN_LIMIT
            sent_array: List[str] = []
            for sent in self.splitter.split(text):
                while len(sent) > charlimit:
                    try:
                        # When sent starts with a space, then sent[0:0] was an empty string,
                        # and it caused an infinite loop. This fixes it.
                        beg = 0
                        while sent[beg] == ' ':
                            beg += 1
                        last_space_idx = sent.rindex(" ", beg, charlimit)
                        sent_array.append(sent[0:last_space_idx])
                        sent = sent[last_space_idx:]
                    except ValueError:
                        # raised if no space found by rindex
                        sent_array.append(sent[0:charlimit])
                        sent = sent[charlimit:]
                sent_array.append(sent)
            return sent_array

        def extract_sentences(text: str) -> Tuple[List[str], List[int]]:
            sentences: List[str] = []
            newlines_after: List[int] = []
            for segment in text.split('\n'):
                if segment:
                    sentences += split_to_sent_array(segment)
                newlines_after.append(len(sentences) - 1)
            return sentences, newlines_after

        def reconstruct_formatting(outputs: List[str], newlines_after: List[int]) -> List[str]:
            for i in newlines_after:
                if i >= 0:
                    outputs[i] += '\n'
            return outputs
        src_sentences = reconstruct_formatting(*extract_sentences(input_text))
        # / adjusted code from lindat frontend ====

        url = f"https://lindat.mff.cuni.cz/services/translation/api/v2/models/{self.model}"
        headers = {
            "accept": "application/json",
        }
        response = requests.post(url, headers=headers, files={
            'input_text': ('input.txt', input_text, 'text/plain')
        })
        
        if response.status_code != 200:
            print(f"Error: {response.status_code}", file=sys.stderr)
            print(response.text, file=sys.stderr)
            raise Exception
        tgt_sentences = response.json()
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
        return src_sentences, tgt_sentences

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Translate texts line by line')
    parser.add_argument('input_file', help='Input text file')
    parser.add_argument('src_lang', help='Source language')
    parser.add_argument('trg_lang', help='Target language')
    parser.add_argument('model', help='Target language')
    args = parser.parse_args()

    translator = LindatTranslator(args.src_lang, args.trg_lang, args.model)

    with open(args.input_file) as f_in:
        # TODO (low priority): make it streamin'
        source = f_in.read()
        src_sentences, tgt_sentences = translator.translate(source)
        print(translator.sentences_to_text(tgt_sentences), end="")