import requests, sys

url = "https://translator.cuni.cz/api/v2/languages/"
for line in sys.stdin:
    r = requests.post(
        url,
        data={
            "src": "cs",
            "tgt": "uk",
            "input_text": line,
            "logInput": "false",
            "author": "H-edu",
        },
        headers={
            "accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    #    print(r.json())
    sys.stderr.write(str(r.json()))
    sentences = " ".join(r.json()).replace("\n", "")
    print(sentences)
