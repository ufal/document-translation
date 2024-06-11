from bisect import bisect_left
from collections import defaultdict
from typing import Callable, Dict, Iterable, List, Optional, Self, Set, Tuple
import re
import logging
from time import perf_counter

from termcolor import colored

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class Translator:
    def translate(self, input_text: str) -> Tuple[List[str], List[str]]:
        raise NotImplementedError

class Aligner:
    def align(self, src_batch: List[List[str]], tgt_batch: List[List[str]]) -> List[List[Tuple[int, int]]]:
        raise NotImplementedError

class Tokenizer:
    def tokenize(self, string: str) -> List[str]:
        raise NotImplementedError

class Segment(str):
    def __new__(cls, string: str) -> Self:
        instance = super().__new__(cls, string)
        return instance
    def debug_color(self, string: str) -> str:
        raise NotImplementedError
    def debug_str(self) -> str:
        return self.debug_color(self)
    def debug_len(self) -> int:
        return len(self)

class TextSegment(Segment):
    def debug_color(self, string: str) -> str:
        return colored(string, "black", "on_white")

class TagSegment(Segment):
    def __init__(self, string: str):
        if string.startswith("</"):
            match = re.search(r'</(\w+)>', string)
            if match:
                self.tag = match.group(1)
            else:
                raise ValueError("tag name not found in string: " + string)
        else:
            match_tag = re.search(r'<(\w+)', string)

            if match_tag:
                self.tag = match_tag.group(1)
            else:
                raise ValueError("tag name not found in string: " + string)
    def debug_color(self, string: str) -> str:
        return colored(string, "black", "on_magenta", attrs=["bold"])

class PairedTagSegment(TagSegment):
    def __init__(self, string: str) -> None:
        super().__init__(string)
        if string == '</g>':
            self.opening_tag = False
        elif string.startswith('<g'):
            self.opening_tag = True
        else:
            raise ValueError(f"Not a PairedTagSegment string: {string}")
    def debug_color(self, string: str) -> str:
        return colored(string, "black", "on_cyan", attrs=["bold"])

class WhitespaceSegment(Segment):
    def debug_color(self, string: str) -> str:
        return colored(string, "white", "on_blue")
    def debug_str(self) -> str:
        return self.debug_color(repr(self))
    def debug_len(self) -> int:
        return len(repr(self))

class SegmentFactory:
    paired_tag_pattern = r'</?g.*?>'
    paired_tag_regex = re.compile(paired_tag_pattern)
    tag_pattern = r'</?(x|bx|ex|lb|mrk).*?>'
    tag_regex = re.compile(tag_pattern)
    whitespace_regex = re.compile(r'\s+')
    @classmethod
    def from_string(cls, string: str) -> Segment:
        if cls.paired_tag_regex.match(string):
            return PairedTagSegment(string)
        elif cls.tag_regex.match(string):
            return TagSegment(string)
        elif cls.whitespace_regex.match(string):
            return WhitespaceSegment(string)
        else:
            return TextSegment(string)

class SentenceSeparator(Segment):
    def __new__(cls):
        instance = super().__new__(cls, "")
        return instance
    def debug_color(self, string: str) -> str:
        return colored(string, "black", "on_red")
    def debug_str(self):
        return self.debug_color("||")
    def debug_len(self) -> int:
        return 2

class JoinedSegment(Segment):
    def __new__(cls, segments: List[Segment]):
        instance = super().__new__(cls, ''.join(str(x) for x in segments))
        return instance
    def __init__(self, segments: List[Segment]):
        self.segments = segments
    def debug_color(self, string: str) -> str:
        return colored(string, "black", "on_yellow", attrs=["underline"])
    def debug_str(self) -> str:
        return ''.join(colored(x.debug_str(), attrs=["underline"]) for x in self.segments)
    def debug_len(self) -> int:
        return sum(x.debug_len() for x in self.segments)
