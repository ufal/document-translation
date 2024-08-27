import re
from typing import List, Tuple
import unittest
import logging

from align import LindatAligner
from markuptranslator.alignedsegments import AlignedSegments
from markuptranslator.alignment import Alignment
from markuptranslator.markuptranslator import Aligner, MarkupTranslator, Translator
from markuptranslator.segmentedtext import SegmentedText, WhitespaceSegment
from markuptranslator.tagreinserter import TagReinserter
from translate import LindatTranslator
from translate_markup import RegexTokenizer

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
# set the level of all loggers to DEBUG
loggers = [logging.getLogger(name) for name in logging.root.manager.loggerDict]
for logger in loggers:
    logger.setLevel(logging.DEBUG)

class TagReinserterTester(unittest.TestCase):
    def test_reinsert_segments_simple(self):
        src = SegmentedText.from_string_list(["<x id='1'/>","This","<x id='2'/>","is","<x id='3'/>","<x id='4'/>","<x id='5'/>","test","<x id='6'/>",".","<x id='7'/>","<x id='8'/>","<x id='9'/>"])
        tgt = SegmentedText.from_string_list(["Toto","je","test","."])
        
        aligned_segments = AlignedSegments(src, tgt)
        aligned_segments.alignment_from_iterable([(1, 0), (3, 1), (7, 2), (9, 3)])
        
        TagReinserter.reinsert_segments(aligned_segments)

        tgt_reinserted = "<x id='1'/>Toto<x id='2'/>je<x id='3'/><x id='4'/><x id='5'/>test<x id='6'/>.<x id='7'/><x id='8'/><x id='9'/>"
        self.assertEqual(str(aligned_segments.tgt), tgt_reinserted)
    
    def test_reinsert_tags_simple(self):
        src = SegmentedText.from_string_list([
            "<g id='1'>","<g id='2'>","Můj"," ","<g id='3'>","přítel","</g>","</g>",","," ",
            "který"," ","pracuje"," ","<g id='4'>","v"," ","bankovním"," ","sektoru","</g>",","," ",
            "<g id='5'>","se"," ","v"," ","říjnu"," ","žení","</g>",".","</g>"
        ])
        src = SegmentedText(filter(lambda x: not isinstance(x, WhitespaceSegment), src))
        # tgt = SegmentedText.from_string_list(["A"," ","friend"," ","of"," ","mine"," ","who"," ","works"," ","in"," ","banking"," ","is"," ","getting"," ","married"," ","in"," ","October","."])
        tgt = SegmentedText.from_string("A friend of mine who works in banking is getting married in October .")
        aligned_segments = AlignedSegments(src, tgt)
        aligned_segments.alignment_from_iterable([(2,6), (4,2), (8,8), (9,10), (11,12),(12,14),(13,14),(17,22),(19,24),(20,18),(20,20),(22,26)])

        print("BEGIN STATE")
        aligned_segments.debug_print()

        print("PROCEED")
        TagReinserter.reinsert_tags(aligned_segments)

        print("END STATE")
        aligned_segments.debug_print()

    def test_reinsert_long_tag(self):
        src = SegmentedText.from_string_list([
            "<g id='1'>","<g id='2'>","<g id='3'>","Můj","</g>"," ","<g id='4'>","přítel","</g>","</g>","</g>"
        ])
        tgt = SegmentedText.from_string("A friend of mine")
        aligned_segments = AlignedSegments(src, tgt)
        aligned_segments.alignment_from_iterable([(3,6),(7,2)])

        aligned_segments.debug_print()
        TagReinserter.reinsert_tags(aligned_segments)
        aligned_segments.debug_print()
        self.assertEqual(str(aligned_segments.tgt), "<g id='1'><g id='2'>A <g id='4'>friend</g> of <g id='3'>mine</g></g></g>")

    def test_reinsert_tag_wordend(self):
        src = SegmentedText.from_string_list([
            # <g id="1"><g id="2"><g id="3"></g><g id="4">Jak číst taxobox</g></g></g>Mateřídouška
            '<g id="1">', '<g id="2">', '<g id="3">', '</g>', '<g id="4">', 'Jak', ' ', 'číst', ' ', 'taxobox', '</g>', '</g>', '</g>', 'Mateřidouška'
        ])

        tgt = SegmentedText.from_string_list(['Jak', ' ', 'číst', ' ', 'taxobox', 'Mateřidouška'])
        aligned_segments = AlignedSegments(src, tgt)
        aligned_segments.alignment_from_iterable([(5,0), (6,1), (7,2), (8,3), (9, 4), (13, 5)])
        aligned_segments.debug_print()
        TagReinserter.reinsert_tags(aligned_segments)
        aligned_segments.debug_print()


