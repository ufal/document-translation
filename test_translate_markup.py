from collections import defaultdict
from functools import cached_property
from typing import Callable, Dict, Iterable, List, Optional, Self, Set, Tuple
import unittest
import re
from enum import Enum
import mosestokenizer as moses

from termcolor import colored

import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class Translator:
    def translate(self, src: str) -> Tuple[List[str], List[str]]:
        raise NotImplementedError

class Aligner:
    def align(self, src_batch: List[List[str]], tgt_batch: List[List[str]]) -> List[List[Tuple[int, int]]]:
        raise NotImplementedError

class Tokenizer:
    def tokenize(self, string: str) -> List[str]:
        raise NotImplementedError

# TODO (low priority): it makes more sense to subclass Segment instead of using SegmentType
class SegmentType(Enum):
    TEXT = 0
    TAG = 1
    WHITESPACE = 2
    SENTENCE_SEP = 3

class Segment(object):
    # TODO (low priority): we repeat code here, this should be probably moved into SegmentedText.from_string
    tag_pattern = r'<\/?(g|x|bx|ex|lb|mrk).*?>'
    tag_regex = re.compile(tag_pattern)
    whitespace_regex = re.compile(r'\s+')

    def __init__(self, string: str, type: SegmentType):
        self.string = string
        self.type = type
    
    @classmethod
    def from_string(cls, string: str):
        if cls.tag_regex.match(string):
            return cls(string, SegmentType.TAG)
        if cls.whitespace_regex.match(string):
            return cls(string, SegmentType.WHITESPACE)
        return cls(string, SegmentType.TEXT)

    def debug_color(self, string: str) -> str:
        if self.type == SegmentType.TAG:
            return colored(string, "black", "on_cyan", attrs=["bold"])
        if self.type == SegmentType.WHITESPACE:
            return colored(string, "white", "on_blue")
        if self.type == SegmentType.SENTENCE_SEP:
            return colored(string, "black", "on_red")
        return colored(string, "black", "on_white")

    def __len__(self) -> int:
        return len(self.string)
    
    def __str__(self) -> str:
        return self.string

    def debug_str(self) -> str:
        string = repr(self.string) if self.whitespace_regex.match(self.string) else self.string
        return self.debug_color(string)

    def debug_len(self) -> int:
        return len(repr(self.string)) if self.whitespace_regex.match(self.string) else len(self.string)

class SentenceSeparator(Segment):
    def __init__(self):
        super().__init__("", SegmentType.SENTENCE_SEP)

    def debug_str(self) -> str:
        return self.debug_color("||")

    def debug_len(self) -> int:
        return 2

class JoinedSegment(Segment):
    def __init__(self, segments: List[Segment]):
        self.segments = segments
    
    def __len__(self) -> int:
        return sum(len(s) for s in self.segments)
    
    def debug_color(self, string: str) -> str:
        return colored(string, "black", "on_yellow", attrs=["underline"])
    
    def __str__(self) -> str:
        return ''.join(str(x) for x in self.segments)
        
    def debug_str(self) -> str:
        return ''.join(colored(x.debug_str(), attrs=["underline"]) for x in self.segments)