class SegmentedText(list[Segment]):
    """
    A text that has been split into segments of text, tags and whitespace.
    The main assumption is that joining the segments will yield the original text.
    """
    segments_regex = re.compile(r'(</?(g|x|bx|ex|lb|mrk).*?>|\n|[^\S\n]+|[^<\s]+|[^>\s]+)')

    def __init__(self, iterable: Optional[Iterable[Segment]] = None):
        if iterable is None:
            iterable = []
        super().__init__(iterable)

    @classmethod
    def from_string(cls, string: str):
        segment_strings = cls.segments_regex.findall(string)
        segment_strings = list(map(lambda x: x[0], segment_strings))
        assert "".join(segment_strings) == string
        return cls(SegmentFactory.from_string(s) for s in segment_strings)
    
    @classmethod
    def from_string_list(cls, strings: List[str]):
        return cls(SegmentFactory.from_string(s) for s in strings)
    
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
            if isinstance(seg, TextSegment):
                tokens = tokenizer.tokenize(str(seg))
                if len(tokens) > 1:
                    for tok in tokens:
                        new_segments.append(TextSegment(tok))
                else:
                    new_segments.append(seg)
            else:
                new_segments.append(seg)
        return SegmentedText(new_segments)
    
    def __str__(self) -> str:
        return ''.join(x for x in self)

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

    def translator_view(self):
        """
        Returns a new SegmentedText that is ready for the translator.
        Moreover, we preserve the alignment between the original SegmentedText and the processed SegmentedText for the translator.
        
        The processing steps are following:
        - replace any whitespace sequence with a single space (but keep newlines)
        - remove any tags
        - if the tag removed was <x> or <lb>, insert a space instead of the tag
        """
        src_for_translator = SegmentedText()
        alignment = Alignment()
        for i, s in enumerate(self):
            if isinstance(s, TagSegment) and (s.tag == "x" or s.tag == "lb"):
                # TODO (low priority): check if there already is a space and do not add it if it is there
                # replace self-closing tags and linebreak tags with spaces
                src_for_translator.append(WhitespaceSegment(" "))
            elif isinstance(s, TagSegment):
                continue
            elif isinstance(s, WhitespaceSegment):
                if s == "\n" or s == " ":
                    src_for_translator.append(s)
                else:
                    # normalize whitespace other than space and newline
                    src_for_translator.append(WhitespaceSegment(" "))
                alignment.add((i, len(src_for_translator) - 1))
            else:
                src_for_translator.append(s)
                alignment.add((i, len(src_for_translator) - 1))
        return src_for_translator, AlignedSegments(self, src_for_translator, alignment)
    
    def aligner_view(self):
        """
        Returns a new SegmentedText that is ready for the word aligner.
        Preserves the alignment between the original SegmentedText and the processed SegmentedText.

        The details of the processing steps are:
        - remove anything other than words (TextSegments), sentence separators (SentenceSeparator) and newlines
        - the sentence separators are preserved because the aligner works on sentence level rather than line level.
        - all whitespace except newline is removed because the aligner does not use it.
        """
        src_for_aligner = SegmentedText()
        alignment = Alignment()
        for i, s in enumerate(self):
            if isinstance(s, TextSegment) or isinstance(s, SentenceSeparator) or s == "\n":
                src_for_aligner.append(s)
                alignment.add((i, len(src_for_aligner) - 1))
        return src_for_aligner, AlignedSegments(self, src_for_aligner, alignment)

    def split_sentences(self):
        i = 0
        for j, seg in enumerate(self):
            if isinstance(seg, SentenceSeparator):
                # TODO (low priority): why self[i:j] does not return SegmentedText right away?
                yield SegmentedText(self[i:j])
                i = j + 1
        yield SegmentedText(self[i:])


