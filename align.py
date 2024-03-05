import sys
import argparse
import requests
from translate import BatchRequest

def align_tokens(source_tokens, target_tokens, src_lang, trg_lang):
    url = f'https://lindat.cz/services/text-aligner/align/{src_lang}-{trg_lang}'
    headers = {
        'Content-Type': 'application/json',
    }
    data = {
        'src_tokens': source_tokens,
        'trg_tokens': target_tokens,
    }

    response = requests.post(url, headers=headers, json=data)

    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error: {response.status_code}", file=sys.stderr)
        print(response.text, file=sys.stderr)

def _send_batch(batch, src_lang, trg_lang):
    print(repr(batch), file=sys.stderr)
    source_tokens, target_tokens = zip(*batch)
    alignments = align_tokens(source_tokens, target_tokens, src_lang, trg_lang)
    print(repr(alignments), file=sys.stderr)
    for alignment in alignments["alignment"]:
        print(repr(alignment), file=sys.stderr)
        alignment_string = [f"{a}-{b}" for a,b in alignment]
        print(" ".join(alignment_string))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Align texts line by line')
    parser.add_argument('src_file', help='Path to the source file')
    parser.add_argument('trg_file', help='Path to the target file')
    parser.add_argument('src_lang', help='Source language')
    parser.add_argument('trg_lang', help='Target language')
    args = parser.parse_args()

    src_file = args.src_file
    trg_file = args.trg_file
    callback = lambda l: _send_batch(l, args.src_lang, args.trg_lang)
    compute_size = lambda x: len(" ".join(x[0]).encode()) + len(" ".join(x[1]).encode())
    batchreq = BatchRequest(100000, callback, compute_size)
    
    with open(src_file) as f_src, open(trg_file) as f_trg:
        for src, trg in zip(f_src, f_trg):
            src, trg = src.strip().split(), trg.strip().split()
            batchreq((src, trg))
        batchreq.flush()
        assert not f_src.readline() and not f_trg.readline()