class DummyTranslator(Translator):
    def translate(self, input_text: str) -> Tuple[List[str], List[str]]:
        """
        src_text is a multiline string.
        The output is a list of sentences
        """
        # dummy translate
        tgt = input_text.replace("Ahoj", "Hello")
        tgt = tgt.replace("světe", "world")
        tgt = tgt.replace("Jak se máš", "How are you")
        tgt = tgt.replace("Mám se fajn", "I am fine")
        def _sentence_split(text: str):
            output: List[str] = []
            for line in re.split(r"(\n+)", text):
                if not line:
                    continue
                if line.startswith("\n") and output:
                    output[-1] += line
                else:
                    output.extend([x[0] for x in re.findall(r"([^\.\!\?]+(\.|\!|\?))", line)])
                    # output += 
            return output

        return _sentence_split(input_text), _sentence_split(tgt)

class DummyAligner(Aligner):
    def align(self, src_batch: List[List[str]], tgt_batch: List[List[str]]) -> List[List[Tuple[int, int]]]:
        return [[(i, i) for i in range(len(src))] for src in src_batch]

class MarkupTranslatorTester(unittest.TestCase):
    def setUp(self):
        self.markup_translator = MarkupTranslator(translator=DummyTranslator(), aligner=DummyAligner(), tokenizer=RegexTokenizer())

    def test_nomarkup(self):
        src = "Ahoj světe! Jak se máš?\n\nMám se fajn.\n\n"
        tgt_expected = "Hello world! How are you?\n\nI am fine.\n\n"
        
        tgt = self.markup_translator.translate(src)
        self.assertEqual(tgt, tgt_expected)

    def test_simple(self):
        src = "Ahoj <g id='1'>světe</g>!<ex id='2'/> Jak se máš?\n\n<bx id='3'/>Mám se <g id='4'>fajn</g>.\n\n"
        tgt_expected = "Hello <g id='1'>world</g>!<ex id='2'/> How are you?\n\n<bx id='3'/>I am <g id='4'>fine</g>.\n\n"
        tgt = self.markup_translator.translate(src)
        self.assertEqual(tgt, tgt_expected)
    # TODO: otestovat vnořené tagy, taky jestli se zachovává jejich pořadí

    def test_whitespace(self):
        src = "   Ahoj\t\tsvěte.    \n     Jak\t\t\tse    máš?\n\n"
        tgt_expected = "   Hello\t\tworld.    \n     How\t\t\tare    you?\n\n"
        tgt = self.markup_translator.translate(src)
        self.assertEqual(tgt, tgt_expected)

    def test_whitespace_2(self):
        src = " <g id='1'>\t</g>  <g id='2'>Ahoj\t</g><g id='3'>\tsvěte<g id='4'>.\t</g>\t</g> \t \n  Jak\t\t\tse    máš?\n\n"
        tgt_expected = " <g id='1'>\t</g>  <g id='2'>Hello\t</g><g id='3'>\tworld<g id='4'>.\t</g>\t</g> \t \n  How\t\t\tare    you?\n\n"
        tgt = self.markup_translator.translate(src)
        self.assertEqual(tgt, tgt_expected)

class ProductionMarkupTranslatorTester(unittest.TestCase):
    def setUp(self):
        translator = LindatTranslator("cs", "en", "cs-en")
        aligner = LindatAligner("cs", "en")
        tokenizer = RegexTokenizer()
        self.mt = MarkupTranslator(translator, aligner, tokenizer)

    def test_crossing(self):
        src = 'Pěstování<g id="1"> tabáku </g>a<g id="2"> cukrové třtiny </g>– plantáže.'
        tgt = self.mt.translate(src)
        print(src)
        print(tgt)

    def test_crossing_hard(self):
        src = 'Podrobnosti naleznete na stránce <g id="3">Podmínky užití</g>.'
        tgt = self.mt.translate(src)
        print(src)
        print(tgt)

    def test_keep_ending_whitespace(self):
        src = 'Testovací věta. Testovací věta'
        # tgt_expected = " <g id='1'>\t</g>  <g id='2'>Hello\t</g><g id='3'>\tworld<g id='4'>.\t</g>\t</g> \t \n  How\t\t\tare    you?\n\n"
        tgt = self.mt.translate(src)
        print(tgt)
        # self.assertEqual(tgt, tgt_expected)

if __name__ == "__main__":
    unittest.main()