class Alignment:
    # TODO (low priority): instead of Set[Tuple[int, int]] we could use something like Dict[Segment, List[Segment]]
    #                      that way the alignment would be invariant to the order of the segments
    def __init__(self, mapping: Optional[Iterable[Tuple[int, int]]] = None):
        if mapping is None:
            mapping = set()
        self.mapping = set(mapping)
        self._src_to_tgt = None
    
    @property
    def src_to_tgt(self) -> Dict[int, List[int]]:
        if self._src_to_tgt is None:
            src_to_tgt: Dict[int, List[int]] = defaultdict(list)
            for i, j in self.mapping:
                src_to_tgt[i].append(j)
            self._src_to_tgt = src_to_tgt
        return self._src_to_tgt
    
    def is_empty(self) -> bool:
        return len(self.mapping) == 0
    
    def add(self, pair: Tuple[int, int]) -> None:
        self._src_to_tgt = None
        self.mapping.add(pair)

    def get_src(self, i: int) -> List[int]:
        return self.src_to_tgt.get(i, [])

    def map(self, f: Callable[[int, int], Tuple[int, int]]):
        return Alignment(map(lambda x: f(*x), self.mapping))

    def filter(self, f: Callable[[int, int], bool]):
        return Alignment(filter(lambda x: f(*x), self.mapping))
    
    def __str__(self) -> str:
        return f"Alignment({sorted(self.mapping)})"
    
    def __add__(self, other: Self):
        return Alignment(self.mapping.union(other.mapping))
    
    def compose(self, other: Self):
        new_alignment: Set[Tuple[int, int]] = set()
        for (i, js) in self.src_to_tgt.items():
            for j in js:
                for k in other.src_to_tgt[j]:
                    new_alignment.add((i, k))
        return Alignment(new_alignment)


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
    
    def remove_segment(self, index: int) -> None:
        self.tgt.pop(index)
        self.alignment = self.alignment.filter(lambda i, j: j != index)
        self.alignment = self.alignment.map(lambda i, j: (i, j-1) if j > index else (i, j))

    def merge_segment_span(self, start: int, end: int) -> None:
        """
        Joins the segments at `index` and `index+1` and inserts the result at `index`.
        If the segment at `index` is already a JoinedSegment, the segments are appended to it.
        """
        assert start < end
        length = end - start
        new_seg = JoinedSegment(self.src[start:end])
        self.src = self.src[:start] + [new_seg] + self.src[end:]
        # TODO (low priority) map the alignments to the joined segment
        # We do not need it because we only join segments that have no alignment
        #  ... self.alignment = self.alignment.map(lambda i, j: (start, j) if i > end else (i, j)) ...
        self.alignment = self.alignment.map(lambda i, j: (i-length+1, j) if i >= end else (i, j))
    
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
    
    def recover_alignment(self) -> None:
        # greedily recover the alignment based on segment equality
        # assume that tgt contains extra elements and src == (tgt - extra)
        assert self.alignment.is_empty()
        src_iter = enumerate(self.src)
        for i, seg_tgt in enumerate(self.tgt):
            # skip sentence separators
            if isinstance(seg_tgt, SentenceSeparator):
                continue
            while True:
                j, seg_src = next(src_iter)
                if seg_src == seg_tgt:
                    self.alignment.add((j, i))
                    break
                if seg_tgt.startswith(seg_src):
                    self.alignment.add((j, i))
                    seg_tgt = seg_tgt[len(seg_src):]
                # if not found immediately do not continue 
                # searching for whitespace, it might be missing
                # if isinstance(seg_tgt, WhitespaceSegment):
                #     skipped_last_tgt = True
                #     break

    def recover_newline_alignment(self) -> None:
        src_newlines = [i for i, seg in enumerate(self.src) if seg == "\n"]
        tgt_newlines = [i for i, seg in enumerate(self.tgt) if seg == "\n"]
        assert len(src_newlines) == len(tgt_newlines)
        self.alignment.mapping.update(zip(src_newlines, tgt_newlines))

    def infer_whitespace_alignment(self) -> None:
        """
        find whitespace alignments that do not "cross" any existing alignments
        for example:
        we have alignments (1,2), (3, 6)
        can we add (2, 3)? yes because (2, 3) fits in between (1, 2) and (3, 6)
        can we add (2, 0)? No, because that would "cross" the alignment (1, 2)
        """
        unaligned_tgt_whitespace: List[int] = []
        aligned_tgts = set([j for _, j in self.alignment.mapping])
        for j, seg_tgt in enumerate(self.tgt):
            if isinstance(seg_tgt, WhitespaceSegment) and j not in aligned_tgts:
                unaligned_tgt_whitespace.append(j)
        
        rightmost_alignment_by_src = [-1]*len(self.src)
        leftmost_alignment_by_src = [len(self.tgt)]*len(self.src)
        for i, j in self.alignment.mapping:
            # store minimum target index for each source
            if rightmost_alignment_by_src[i] < j:
                rightmost_alignment_by_src[i] = j
            # store maximum target index for each source
            if leftmost_alignment_by_src[i] > j:
                leftmost_alignment_by_src[i] = j
        # fill missing values with the nearest previous alignment
        current = -1
        for i, j in enumerate(rightmost_alignment_by_src):
            if j == -1:
                rightmost_alignment_by_src[i] = current
            else:
                current = j
        # fill missing values with the nearset next alignment
        current = len(self.tgt)
        for i, j in reversed(list(enumerate(leftmost_alignment_by_src))):
            if j == len(self.tgt):
                leftmost_alignment_by_src[i] = current
            else:
                current = j

        aligned_srcs = set([i for i, _ in self.alignment.mapping])
        for i, seg in enumerate(self.src):
            if isinstance(seg, WhitespaceSegment) and not i in aligned_srcs:
                # segment is whitespace and is not aligned to anything in target
                # find the first whitespace in target that we can align this whitespace 
                # without crossing any existing alignments
                for j in range(rightmost_alignment_by_src[i]+1, leftmost_alignment_by_src[i]):
                    # check if this whitespace can be aligned
                    if j in unaligned_tgt_whitespace:
                        self.alignment.add((i, j))
                        unaligned_tgt_whitespace.remove(j)
                        break

    def swap_sides(self) -> "AlignedSegments":
        # TODO (low priority): alignment should be more of a black box
        alignment = self.alignment.map(lambda i, j: (j, i))
        return AlignedSegments(self.tgt, self.src, alignment)
    
    def compose(self, other: Self) -> "AlignedSegments":
        assert self.tgt == other.src
        new_alignment = self.alignment.compose(other.alignment)
        return AlignedSegments(self.src, other.tgt, new_alignment)


