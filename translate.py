import requests, sys
import argparse

def _handle_response(response):
    if response.status_code == 200:
        response = response.json()
        sentences = " ".join(response).replace("\n ", "\n")
        return sentences
    else:
        print(f"Error: {response.status_code}");
        print(response.text)


def translate_text_lindat(input_text, src_lang, trg_lang):
    assert src_lang+"-"+trg_lang in [
        "en-cs","cs-en","en-hi","en-fr","fr-en","en-de","de-en","ru-en","en-ru","en-pl","pl-en","uk-cs","cs-uk","ru-cs","cs-ru"
    ]
    url = f"https://lindat.mff.cuni.cz/services/translation/api/v2/models/{src_lang}-{trg_lang}"
    headers = {
        "accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
            "src": src_lang,
            "tgt": trg_lang,
            "input_text": input_text,
    }

    response = requests.post(url, headers=headers, data=data)
    return _handle_response(response)


class BatchRequest:
    def __init__(self, batch_max_bytes, callback, compute_size=lambda x: len(x.encode())):
        self.batch = []
        self.batch_current_bytes = 0
        self.batch_max_bytes = batch_max_bytes
        self.callback = callback
        self.compute_size = compute_size
    
    def _send_batch(self):
        self.callback(self.batch)
        self.batch = []
        self.batch_current_bytes = 0

    def __call__(self, line):
        size = self.compute_size(line)
        if self.batch_current_bytes + size > self.batch_max_bytes:
            self._send_batch()
        self.batch.append(line)
        self.batch_current_bytes += size

    def flush(self):
        if self.batch:
            self._send_batch()

def _send_batch(batch, src_lang, trg_lang):
    batch_str = "".join(batch)
    print(repr(batch_str), file=sys.stderr)
    translation = translate_text_lindat(batch_str, src_lang, trg_lang)
    if translation.endswith("\n\n"):
        translation = translation[:-2]
    print(repr(translation), file=sys.stderr)
    print(translation)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Translate texts line by line')
    parser.add_argument('src_lang', default='cs', help='Source language')
    parser.add_argument('trg_lang', default='uk', help='Target language')
    args = parser.parse_args()

    batchreq = BatchRequest(100000, lambda l: _send_batch(l, args.src_lang, args.trg_lang))
    for line in sys.stdin:
        batchreq(line)
    batchreq.flush()