from collections import defaultdict
from functools import cached_property
from typing import Callable, Dict, List, Tuple
import unittest
import re
from enum import Enum
from mosestokenizer import MosesTokenizer

from termcolor import colored

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
    
    def __str__(self) -> str:
        # string = self.string.replace(" ", "_")
        string = self.string
        if self.type == SegmentType.TAG:
            return colored(string, "black", "on_cyan", attrs=["bold"])
        if self.type == SegmentType.WHITESPACE:
            return colored(string, "white", "on_blue")
        return colored(string, "black", "on_white")

class SegmentedText(object):
    """
    A text that has been split into segments of text, tags and whitespace.
    The main assumption is that joining the segments will yield the original text.
    """
    tag_pattern = r'<\/?(g|x|bx|ex|lb|mrk).*?>'
    tag_regex = re.compile(tag_pattern)
    whitespace_regex = re.compile(r'\s+')
    segments_regex = re.compile(r'('+tag_pattern+r'|\s+|[^<\s]+|[^>\s]+)')

    def __init__(self, segments: List[Segment]):
        self.segments = segments

    @classmethod
    def from_string(cls, string: str):
        segment_strings = cls.segments_regex.findall(string)
        segment_strings = map(lambda x: x[0], segment_strings)
        return cls([Segment.from_string(s) for s in segment_strings])
    
    def __str__(self) -> str:
        return ''.join(str(x) for x in self.segments)

    def translation_view(self):
        return ''.join(s.string for s in self.segments if s.type == SegmentType.TEXT)
    
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
        self.mapping = list(map(lambda x: f(*x), self.mapping))

class AlignedSegments(object):
    def __init__(self, src_segments: SegmentedText, tgt_segments: SegmentedText, alignment: Alignment):
        self.src = src_segments
        self.tgt = tgt_segments
        self.alignment = alignment

    def insert_segment(self, index: int, segment: Segment) -> None:
        self.tgt.segments.insert(index, segment)
        self.alignment.map(lambda i, j: (i, j+1) if j >= index else (i, j))
    
class TagType(Enum):
    OPEN = 0
    CLOSE = 1
    SELFCLOSE = 2

class Tag:
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
        return cls(match.group(1), int(match.group(2)), match.group(3) != "/")

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
        for i, seg in enumerate(aligned_segments.src.segments):
            if aligned_segments.alignment.get_src(i) != []:
                # this segment from src is aligned to a segment in tgt
                # therefore it does not need to be reinserted (it's already in tgt)
                continue
            else:
                # this segment from src is not aligned to a segment in tgt
                # therefore it needs to be reinserted
                if aligned_segments.alignment.get_src(i+1) != []:
                    # the next segment from src is aligned to a segment in tgt
                    # we insert the current segment before the next segment
                    index = min(aligned_segments.alignment.get_src(i+1))
                    aligned_segments.insert_segment(index, seg)
                elif aligned_segments.alignment.get_src(i-1) != []:
                    # the previous segment from src is aligned to a segment in tgt
                    # we insert the current segment after the previous segment
                    index = max(aligned_segments.alignment.get_src(i-1))
                    aligned_segments.insert_segment(index, seg)
                else:
                    # no segment in tgt is aligned to this segment from src
                    # we insert the current segment at the end
                    aligned_segments.insert_segment(len(aligned_segments.tgt.segments), seg)
                    # TODO: find the best place to insert the segment by counting 
                    #       the number of aligned segments before and after the reinserted segments
        
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
    def test_reinsert_segments(self):
        src = SegmentedText.from_string("This is a <g id='1'>test</g>.")
        tgt = SegmentedText.from_string("Toto je test.")
        print(tgt)
        # alignment = Alignment([(0, 0), (1, 1), (2, 2), (3, 3), (4, 4), (5, 5), (6, 6)])


class TranslateMarkupTester(unittest.TestCase):
    pass
    # def test_nomarkup(self):

    # def test_simple(self):
    #     src = "<i>This</i> is a sample text with markup."
    #     tgt = "Toto je ukázkový text s markupem."

    #     translate_markup()

if __name__ == "__main__":
    unittest.main()