class SegmentedText(list[Segment]):
    """
    A text that has been split into segments of text, tags and whitespace.
    The main assumption is that joining the segments will yield the original text.
    """
    tag_pattern = r'<\/?(g|x|bx|ex|lb|mrk).*?>'
    tag_regex = re.compile(tag_pattern)
    whitespace_regex = re.compile(r'\s+')
    segments_regex = re.compile(r'('+tag_pattern+r'|\s+|[^<\s]+|[^>\s]+)')

    def __init__(self, iterable: Optional[Iterable[Segment]] = None):
        if iterable is None:
            iterable = []
        super().__init__(iterable)

    @classmethod
    def from_string(cls, string: str):
        segment_strings = cls.segments_regex.findall(string)
        segment_strings = map(lambda x: x[0], segment_strings)
        return cls([Segment.from_string(s) for s in segment_strings])
    
    @classmethod
    def from_string_list(cls, strings: List[str]):
        return cls([Segment.from_string(s) for s in strings])
    
    @classmethod
    def from_sentences(cls, sentences: List[str]):
        # TODO (low priority): output could be SegmentedText
        output: list[Segment] = []
        for sentence in sentences:
            output += cls.from_string(sentence) + [SentenceSeparator()]
        return cls(output[:-1])
    
    def tokenize(self, tokenizer: Tokenizer):
        # TODO (low priority): new_segments could be SegmentedText
        new_segments: list[Segment] = []
        for seg in self:
            if seg.type == SegmentType.TEXT:
                tokens = tokenizer.tokenize(str(seg))
                if len(tokens) > 1:
                    for tok in tokens:
                        new_segments.append(Segment(tok, SegmentType.TEXT))
                else:
                    new_segments.append(seg)
            else:
                new_segments.append(seg)
        return SegmentedText(new_segments)
    
    def __str__(self) -> str:
        return ''.join(str(x) for x in self)

    def debug_str(self) -> str:
        return ''.join(x.debug_str() for x in self)

    def debug_print(self) -> None:
        print(self.debug_str())
        index_top = 0
        index_bottom = 0
        for i, seg in enumerate(self):
            index_str = str(i)
            print(seg.debug_color(index_str), end="")
            index_top += seg.debug_len()
            index_bottom += len(index_str)
            if index_bottom < index_top:
                print(" "*(index_top-index_bottom), end="")
                index_bottom = index_top
        print()

    def translation_view(self):
        # TODO (low priority): maybe rename tgt to something like src_for_translation
        tgt = SegmentedText()
        alignment = Alignment()
        for i, s in enumerate(self):
            if s.type == SegmentType.TAG:
                continue
            elif s.type == SegmentType.WHITESPACE:
                normalized_whitespace = re.sub(r'[^\n]', ' ', s.string)
                tgt.append(Segment(normalized_whitespace, SegmentType.WHITESPACE))
                alignment.mapping.append((i, len(tgt) - 1))
            else:
                tgt.append(s)
                alignment.mapping.append((i, len(tgt) - 1))
        return tgt, alignment
    
    # def iter_characters(self):
    #     for i, seg in enumerate(self):
    #         for j, c in enumerate(seg.string):
    #             yield i, j, c

    def alignment_view(self):
        tgt = SegmentedText()
        alignment = Alignment()
        for i, s in enumerate(self):
            if s.type == SegmentType.TEXT or s.type == SegmentType.SENTENCE_SEP:
                tgt.append(s)
                alignment.mapping.append((i, len(tgt) - 1))
        return tgt, alignment

    def split_sentences(self):
        i = 0
        for j, seg in enumerate(self):
            if seg.type == SegmentType.SENTENCE_SEP:
                # TODO (low priority): why self[i:j] does not return SegmentedText right away?
                yield SegmentedText(self[i:j])
                i = j + 1
        yield SegmentedText(self[i:])


class Alignment:
    # TODO (low priority): instead of List[Tuple[int, int]] we could use something like Dict[Segment, List[Segment]]
    #                      that way the alignment would be invariant to the order of the segments
    def __init__(self, mapping: Optional[List[Tuple[int, int]]] = None):
        if mapping is None:
            mapping = []
        self.mapping = mapping
    
    @cached_property
    def src_to_tgt(self) -> Dict[int, List[int]]:
        src_to_tgt: Dict[int, List[int]] = defaultdict(list)
        for i, j in self.mapping:
            src_to_tgt[i].append(j)
        return src_to_tgt

    def get_src(self, i: int) -> List[int]:
        return self.src_to_tgt.get(i, [])

    def map(self, f: Callable[[int, int], Tuple[int, int]]):
        return Alignment(list(map(lambda x: f(*x), self.mapping)))
    
    def __str__(self) -> str:
        return f"Alignment({self.mapping})"
    
    def __add__(self, other: Self):
        return Alignment(self.mapping + other.mapping)