class TagReinserter:
    @staticmethod
    def reinsert_whitespace(aligned_segments: AlignedSegments) -> AlignedSegments:
        """
        Reinserts whitespace segments from `src` that are aligned to segment in `tgt` 
        but the whitespace has been normalized as a single space.
        """
        for i, seg in enumerate(aligned_segments.src):
            tgt_index = aligned_segments.alignment.get_src(i)
            if isinstance(seg, WhitespaceSegment) and len(tgt_index) == 1:
                # replace the segment 
                aligned_segments.tgt[tgt_index[0]] = seg
        return aligned_segments

    @staticmethod
    def reinsert_segments(aligned_segments: AlignedSegments) -> AlignedSegments:
        """
        Reinserts all segments from `src` that are not aligned to any segment in `tgt`.
        """
        # simplify source segments - join the adjacent reinserted segments together
        def _to_be_reinserted(i: int) -> bool:
            segment = aligned_segments.src[i]
            # joined segment is a helper method for reinsert_segment and we want to reinsert it always
            if isinstance(segment, JoinedSegment):
                return True
            # if the segment from `src`` is aligned already with something in `tgt``, it should not be reinserted (as it is already there)
            if aligned_segments.alignment.get_src(i) != []:
                return False
            if isinstance(segment, PairedTagSegment):
                logger.warning(f"Found unaligned PairedTagSegment {segment} on index {i}!")
            # reinsert unaligned tags
            if isinstance(segment, TagSegment):
                return True
            # reinsert whitespace if it is not a simple space and it is not only newlines
            if isinstance(segment, WhitespaceSegment) and segment != " " and segment != "\n":
                return True
            return False 
        i = 0
        while i < len(aligned_segments.src) - 1:
            if _to_be_reinserted(i):
                j = i+1
                while j < len(aligned_segments.src) and _to_be_reinserted(j):
                    j += 1
                if j > i + 1:
                    aligned_segments.merge_segment_span(i, j)
                i = j
            else:
                i += 1

        for i, seg in enumerate(aligned_segments.src):
            if not _to_be_reinserted(i):
                # this segment from src is aligned to a segment in tgt
                # therefore it does not need to be reinserted (it's already in tgt)
                continue
            else:
                # TODO (!): all this might be better implemented as finding
                # a non-crossing alignment for the segment

                # this segment from src is not aligned to a segment in tgt
                # therefore it needs to be reinserted
                if aligned_segments.alignment.get_src(i+1) != []:
                    # the next segment from src is aligned to a segment in tgt
                    # we insert the current segment before the next segment
                    index = min(aligned_segments.alignment.get_src(i+1))
                    aligned_segments.insert_segment(index, seg)
                    aligned_segments.alignment.add((i, index))
                elif aligned_segments.alignment.get_src(i-1) != []:
                    # the previous segment from src is aligned to a segment in tgt
                    # we insert the current segment after the previous segment
                    index = max(aligned_segments.alignment.get_src(i-1)) + 1
                    aligned_segments.insert_segment(index, seg)
                    aligned_segments.alignment.add((i, index))
                else:
                    # no segment in tgt is aligned to this segment from src
                    # we insert the current segment at the end
                    logger.warning(f"no segment in tgt is aligned to this segment {i} {seg} from src")
                    # TODO: find the best place to insert the segment by counting 
                    #       the number of aligned segments before and after the reinserted segments
                    tgt_indices_left: Set[int] = set()
                    tgt_indices_right: Set[int] = set()
                    for j in range(0, i):
                        tgt_indices_left.update(aligned_segments.alignment.get_src(j))
                    for j in range(i+1, len(aligned_segments.src)):
                        tgt_indices_right.update(aligned_segments.alignment.get_src(j))
                    print(tgt_indices_left, tgt_indices_right)
                    max_tgt_indices_left = max(tgt_indices_left) + 1 if tgt_indices_left else 0
                    min_tgt_indices_right = min(tgt_indices_right) if tgt_indices_right else len(aligned_segments.tgt)
                    if max_tgt_indices_left <= min_tgt_indices_right:
                        # simple case
                        index = max_tgt_indices_left
                        aligned_segments.insert_segment(index, seg)
                        aligned_segments.alignment.add((i, index))
                    else:
                        logger.error("DID NOT FIND PLACE TO INSERT SEGMENT")
                        # TODO: implement a more sophisticated way to insert the segment
                        index = max_tgt_indices_left
                        aligned_segments.insert_segment(index, seg)
                        aligned_segments.alignment.add((i, index))


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
        tag_stack: List[int] = []
        unique_opening_tags: Dict[int, Tuple[int, PairedTagSegment]] = dict()
        unique_closing_tags: Dict[int, Tuple[int, PairedTagSegment]] = dict()
        tag_to_tgt_indices: defaultdict[int, Set[int]] = defaultdict(set)

        def _find_line_boundaries(segments: SegmentedText):
            line_boundaries = [i for i, seg in enumerate(segments) if seg == "\n"]
            line_boundaries = [-1] + line_boundaries + [len(segments)]
            return line_boundaries
        line_boundaries = _find_line_boundaries(aligned_segments.src)
        tgt_line_boundaries = _find_line_boundaries(aligned_segments.tgt)
        assert len(line_boundaries) == len(tgt_line_boundaries)

        for src_index, seg in enumerate(aligned_segments.src):
            if seg == "\n" and tag_stack:
                line = bisect_left(line_boundaries, src_index)
                raise ValueError(f"Paired tag is not closed in the source text on line {line}.")
            if isinstance(seg, PairedTagSegment):
                if seg.opening_tag:
                    tag_stack.append(src_index)
                    unique_opening_tags[src_index] = (src_index, seg)
                else:
                    tag_src_index = tag_stack.pop()
                    unique_closing_tags[tag_src_index] = (src_index, seg)
            else:
                tgt_indices = aligned_segments.alignment.get_src(src_index)
                if tgt_indices != []:
                    for tgt_index in tgt_indices:
                        for tag_src_index in tag_stack:
                            tag_to_tgt_indices[tag_src_index].add(tgt_index)
        if tag_stack:
            raise ValueError(f"Paired tag is not closed in the source text.")

        assert set(unique_opening_tags.keys()) == set(unique_closing_tags.keys())

        for tag_src_index in unique_opening_tags.keys():
            tagged_tgt_indices = tag_to_tgt_indices[tag_src_index]
            if not tagged_tgt_indices:
                continue
            min_tgt_index = min(tagged_tgt_indices)
            max_tgt_index = max(tagged_tgt_indices)

            opening_src_index, opening_tag = unique_opening_tags[tag_src_index]
            assert opening_src_index == tag_src_index
            closing_src_index, closing_tag = unique_closing_tags[tag_src_index]
            assert min_tgt_index <= max_tgt_index

            # find the current line
            line_bound_index = bisect_left(line_boundaries, tag_src_index)
            left_line_bound = line_boundaries[line_bound_index-1]+1
            right_line_bound = line_boundaries[line_bound_index]
            assert left_line_bound <= tag_src_index and tag_src_index < right_line_bound

            # find where the text begins and ends in the current line
            text_src_indices = {i for i, seg in list(enumerate(aligned_segments.src))[left_line_bound:right_line_bound] if isinstance(seg, TextSegment)}
            seg = aligned_segments.src[tag_src_index]
            first_text_src_index = min(text_src_indices)
            last_text_src_index = max(text_src_indices)

            if opening_src_index <= first_text_src_index and closing_src_index >= last_text_src_index:
                logger.info(f"Found a tag that spans the entire line {line_bound_index} in the source.")
                left_tgt_line_bound = tgt_line_boundaries[line_bound_index-1]+1
                right_tgt_line_bound = tgt_line_boundaries[line_bound_index]
                text_tgt_indices = {i for i, seg in list(enumerate(aligned_segments.tgt))[left_tgt_line_bound:right_tgt_line_bound] if isinstance(seg, TextSegment)}
                min_tgt_index = min(min_tgt_index, min(text_tgt_indices))
                max_tgt_index = max(max(text_tgt_indices), max_tgt_index)

            aligned_segments.insert_segment(min_tgt_index, opening_tag)
            aligned_segments.insert_segment(max_tgt_index+2, closing_tag)
            aligned_segments.alignment.add((opening_src_index, min_tgt_index))
            aligned_segments.alignment.add((closing_src_index, max_tgt_index+2))
            # fix indices after insertion
            for tag_2 in unique_opening_tags.keys():
                fixed_indices: Set[int] = set()
                for src_index in tag_to_tgt_indices[tag_2]:
                    if src_index > max_tgt_index:
                        fixed_indices.add(src_index+2)
                    elif src_index >= min_tgt_index:
                        fixed_indices.add(src_index+1)
                    else:
                        fixed_indices.add(src_index)
                tag_to_tgt_indices[tag_2] = fixed_indices
            
            # update target line boundaries
            tgt_line_boundaries = _find_line_boundaries(aligned_segments.tgt)

        return aligned_segments

