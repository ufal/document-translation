import re
from typing import List, Tuple
import unittest
import logging

import mosestokenizer as moses # type: ignore

from translate_markup import Aligner, MarkupTranslator, SegmentedText, Alignment, AlignedSegments, TagReinserter, WhitespaceSegment, Tokenizer, Translator

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class TagReinserterTester(unittest.TestCase):
    def test_reinsert_segments_simple(self):
        src = SegmentedText.from_string_list(["This","is","<x id='1'/>","<x id='2'/>","<x id='3'/>","test","<x id='2'/>",".","<x id='3'/>","<x id='4'/>","<x id='5'/>"])
        tgt = SegmentedText.from_string_list(["Toto"," ","je"," ","test","."])
        alignment = Alignment([(0, 0), (1, 2), (5, 4), (7, 5)])
        
        aligned_segments = AlignedSegments(src, tgt, alignment)
        
        print("BEGIN STATE")
        print(aligned_segments)

        print("PROCEED")
        TagReinserter.reinsert_segments(aligned_segments)

        print("END STATE")
        print(aligned_segments)

        # tgt_reinserted = SegmentedText.from_string_list(["Toto"," ","je"," ","<x id='1'/>","test","<x id='2'/>","."])
        # self.assertEqual(aligned_segments.tgt, tgt_reinserted)
    
    def test_reinsert_tags_simple(self):
        src = SegmentedText.from_string_list([
            "<g id='1'>","<g id='2'>","Můj"," ","<g id='3'>","přítel","</g>","</g>",","," ",
            "který"," ","pracuje"," ","<g id='4'>","v"," ","bankovním"," ","sektoru","</g>",","," ",
            "<g id='5'>","se"," ","v"," ","říjnu"," ","žení","</g>",".","</g>"
        ])
        src = SegmentedText(filter(lambda x: not isinstance(x, WhitespaceSegment), src))
        # tgt = SegmentedText.from_string_list(["A"," ","friend"," ","of"," ","mine"," ","who"," ","works"," ","in"," ","banking"," ","is"," ","getting"," ","married"," ","in"," ","October","."])
        tgt = SegmentedText.from_string("A friend of mine who works in banking is getting married in October .")
        alignment = Alignment([(2,6), (4,2), (8,8), (9,10), (11,12),(12,14),(13,14),(17,22),(19,24),(20,18),(20,20),(22,26)])
        aligned_segments = AlignedSegments(src, tgt, alignment)

        print("BEGIN STATE")
        aligned_segments.debug_print()

        print("PROCEED")
        TagReinserter.reinsert_tags(aligned_segments)

        print("END STATE")
        aligned_segments.debug_print()

class DummyTranslator(Translator):
    def translate(self, src: str) -> Tuple[List[str], List[str]]:
        """
        src_text is a multiline string.
        The output is a list of sentences
        """
        # dummy translate
        tgt = src.replace("Ahoj světe", "Hello world")
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
                    output.extend([x[0].lstrip() for x in re.findall(r"([^\.\!\?]+(\.|\!|\?))", line)])
                    # output += 
            return output

        return _sentence_split(src), _sentence_split(tgt)

class DummyAligner(Aligner):
    def align(self, src_batch: List[List[str]], tgt_batch: List[List[str]]) -> List[List[Tuple[int, int]]]:
        return [[(i, i) for i in range(len(src))] for src in src_batch]

class MosesTokenizer(Tokenizer):
    def __init__(self):
        self.t = moses.MosesTokenizer()
    def tokenize(self, string: str) -> List[str]:
        return self.t(string) # type: ignore

class MarkupTranslatorTester(unittest.TestCase):
    def setUp(self):
        self.markup_translator = MarkupTranslator(translator=DummyTranslator(), aligner=DummyAligner(), tokenizer=MosesTokenizer())

    def test_nomarkup(self):
        src = "Ahoj světe! Jak se máš?\n\nMám se fajn.\n\n"
        tgt_expected = "Hello world! How are you?\n\nI am fine.\n\n"
        
        tgt = self.markup_translator.translate(src)
        # self.assertEqual(tgt, tgt_expected)

    def test_simple(self):
        src = "Ahoj <g id='1'>světe</g>!<ex id='2'/> Jak se máš?\n\n<bx id='3'/>Mám se <g id='4'>fajn</g>.\n\n"
        tgt_expected = "Hello <g id='1'>world</g>!<ex id='2'/> How are you?\n\n<bx id='3'/>I am <g id='4'>fine</g>.\n\n"
        tgt = self.markup_translator.translate(src)
        # self.assertEqual(tgt, tgt_expected)
    # TODO: otestovat vnořené tagy, taky jestli se zachovává jejich pořadí

if __name__ == "__main__":
    unittest.main()
