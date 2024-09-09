import logging
import re
from typing import List
import argparse

from lindat_services.align import LindatAligner
from document_translation.markuptranslator import MarkupTranslator, Tokenizer
from document_translation.regextokenizer import RegexTokenizer
from lindat_services.translate import LindatTranslator


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
loggers = [logging.getLogger(name) for name in logging.root.manager.loggerDict]
for _logger in loggers:
    _logger.setLevel(logger.level)

def main():
    parser = argparse.ArgumentParser(description='Translate texts line by line')
    parser.add_argument('input_file', help='Input text file with markup')
    parser.add_argument('src_lang', help='Source language')
    parser.add_argument('tgt_lang', help='Target language')
    parser.add_argument('model', help='Translation model')
    parser.add_argument('output_file', help='Output text file')
    parser.add_argument('--debug', action='store_true', help='Debug mode')
    args = parser.parse_args()

    if args.debug:
        logger.setLevel(logging.DEBUG)
        for _logger in loggers:
            _logger.setLevel(logger.level)

    translator = LindatTranslator(args.src_lang, args.tgt_lang, args.model)
    aligner = LindatAligner(args.src_lang, args.tgt_lang)
    tokenizer = RegexTokenizer()
    mt = MarkupTranslator(translator, aligner, tokenizer)

    with open(args.input_file) as f_in, open(args.output_file, "w") as f_out:
        input_text = f_in.read()
        output = mt.translate(input_text)
        f_out.write(output)

if __name__ == "__main__":
    main()