from collections import defaultdict
from functools import cached_property
from typing import Callable, Dict, List, Tuple
import unittest
import re
from enum import Enum
# from mosestokenizer import MosesTokenizer

from termcolor import colored

import logging

logging.basicConfig(level=logging.DEBUG)

class Translator:
    def translate(self, src: str) -> str:
        raise NotImplementedError

class Aligner:
    pass


class SegmentType(Enum):
    TEXT = 0
    TAG = 1
    WHITESPACE = 2

class Segment(object):
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
        return colored(string, "black", "on_white")

    def __len__(self) -> int:
        return len(self.string)
    
    def __str__(self) -> str:
        return self.debug_color(self.string)

class JoinedSegment(Segment):
    def __init__(self, segments: List[Segment]):
        self.segments = segments
    
    def __len__(self) -> int:
        return sum(len(s) for s in self.segments)
    
    def debug_color(self, string: str) -> str:
        return colored(string, "black", "on_yellow", attrs=["underline"])
    
    def __str__(self) -> str:
        return ''.join(colored(str(x), attrs=["underline"]) for x in self.segments)

class SegmentedText(list[Segment]):
    """
    A text that has been split into segments of text, tags and whitespace.
    The main assumption is that joining the segments will yield the original text.
    """
    tag_pattern = r'<\/?(g|x|bx|ex|lb|mrk).*?>'
    tag_regex = re.compile(tag_pattern)
    whitespace_regex = re.compile(r'\s+')
    segments_regex = re.compile(r'('+tag_pattern+r'|\s+|[^<\s]+|[^>\s]+)')

    def __init__(self, iterable: List[Segment]):
        super().__init__(iterable)

    @classmethod
    def from_string(cls, string: str):
        segment_strings = cls.segments_regex.findall(string)
        segment_strings = map(lambda x: x[0], segment_strings)
        return cls([Segment.from_string(s) for s in segment_strings])
    
    @classmethod
    def from_string_list(cls, strings: List[str]):
        return cls([Segment.from_string(s) for s in strings])
    
    def __str__(self) -> str:
        return ''.join(str(x) for x in self)

    def translation_view(self):
        return ''.join(s.string for s in self if s.type == SegmentType.TEXT)
    
    def alignment_view(self):
        pass

class Alignment:
    def __init__(self, mapping: List[Tuple[int, int]]):
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

class AlignedSegments(object):
    def __init__(self, src_segments: SegmentedText, tgt_segments: SegmentedText, alignment: Alignment):
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
        output = str(self.src) + "\n"
        output += "".join([seg.debug_color(str(i)) + " "*(len(seg)-1) for i, seg in enumerate(self.src)])
        output += "\n"
        output += "\n"
        output += str(self.tgt) + "\n"
        output += "".join([seg.debug_color(str(i)) + " "*(len(seg)-1) for i, seg in enumerate(self.tgt)])

        output += "\n"
        output += str(self.alignment)
        return output
    
class TagType(Enum):
    OPEN = 0
    CLOSE = 1
    SELFCLOSE = 2

class Tag:
    # TODO
    def __init__(self, tagname: str, id: int, type: TagType):
        self.id = id
        self.tagname = tagname
        self.type = type

    @classmethod
    def from_string(cls, string: str):
        if string == '</g>':
            return cls('g', -1, TagType.CLOSE)
        # <g id="1">
        match = re.search(r'<(g|x|bx|ex|lb|mrk) id="(\d+)"(/)?>', string)
        if not match:
            raise ValueError
        return cls(match.group(1), int(match.group(2)), TagType.OPEN)

    def __str__(self) -> str:
        return f'<{self.tagname} id="{self.id}">'
    

class TaggedSegment(Segment):
    def __init__(self, string: str, type: SegmentType, tags: List[int]):
        super().__init__(string, type)
        self.tags = tags

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
        print(aligned_segments)
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
                    logging.debug("no segment in tgt is aligned to this segment from src")
                    aligned_segments.insert_segment(len(aligned_segments.tgt.segments), seg)
                    # TODO: find the best place to insert the segment by counting 
                    #       the number of aligned segments before and after the reinserted segments

        aligned_segments.flatten_segments()

        return aligned_segments

    @staticmethod
    def reinsert_tags(aligned_segments: AlignedSegments) -> SegmentedText:
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
        # gathered_tags = []
        raise NotImplementedError

        # active_tags = []
        # for seg in aligned_segments.src_segments.segments:
        #     if seg.type == SegmentType.TAG:

        #         active_tags.append(seg.tags[0])
        #     else:
        #         if active_tags:
        #             gathered_tags.append(active_tags)
        #             active_tags = []
        # for 

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
            "<x id='1'>","<x id='2'>","Můj"," ","<x id='3'>","přítel","</x>","</x>",","," ",
            "který"," ","pracuje"," ","<x id='4'>","v"," ","bankovním"," ","sektoru","</x>",","," ",
            "<x id='5'>","se"," ","v"," ","říjnu"," ","žení","</x>",".","</x>"
        ])
        print(src)
        src = SegmentedText(filter(lambda x: x.type == SegmentType.WHITESPACE, src))
        tgt = SegmentedText.from_string_list(["A"," ","friend"," ","of"," ","mine"," ","who"," ","works"," ","in"," ","banking"," ","is"," ","getting"," ","married"," ","in"," ","October","."])
        alignment = Alignment([(0, 0), (1, 2), (5, 4), (7, 5)])

class TranslateMarkupTester(unittest.TestCase):
    pass
    # def test_nomarkup(self):

    # def test_simple(self):
    #     src = "<i>This</i> is a sample text with markup."
    #     tgt = "Toto je ukázkový text s markupem."

    #     translate_markup()

if __name__ == "__main__":
    unittest.main()
