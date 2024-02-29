import requests, sys
import functools
import argparse

@functools.cache
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

    if response.status_code == 200:
        response = response.json()
        sentences = " ".join(response).replace("\n", "")
        return sentences
    else:
        print(f"Error: {response.status_code}");
        print(response.text)

@functools.cache
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

    if response.status_code == 200:
        response = response.json()
        sentences = " ".join(response).replace("\n", "")
        return sentences
    else:
        print(f"Error: {response.status_code}");
        print(response.text)


def translate_text(input_text, src_lang, trg_lang):
    if src_lang in ['cs', 'uk'] and trg_lang in ['cs', 'uk']:
        return translate_text_csuk(input_text)
    else:
        return translate_text_lindat(input_text, src_lang, trg_lang)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Translate texts line by line')
    parser.add_argument('src_lang', default='cs', help='Source language')
    parser.add_argument('trg_lang', default='uk', help='Target language')
    args = parser.parse_args()
    for line in sys.stdin:
        translation = translate_text(line, args.src_lang, args.trg_lang)
        sys.stderr.write(str(translation))
        print(translation)
