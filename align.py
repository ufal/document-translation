import argparse
from typing import List, Tuple
import requests
import json

from batch_request import BatchRequest
from markuptranslator.markuptranslator import Aligner

class LindatAligner(Aligner):
    def __init__(self, src_lang: str, tgt_lang: str):
        self.src_lang = src_lang
        self.tgt_lang = tgt_lang
        def _send_batch(batch: List[Tuple[str, str]]) -> List[List[Tuple[int, int]]]:
            src_batch, tgt_batch = zip(*batch)
            return self.align_request(src_batch, tgt_batch)

        def _compute_size(x: Tuple[str, str]) -> int:
            return len(json.dumps(x).encode())

        self.batch_request = BatchRequest(100000, _send_batch, _compute_size)

    def align(self, src_batch: List[List[str]], tgt_batch: List[List[str]]) -> List[List[Tuple[int, int]]]:
        
        return self.batch_request.batch_process(list(zip(src_batch, tgt_batch)))

    def align_request(self, src_batch: List[List[str]], tgt_batch: List[List[str]]) -> List[List[Tuple[int, int]]]:
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

        response = requests.post(url, headers=headers, json=data)

        if response.status_code == 200:
            alignment = response.json()["alignment"]
            alignment = [[(int(a[0]), int(a[1])) for a in al] for al in alignment]
            return alignment
        else:
            raise Exception(f"Request failed with status code {response.status_code}\n{response.text}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Align texts line by line')
    parser.add_argument('src_file', help='Path to the source file')
    parser.add_argument('trg_file', help='Path to the target file')
    parser.add_argument('src_lang', help='Source language')
    parser.add_argument('trg_lang', help='Target language')
    args = parser.parse_args()

    src_file = args.src_file
    trg_file = args.trg_file

    aligner = LindatAligner(args.src_lang, args.trg_lang)
    
    with open(src_file) as f_src, open(trg_file) as f_trg:
        src_lines = [src.strip().split() for src in f_src]
        tgt_lines = [trg.strip().split() for trg in f_trg]
        assert len(src_lines) == len(tgt_lines), f"Files must have the same number of lines"

        alignments = aligner.align(src_lines, tgt_lines)
        for alignment in alignments:
            print(" ".join([f"{a}-{b}" for a,b in alignment]))
