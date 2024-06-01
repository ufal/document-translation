from collections import defaultdict
from functools import cached_property
from typing import Callable, Dict, Iterable, List, Optional, Self, Set, Tuple
import re
from enum import Enum
import logging

from termcolor import colored

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
            # TODO (low priority): could be merged
            match_tag = re.search(r'<(\w+)', string)

            # warning: also matches wrongly id="1' but that is not a problem
            match_id = re.search(r'id=("|\')(\d+)("|\')', string)
            if match_tag:
                self.tag = match_tag.group(1)
            else:
                raise ValueError("tag name not found in string: " + string)
            if match_id:
                self.id = int(match_id.group(2))
            else:
                raise ValueError("id attribute not found in string: " + string)

        self.id = 0
    def debug_color(self, string: str) -> str:
        return colored(string, "black", "on_cyan", attrs=["bold"])

class PairedTagSegment(TagSegment):
    def __init__(self, string: str) -> None:
        super().__init__(string)
        if string == '</g>':
            self.opening_tag = False
        elif string.startswith('<g'):
            self.opening_tag = True
        else:
            raise ValueError(f"Not a PairedTagSegment string: {string}")

        self.opening_tag = True

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

class SegmentedText(list[Segment]):
    """
    A text that has been split into segments of text, tags and whitespace.
    The main assumption is that joining the segments will yield the original text.
    """
    segments_regex = re.compile(r'(</?(g|x|bx|ex|lb|mrk).*?>|\s+|[^<\s]+|[^>\s]+)')

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

    def translation_view(self):
        # TODO (low priority): maybe rename tgt to something like src_for_translation
        tgt = SegmentedText()
        alignment = Alignment()
        for i, s in enumerate(self):
            if isinstance(s, TagSegment):
                continue
            elif isinstance(s, WhitespaceSegment):
                normalized_whitespace = re.sub(r'[^\n]', ' ', s)
                tgt.append(WhitespaceSegment(normalized_whitespace))
                alignment.mapping.append((i, len(tgt) - 1))
            else:
                tgt.append(s)
                alignment.mapping.append((i, len(tgt) - 1))
        return tgt, AlignedSegments(self, tgt, alignment)
    
    def alignment_view(self):
        tgt = SegmentedText()
        alignment = Alignment()
        for i, s in enumerate(self):
            if isinstance(s, TextSegment) or isinstance(s, SentenceSeparator):
                tgt.append(s)
                alignment.mapping.append((i, len(tgt) - 1))
        return tgt, AlignedSegments(self, tgt, alignment)

    def split_sentences(self):
        i = 0
        for j, seg in enumerate(self):
            if isinstance(seg, SentenceSeparator):
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
    
    def recover_alignment(self) -> None:
        # greedily recover the alignment based on segment equality
        # assume that tgt contains extra elements and src == (tgt - extra)
        assert self.alignment.mapping == []
        src_iter = enumerate(self.src)
        for i, seg_tgt in enumerate(self.tgt):
            print(i, seg_tgt.debug_str())
            # skip sentence separators
            if isinstance(seg_tgt, SentenceSeparator):
                continue
            while True:
                j, seg_src = next(src_iter)
                print("\t", j, seg_tgt.debug_str())
                if seg_src == seg_tgt:
                    self.alignment.mapping.append((j, i))
                    break
                # if not found immediately do not continue 
                # searching for whitespace, it might be missing
                if isinstance(seg_tgt, WhitespaceSegment):
                    break

        # assume that src contains extra elements and (src - extra) == tgt
        # tgt_iter = enumerate(self.tgt)
        # for i, seg_src in enumerate(self.src):
        #     print(i, seg_src.debug_str())
        #     # skip sentence separators
        #     if seg_src.type == SegmentType.SENTENCE_SEP:
        #         continue
        #     while True:
        #         j, seg_tgt = next(tgt_iter)
        #         # do no try to find whitespace, it might be missing
        #         if seg_src.type == SegmentType.WHITESPACE:
        #             break
        #         print("\t", j, seg_tgt)
        #         if seg_tgt == seg_src:
        #             self.alignment.mapping.append((i, j))
        #             break
    
    def swap_sides(self) -> "AlignedSegments":
        # TODO (low priority): alignment should be more of a black box
        alignment = self.alignment.map(lambda i, j: (j, i))
        return AlignedSegments(self.tgt, self.src, alignment)
    
    def compose(self, other: Self) -> "AlignedSegments":
        assert self.tgt == other.src
        # TODO (low priority): move this into Alignment method
        new_alignment: List[Tuple[int, int]] = []
        for (i, j) in self.alignment.mapping:
            for (k, l) in other.alignment.mapping:
                if j == k:
                    new_alignment.append((i, l))
        return AlignedSegments(self.src, other.tgt, Alignment(new_alignment))


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
        # class TaggedSegment(Segment):
        #     def __init__(self, string: str, type: SegmentType, tags: Set[int]):
        #         super().__init__(string, type)
        #         self.tags = tags
        #     @classmethod
        #     def from_segment(cls, segment: Segment):
        #         return cls(segment.string, segment.type, set())
        #     def __str__(self) -> str:
        #         return f"<TaggedSegment({repr(self.string)}, {self.type}, {self.tags})>"

        tagged_src: List[Segment] = []
        # src_to_tagged = AlignedSegments(aligned_segments.src, aligned_segments.src)
        # src_to_tagged.recover_alignment()
        # src_to_tagged.filter_tgt(lambda seg: )
        # src_to_tagged = AlignedSegments(aligned_segments.src, tagged_src)
        for seg in aligned_segments.src:
            if isinstance(seg, TagSegment):
                tagged_src.append(seg)
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
            # tagged_tgt.insert(min_index, TaggedSegment("<g>", SegmentType.TAG, set()))
            # tagged_tgt.insert(max_index+2, TaggedSegment("</g>", SegmentType.TAG, set()))

            aligned_segments.insert_segment(min_index, unique_tags_begins[tag])
            aligned_segments.insert_segment(max_index+2, unique_tags_ends[tag])

        # for i, seg in enumerate(tagged_tgt):
        #     print(i, seg)

        # print(str(tagged_tgt))

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
                aligned_segments += AlignedSegments(SegmentedText([SentenceSeparator()]), SegmentedText([SentenceSeparator()]), Alignment([(0,0)]))
            aligned_segments += AlignedSegments(src_sentence_segments, tgt_sentence_segments, Alignment(alignment))
            first = False

        return aligned_segments

    def translate(self, src: str) -> str:
        src_segments = SegmentedText.from_string(src)
        src_segments = src_segments.tokenize(self.tokenizer)

        # print(":: src segments before translation:")
        # src_segments.debug_print()

        src_for_translation, src_segments_to_src_for_translation = src_segments.translation_view()

        print("TRANSLATION")
        src_sentences, tgt_sentences = self.translator.translate(str(src_for_translation))
        print()
        print(":: src sentences")
        src_sentences_segments = SegmentedText.from_sentences(src_sentences)
        src_sentences_segments = src_sentences_segments.tokenize(self.tokenizer)
        # prepare source sentences for word alignment
        src_tokens, src_sentences_to_src_tokens = src_sentences_segments.alignment_view()

        # recover the sentence segmentation from src_sentences
        src_for_translation_to_src_sentences = AlignedSegments(src_for_translation, src_sentences_segments)
        src_for_translation_to_src_sentences.debug_print()
        src_for_translation_to_src_sentences.recover_alignment()
        src_for_translation_to_src_sentences.debug_print()

        print(":: tgt sentences")
        tgt_sentences_segments = SegmentedText.from_sentences(tgt_sentences)
        tgt_sentences_segments = tgt_sentences_segments.tokenize(self.tokenizer)
        # prepare target sentences for word alignment
        tgt_tokens, tgt_sentences_to_tgt_tokens = tgt_sentences_segments.alignment_view()
        tgt_tokens_to_tgt_sentences = tgt_sentences_to_tgt_tokens.swap_sides()

        print("ALIGNMENT")
        src_tokens_to_tgt_tokens_alignment = self.align_segments(src_tokens, tgt_tokens)

        # and now, mother of all compositions
        src_segments_to_tgt_sentences = \
            src_segments_to_src_for_translation \
            .compose(src_for_translation_to_src_sentences) \
            .compose(src_sentences_to_src_tokens) \
            .compose(src_tokens_to_tgt_tokens_alignment) \
            .compose(tgt_tokens_to_tgt_sentences)

        src_segments_to_tgt_sentences.debug_print()

        TagReinserter.reinsert_tags(src_segments_to_tgt_sentences)

        # src_segments_to_tgt_sentences.debug_print()

        # tgt_sentences = list(src_segments_to_tgt_sentences.split_sentences())

        return "\n".join(tgt_sentences)