class AlignedSegments:
    def __init__(self,
                 src_segments: Optional[SegmentedText] = None,
                 tgt_segments: Optional[SegmentedText] = None,
                 alignment: Optional[Alignment] = None):
        if src_segments is None:
            src_segments = SegmentedText()
        if tgt_segments is None:
            tgt_segments = SegmentedText()
        if alignment is None:
            alignment = Alignment()
        self.src = src_segments
        self.tgt = tgt_segments
        self.alignment = alignment

    def insert_segment(self, index: int, segment: Segment) -> None:
        self.tgt.insert(index, segment)
        self.alignment = self.alignment.map(lambda i, j: (i, j+1) if j >= index else (i, j))

    def join_adjacent_segments(self, index: int) -> None:
        """
        Joins the segments at `index` and `index+1` and inserts the result at `index`.
        If the segment at `index` is already a JoinedSegment, the segments are appended to it.
        """
        fst = self.src.pop(index)
        snd = self.src.pop(index)
        if isinstance(fst, JoinedSegment):
            fst.segments.append(snd)
            self.src.insert(index, fst)
        else:
            new_seg = JoinedSegment([fst, snd])
            self.src.insert(index, new_seg)
        self.alignment = self.alignment.map(lambda i, j: (i-1, j) if i > index else (i, j))
    
    def flatten_segments(self) -> None:
        # TODO
        pass
    
    def __str__(self) -> str:
        return f"AlignedSegments({self.src}, {self.tgt}, {self.alignment})"
    
    def __add__(self, other: Self):
        # TODO (low priority): (self.src + other.src) should return SegmentedText right away
        src = SegmentedText(self.src + other.src)
        tgt = SegmentedText(self.tgt + other.tgt)
        alignment = self.alignment + other.alignment.map(lambda i, j: (i+len(self.src), j+len(self.tgt)))
        return AlignedSegments(src, tgt, alignment)

    def debug_print(self) -> None:
        self.src.debug_print()
        self.tgt.debug_print()
        print(self.alignment)

