import sys
import argparse
import requests

def align_tokens(source_tokens, target_tokens):
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
        print(f"Error: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Align texts line by line')
    parser.add_argument('src_file', help='Path to the source file')
    parser.add_argument('trg_file', help='Path to the target file')
    args = parser.parse_args()

    src_file = args.src_file
    trg_file = args.trg_file
    with open(src_file) as f_src, open(trg_file) as f_trg:
        for src, trg in zip(f_src, f_trg):
            src, trg = src.strip().split(), trg.strip().split()
            if not src or not trg:
                sys.stderr.write("EMPTY LINE\n")
                print()
                continue
            r = align_tokens(src, trg)
            sys.stderr.write(str(r))
            # sentences = " ".join(r.json()).replace("\n", "")
            print(r["alignment"])
        assert not f_src.readline() and not f_trg.readline()