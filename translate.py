import requests, sys

def translate_text(input_text):
    url = "https://translator.cuni.cz/api/v2/languages"
    headers = {
        "accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
            "src": "cs",
            "tgt": "uk",
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

if __name__ == "__main__":
    for line in sys.stdin:
        translation = translate_text(line)
        sys.stderr.write(str(translation))
        print(translation)
