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


def translate_text_csuk(input_text, src_lang, trg_lang):
    assert src_lang in ['cs', 'uk'] and trg_lang in ['cs', 'uk']
    url = "https://translator.cuni.cz/api/v2/languages"
    headers = {
        "accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
            "src": src_lang,
            "tgt": trg_lang,
            "input_text": input_text,
            "logInput": "false",
            "author": "H-edu",
    }

    response = requests.post(url, headers=headers, data=data)
    return _handle_response(response)

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


def translate_text(input_text, src_lang, trg_lang):
    if src_lang in ['cs', 'uk'] and trg_lang in ['cs', 'uk']:
        return translate_text_csuk(input_text)
    else:
        return translate_text_lindat(input_text, src_lang, trg_lang)

def _send_batch(batch, src_lang, trg_lang):
        batch_str = "".join(batch)
        print(repr(batch_str), file=sys.stderr)
        translation = translate_text(batch_str, src_lang, trg_lang)
        if translation.endswith("\n\n"):
            translation = translation[:-2]
        print(repr(translation), file=sys.stderr)
        print(translation)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Translate texts line by line')
    parser.add_argument('src_lang', default='cs', help='Source language')
    parser.add_argument('trg_lang', default='uk', help='Target language')
    args = parser.parse_args()

    batch = []
    total_batch = 0
    for line in sys.stdin:
        b = line.encode()
        if total_batch + len(b) > 100000:
            _send_batch(batch, args.src_lang, args.trg_lang)
            batch = []
            total_batch = 0
        else:
            batch.append(line)
            total_batch += len(b)
    _send_batch(batch, args.src_lang, args.trg_lang)