class TagReinserter:
    @staticmethod
    def reinsert_segments(aligned_segments: AlignedSegments) -> AlignedSegments:
        """
        Reinserts all segments from `src` that are not aligned to any segment in `tgt`.
        """
        # simplify source segments - join the adjacent reinserted segments together
        def _to_be_reinserted(i: int) -> bool:
            return aligned_segments.alignment.get_src(i) == []
        i = 0
        while i < len(aligned_segments.src) - 1:
            # fst = aligned_segments.src[i]
            # snd = aligned_segments.src[i+1]
            if _to_be_reinserted(i) and _to_be_reinserted(i+1):
                aligned_segments.join_adjacent_segments(i)
            else:
                i += 1

        for i, seg in enumerate(aligned_segments.src):
            if aligned_segments.alignment.get_src(i) != []:
                # this segment from src is aligned to a segment in tgt
                # therefore it does not need to be reinserted (it's already in tgt)
                continue
            else:
                # this segment from src is not aligned to a segment in tgt
                # therefore it needs to be reinserted
                # print(i, seg, i+1, "->", aligned_segments.alignment.get_src(i+1))
                # print(i, seg, i-1, "->", aligned_segments.alignment.get_src(i-1))
                if aligned_segments.alignment.get_src(i+1) != []:
                    # the next segment from src is aligned to a segment in tgt
                    # we insert the current segment before the next segment
                    index = min(aligned_segments.alignment.get_src(i+1))
                    aligned_segments.insert_segment(index, seg)
                elif aligned_segments.alignment.get_src(i-1) != []:
                    # the previous segment from src is aligned to a segment in tgt
                    # we insert the current segment after the previous segment
                    index = max(aligned_segments.alignment.get_src(i-1)) + 1
                    aligned_segments.insert_segment(index, seg)
                else:
                    # no segment in tgt is aligned to this segment from src
                    # we insert the current segment at the end
                    logger.warn("no segment in tgt is aligned to this segment from src")
                    aligned_segments.insert_segment(len(aligned_segments.tgt), seg)
                    # TODO: find the best place to insert the segment by counting 
                    #       the number of aligned segments before and after the reinserted segments

        aligned_segments.flatten_segments()

        return aligned_segments

    @staticmethod
    def reinsert_tags(aligned_segments: AlignedSegments) -> AlignedSegments:
        """
        We have two sequences of segments.
        The segments are aligned - some segments in `src` are aligned to some other segments in `tgt`.
            - one segment in `src` may be aligned to multiple segments in `tgt` and vice versa
        Inside the `src` segments, there may be tags.
        A (B C) D ((E) F) G
        x x A x C x D x x E

        Segments that are not aligned are free to be tagged or untagged.
        Segments in `src` that are tagged should be tagged in `tgt`.
        """
        class TaggedSegment(Segment):
            def __init__(self, string: str, type: SegmentType, tags: Set[int]):
                super().__init__(string, type)
                self.tags = tags
            @classmethod
            def from_segment(cls, segment: Segment):
                return cls(segment.string, segment.type, set())
            def __str__(self) -> str:
                return f"<TaggedSegment({repr(self.string)}, {self.type}, {self.tags})>"

        class TagSegment(Segment):
            def __init__(self, string: str, type: SegmentType, tag_id: int, opening_tag: bool):
                super().__init__(string, type)
                self.tag_id = tag_id
                self.opening_tag = opening_tag
            @classmethod
            def from_string(cls, string: str):
                if string == '</g>':
                    return cls(string, SegmentType.TAG, -1, False)
                elif string.startswith('<g'):
                    match = re.search(r'id=("|\')(\d+)("|\')', string) # warning: also matches wrongly id="1' but that is not a problem
                    if match:
                        tag_id = int(match.group(2))
                        return cls(string, SegmentType.TAG, tag_id, True)
                    else:
                        raise ValueError("tag id attribute not found in string: " + string)
                else:
                    raise ValueError(f"Not a TagSegment string: {string}")

        tagged_src: List[Segment] = []
        for seg in aligned_segments.src:
            if seg.type == SegmentType.TAG:
                tagged_src.append(TagSegment.from_string(seg.string))
            else:
                tagged_src.append(TaggedSegment.from_segment(seg))
        tag_stack: List[int] = []
        unique_tags_begins: Dict[int, Segment] = dict()
        unique_tags_ends: Dict[int, Segment] = dict()

        for orig_seg, seg in zip(aligned_segments.src, tagged_src):
            if isinstance(seg, TagSegment):
                if seg.opening_tag:
                    tag_stack.append(seg.tag_id)
                    unique_tags_begins[seg.tag_id] = orig_seg
                else:
                    tag_id = tag_stack.pop()
                    unique_tags_ends[tag_id] = orig_seg
            elif isinstance(seg, TaggedSegment):
                seg.tags.update(tag_stack)

        if tag_stack:
            raise ValueError(f"tag_stack is not empty: {tag_stack}")

        # print(unique_tags_begins)
        # print(unique_tags_ends)
        
        tagged_tgt: List[TaggedSegment] = [TaggedSegment.from_segment(seg) for seg in aligned_segments.tgt]

        for i, seg in enumerate(tagged_src):
            if isinstance(seg, TaggedSegment) and len(seg.tags):
                tgt_segments = aligned_segments.alignment.get_src(i)
                if tgt_segments != []:
                    for tgt_segment in tgt_segments:
                        tagged_tgt[tgt_segment].tags.update(seg.tags)

        for tag in unique_tags_begins.keys():
            tagged_indices = [i for i, seg in enumerate(tagged_tgt) if tag in seg.tags]
            # print(tag, tagged_indices)
            min_index = min(tagged_indices)
            max_index = max(tagged_indices)
            tagged_tgt.insert(min_index, TaggedSegment("<g>", SegmentType.TAG, set()))
            tagged_tgt.insert(max_index+2, TaggedSegment("</g>", SegmentType.TAG, set()))

            aligned_segments.insert_segment(min_index, unique_tags_begins[tag])
            aligned_segments.insert_segment(max_index+2, unique_tags_ends[tag])

        # for i, seg in enumerate(tagged_tgt):
        #     print(i, seg)

        # print(str(tagged_tgt))

        return aligned_segments

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
        src = SegmentedText(filter(lambda x: x.type != SegmentType.WHITESPACE, src))
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