class MarkupTranslator:
    def __init__(self, translator: Translator, aligner: Aligner, tokenizer: Tokenizer):
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
                aligned_segments += AlignedSegments(SegmentedText([SentenceSeparator()]), SegmentedText([SentenceSeparator()]), Alignment({(0,0)}))
            alignment = set(map(tuple, alignment))
            aligned_segments += AlignedSegments(src_sentence_segments, tgt_sentence_segments, Alignment(alignment))
            first = False

        return aligned_segments

    def translate(self, src: str) -> str:
        timer_start = perf_counter()
        # remove non-breakable spaces
        src = src.replace("\xa0", " ")
        src_segments = SegmentedText.from_string(src)
        src_segments = src_segments.tokenize(self.tokenizer)

        src_for_translation, src_segments_to_src_for_translation = src_segments.translator_view()

        # src_segments_to_src_for_translation.debug_print()

        logger.info("RUN TRANSLATION")
        timer = perf_counter()
        src_sentences, tgt_sentences = self.translator.translate(str(src_for_translation))
        translation_time = perf_counter() - timer
        
        # print()
        # print(":: src sentences")
        src_sentences_segments = SegmentedText.from_sentences(src_sentences)
        src_sentences_segments = src_sentences_segments.tokenize(self.tokenizer)
        # prepare source sentences for word alignment
        src_tokens, src_sentences_to_src_tokens = src_sentences_segments.aligner_view()

        # recover the sentence segmentation from src_sentences
        src_for_translation_to_src_sentences = AlignedSegments(src_for_translation, src_sentences_segments)
        src_for_translation_to_src_sentences.recover_alignment()

        # print(":: tgt sentences")
        tgt_sentences_segments = SegmentedText.from_sentences(tgt_sentences)
        tgt_sentences_segments = tgt_sentences_segments.tokenize(self.tokenizer)
        # prepare target sentences for word alignment
        tgt_tokens, tgt_sentences_to_tgt_tokens = tgt_sentences_segments.aligner_view()
        tgt_tokens_to_tgt_sentences = tgt_sentences_to_tgt_tokens.swap_sides()

        logger.info("RUN ALIGNER")
        timer = perf_counter()
        src_tokens_to_tgt_tokens_alignment = self.align_segments(src_tokens, tgt_tokens)
        alignment_time = perf_counter() - timer
        
        src_tokens_to_tgt_tokens_alignment.recover_newline_alignment()

        src_for_translation_to_tgt_sentences = \
            src_for_translation_to_src_sentences \
            .compose(src_sentences_to_src_tokens) \
            .compose(src_tokens_to_tgt_tokens_alignment) \
            .compose(tgt_tokens_to_tgt_sentences)

        print(":: infer_whitespace_alignment")
        # src_for_translation_to_tgt_sentences.debug_print()
        src_for_translation_to_tgt_sentences.infer_whitespace_alignment()
        # src_for_translation_to_tgt_sentences.debug_print()

        src_segments_to_tgt_sentences = \
            src_segments_to_src_for_translation \
            .compose(src_for_translation_to_tgt_sentences) \
        
        print()
        print(":: final alignment before reinserting tags:")
        # src_segments_to_tgt_sentences.debug_print()

        print()
        print(":: reinsert paired tags")
        TagReinserter.reinsert_tags(src_segments_to_tgt_sentences)
        # src_segments_to_tgt_sentences.debug_print()

        print()
        print(":: reinsert aligned whitespace")
        TagReinserter.reinsert_whitespace(src_segments_to_tgt_sentences)
        # src_segments_to_tgt_sentences.debug_print()

        print()
        print(":: reinsert missing segments")
        TagReinserter.reinsert_segments(src_segments_to_tgt_sentences)
        # src_segments_to_tgt_sentences.debug_print()

        logger.info(f"Translation took {translation_time:.2f} sec")
        logger.info(f"Alignment took {alignment_time:.2f} seconds")
        total = perf_counter() - timer_start
        logger.info(f"Total time {total:.2f} seconds")
        logger.info(f"Total without requests {(total - translation_time - alignment_time):.2f} seconds")
        return str(src_segments_to_tgt_sentences.tgt)

