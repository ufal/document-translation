import logging
import argparse

from document_translation.lindat_services.align import LindatAligner
from document_translation.markuptranslator import MarkupTranslator
from document_translation.regextokenizer import RegexTokenizer
from document_translation.lindat_services.translate import LindatTranslator
from document_translation.pdf_tools.pdfeditor import PdfEditor

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
loggers = [logging.getLogger(name) for name in logging.root.manager.loggerDict]
for _logger in loggers:
    _logger.setLevel(logger.level)

def main():
    parser = argparse.ArgumentParser(description='Translate PDF file')
    parser.add_argument('input_file', help='Input PDF file')
    parser.add_argument('src_lang', help='Source language')
    parser.add_argument('tgt_lang', help='Target language')
    parser.add_argument('model', help='Translation model')
    parser.add_argument('output_file', help='Output PDF file')
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

    pdf_editor = PdfEditor(args.input_file)

    lines = pdf_editor.extract_text()

    input_text = "<lb />".join(lines)
    assert "\n" not in input_text
    input_text = input_text.replace("<page-break />", "\n")

    translations = mt.translate(input_text)

    translated_lines = translations.replace("\n", "<page-break />").split("<lb />")
    assert len(lines) == len(translated_lines), f"{len(lines)} != {len(translated_lines)}"
    pdf_editor.merge_text(translated_lines, args.output_file)


if __name__ == "__main__":
    main()