class MarkupTranslator:
    def __init__(self, translator: Translator, aligner: Aligner, tokenizer: MosesTokenizer):
        self.translator = translator
        self.aligner = aligner
        self.tokenizer = tokenizer

    def align_segments(self, src: SegmentedText, tgt: SegmentedText) -> AlignedSegments:
        src_sentences = list(src.split_sentences())
        tgt_sentences = list(tgt.split_sentences())

        src_batch = [[str(t) for t in sent] for sent in src_sentences]
        tgt_batch = [[str(t) for t in sent] for sent in tgt_sentences]
        
        assert len(src_batch) == len(tgt_batch)
        
        alignments = self.aligner.align(src_batch, tgt_batch)

        aligned_segments = AlignedSegments()
        first = True
        for src_sentence_segments, tgt_sentence_segments, alignment in zip(src_sentences, tgt_sentences, alignments):
            if not first:
                # add separator after each sentence
                aligned_segments += AlignedSegments(SegmentedText([SentenceSeparator()]), SegmentedText([SentenceSeparator()]), Alignment([(0,0)]))
            aligned_segments += AlignedSegments(src_sentence_segments, tgt_sentence_segments, Alignment(alignment))
            first = False

        return aligned_segments

    def translate(self, src: str) -> str:
        src_segments = SegmentedText.from_string(src)
        src_segments = src_segments.tokenize(self.tokenizer)

        # src_lines = src.splitlines()
        print(":: src segments before translation:")
        src_segments.debug_print()

        src_for_translation, src_to_src_for_translation_alignment = src_segments.translation_view()
        # src_to_src_for_translation = AlignedSegments(src, src_for_translation, src_to_src_for_translation_alignment)
        print()
        print(":: translation view on src segments:")
        src_for_translation.debug_print()
        print(src_to_src_for_translation_alignment)


        print()
        print("TRANSLATION")
        src_sentences, tgt_sentences = self.translator.translate(str(src_for_translation))
        print()
        print(":: src sentences")
        src_sentences_segments = SegmentedText.from_sentences(src_sentences)
        src_sentences_segments = src_sentences_segments.tokenize(self.tokenizer)
        src_sentences_segments.debug_print()
        src_for_alignment,  = src_sentences_segments.alignment_view()

        src_for_alignment.debug_print()
        # print(src_to_src_for_alignment_alignment)

        print(":: tgt sentences")
        tgt_segments = SegmentedText.from_sentences(tgt_sentences)
        tgt_segments = tgt_segments.tokenize(self.tokenizer)
        tgt_segments.debug_print()

        tgt_for_alignment, _ = tgt_segments.alignment_view()
        tgt_for_alignment.debug_print()


        print("ALIGNMENT")
        src_to_tgt_alignment = self.align_segments(src_for_alignment, tgt_for_alignment)
        src_to_tgt_alignment.debug_print()

        print(":: src to tgt alignment")

        # print([self.tokenizer(sent) for sent in src_sentences])

        return "\n".join(tgt_sentences)

class MarkupTranslatorTester(unittest.TestCase):
    def setUp(self):
        self.markup_translator = MarkupTranslator(translator=DummyTranslator(), aligner=DummyAligner(), tokenizer=MosesTokenizer())

    def test_nomarkup(self):
        src = "Ahoj světe! Jak se máš?\n\nMám se fajn.\n\n"
        tgt_expected = "Hello world! How are you?\n\nI am fine.\n\n"
        
        tgt = self.markup_translator.translate(src)
        # self.assertEqual(tgt, tgt_expected)

    def test_simple(self):
        src = "Ahoj <g id='1'>světe</g>!<ex id='2'/> Jak se máš?\n\n<bx id='3'/>Mám se fajn.\n\n"
        tgt_expected = "Hello <g id='1'>world</g>!<ex id='2'/> How are you?\n\n<bx id='3'/>I am fine.\n\n"
        tgt = self.markup_translator.translate(src)
        # self.assertEqual(tgt, tgt_expected)


if __name__ == "__main__":
    unittest.main()