from sentence_splitter import SentenceSplitter # type: ignore
import requests
class LindatTranslator(Translator):
    def __init__(self, src_lang: str, tgt_lang: str):
        self.src_lang = src_lang
        self.tgt_lang = tgt_lang
        self.splitter = SentenceSplitter(language=src_lang)
    def translate(self, input_text: str) -> Tuple[List[str], List[str]]:
        src_lang = self.src_lang
        tgt_lang = self.tgt_lang
        assert src_lang+"-"+tgt_lang in [
            "en-cs","cs-en","en-hi","en-fr","fr-en","en-de","de-en","ru-en","en-ru","en-pl","pl-en","uk-cs","cs-uk","ru-cs","cs-ru"
        ]
        url = f"https://lindat.mff.cuni.cz/services/translation/api/v2/models/{src_lang}-{tgt_lang}"
        headers = {
            "accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        num_prefix_newlines = 0
        if input_text.startswith("\n"):
            while input_text[num_prefix_newlines] == "\n":
                num_prefix_newlines += 1
            input_text = input_text[num_prefix_newlines:]

        print("LINDAT TRANSLATOR HERE")
        SENT_LEN_LIMIT = 500
        def _sentence_split(text: str):
            output: List[str] = []
            for line in re.split(r"(\n+)", text):
                if not line:
                    continue
                if line.startswith("\n") and output:
                    output[-1] += line
                else:
                    output.extend(self.splitter.split(line))
            return output
        
        def split_to_sent_array(text: str):
            sent_array: List[str] = []
            for sent in _sentence_split(text):
                while len(sent) > SENT_LEN_LIMIT:
                    try:
                        # When sent starts with a space, then sent[0:0] was an empty string,
                        # and it caused an infinite loop. This fixes it.
                        beg = 0
                        while sent[beg] == ' ':
                            beg += 1
                        last_space_idx = sent.rindex(" ", beg, SENT_LEN_LIMIT)
                        sent_array.append(sent[0:last_space_idx])
                        sent = sent[last_space_idx:]
                    except ValueError:
                        # raised if no space found by rindex
                        sent_array.append(sent[0:SENT_LEN_LIMIT])
                        sent = sent[SENT_LEN_LIMIT:]
                sent_array.append(sent)
            return sent_array

        src_sentences = split_to_sent_array(input_text)
        data = {
                "src": src_lang,
                "tgt": tgt_lang,
                "input_text": input_text,
        }
        print("====")
        tgt_sentences = requests.post(url, headers=headers, data=data).json()
        assert len(src_sentences) == len(tgt_sentences), f"{len(src_sentences)} != {len(tgt_sentences)}"
        if tgt_sentences:
            # if the line was empty or whitespace-only, then discard any potential translation
            new_tgt_sentences: List[str] = []
            for src, tgt in zip(src_sentences, tgt_sentences):
                if re.match(r"^\s+$", src):
                    new_tgt_sentences.append(src)
                else:
                    new_tgt_sentences.append(tgt)
            tgt_sentences = new_tgt_sentences
            # reinsert prefix newlines
            src_sentences[0] = "\n" * num_prefix_newlines + src_sentences[0]
            tgt_sentences[0] = "\n" * num_prefix_newlines + tgt_sentences[0]
            # add spaces after sentence ends
            tgt_sentences = [tgt_sentence + " " if not tgt_sentence.endswith("\n") else tgt_sentence for tgt_sentence in tgt_sentences]
            # remove final newline
            assert tgt_sentences[-1].endswith("\n")
            tgt_sentences[-1] = tgt_sentences[-1][:-1]
        print("")
        print(src_sentences, tgt_sentences)
        return src_sentences, tgt_sentences

import sys
class LindatAligner(Aligner):
    def __init__(self, src_lang: str, tgt_lang: str):
        self.src_lang = src_lang
        self.tgt_lang = tgt_lang
    def align(self, src_batch: List[List[str]], tgt_batch: List[List[str]]) -> List[List[Tuple[int, int]]]:
        src_lang = self.src_lang
        tgt_lang = self.tgt_lang

        url = f'https://lindat.cz/services/text-aligner/align/{src_lang}-{tgt_lang}'
        headers = {
            'Content-Type': 'application/json',
        }
        data = {
            'src_tokens': src_batch,
            'trg_tokens': tgt_batch,
        }
        print("Alignment data", data)
        tgt_lang = self.tgt_lang


        response = requests.post(url, headers=headers, json=data)

        if response.status_code == 200:
            alignment = response.json()["alignment"]
            print(alignment)
            return alignment
        else:
            print(f"Error: {response.status_code}", file=sys.stderr)
            print(response.text, file=sys.stderr)
            raise Exception

class RegexTokenizer(Tokenizer):
    def __init__(self):
        ACCENT = chr(769)
        self.WORD_TOKENIZATION_RULES = re.compile(r"""
        [\w""" + ACCENT + """]+://(?:[a-zA-Z]|[0-9]|[$-_@.&+])+
        |[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+.[a-zA-Z0-9-.]+
        |[0-9]+-[а-яА-ЯіїІЇ'’`""" + ACCENT + r"""]+
        |[+-]?[0-9](?:[0-9,.-]*[0-9])?
        |[\w""" + ACCENT + r"""](?:[\w'’`-""" + ACCENT + r"""]?[\w""" + ACCENT + r"""]+)*
        |[\w""" + ACCENT + r"""].(?:\[\w""" + ACCENT + r"""].)+[\w""" + ACCENT + r"""]?
        |[^\s]
        |[.!?]+
        |-+
        """, re.X | re.U)

    def tokenize(self, string: str) -> List[str]:
        return re.findall(self.WORD_TOKENIZATION_RULES, string)

import argparse
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Translate texts line by line')
    parser.add_argument('input_file', help='Input text file with markup')
    parser.add_argument('src_lang', help='Source language')
    parser.add_argument('tgt_lang', help='Target language')
    parser.add_argument('output_file', help='Output text file')
    args = parser.parse_args()

    translator = LindatTranslator(args.src_lang, args.tgt_lang)
    aligner = LindatAligner(args.src_lang, args.tgt_lang)
    tokenizer = RegexTokenizer()
    mt = MarkupTranslator(translator, aligner, tokenizer)

    with open(args.input_file) as f_in, open(args.output_file, "w") as f_out:
        input_text = f_in.read()
        print(repr(input_text))
        output = mt.translate(input_text)
        print(repr(output))
        f_out.write(output)
