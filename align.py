import sys
import argparse
import requests
import functools

@functools.cache
def align_tokens(source_tokens, target_tokens):
    source_tokens = source_tokens.split()
    target_tokens = target_tokens.split()
    url = 'https://lindat.cz/services/text-aligner/align/cs-uk'
    headers = {
        'Content-Type': 'application/json',
    }
    data = {
        'src_tokens': source_tokens,
        'trg_tokens': target_tokens,
    }

    response = requests.post(url, headers=headers, json=data)

    if response.status_code == 200:
        return response.json()["alignment"]
    else:
        print(f"Error: {response.status_code}", file=sys.stderr)
        print(response.text, file=sys.stderr)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Align texts line by line')
    parser.add_argument('src_file', help='Path to the source file')
    parser.add_argument('trg_file', help='Path to the target file')
    args = parser.parse_args()

    src_file = args.src_file
    trg_file = args.trg_file
    with open(src_file) as f_src, open(trg_file) as f_trg:
        for src, trg in zip(f_src, f_trg):
            src, trg = src.strip(), trg.strip()
            if not src or not trg:
                sys.stderr.write("EMPTY LINE\n")
                print()
                continue
            print(src, trg, file=sys.stderr)
            alignment = align_tokens(src, trg)
            print(alignment, file=sys.stderr)
            print("\n", file=sys.stderr)
            # sentences = " ".join(r.json()).replace("\n", "")
            # print(alignment)
            alignment_string = [f"{a}-{b}" for a,b in alignment]
            print(" ".join(alignment_string))
        assert not f_src.readline() and not f_trg.readline()