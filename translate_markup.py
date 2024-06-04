from collections import defaultdict
from functools import cached_property
from typing import Callable, Dict, Iterable, List, Optional, Self, Set, Tuple
import re
import logging
from time import perf_counter

from termcolor import colored

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

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

    def translation_view(self):
        # TODO (low priority): maybe rename tgt to something like src_for_translation
        tgt = SegmentedText()
        alignment = Alignment()
        for i, s in enumerate(self):
            if isinstance(s, TagSegment):
                continue
            elif isinstance(s, WhitespaceSegment):
                if s == "\n" or s == " ":
                    tgt.append(s)
                else:
                    tgt.append(WhitespaceSegment(" "))
                alignment.mapping.append((i, len(tgt) - 1))
            else:
                tgt.append(s)
                alignment.mapping.append((i, len(tgt) - 1))
        return tgt, AlignedSegments(self, tgt, alignment)
    
    def alignment_view(self):
        tgt = SegmentedText()
        alignment = Alignment()
        for i, s in enumerate(self):
            if isinstance(s, TextSegment) or isinstance(s, SentenceSeparator) or s == "\n":
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
            # skip sentence separators
            if isinstance(seg_tgt, SentenceSeparator):
                continue
            while True:
                j, seg_src = next(src_iter)
                if seg_src == seg_tgt:
                    self.alignment.mapping.append((j, i))
                    break
                if seg_tgt.startswith(seg_src):
                    self.alignment.mapping.append((j, i))
                    seg_tgt = seg_tgt[len(seg_src):]
                # if not found immediately do not continue 
                # searching for whitespace, it might be missing
                if isinstance(seg_tgt, WhitespaceSegment):
                    break

    def recover_newline_alignment(self) -> None:
        src_newlines = [i for i, seg in enumerate(self.src) if seg == "\n"]
        tgt_newlines = [i for i, seg in enumerate(self.tgt) if seg == "\n"]
        assert len(src_newlines) == len(tgt_newlines)
        self.alignment.mapping.extend(zip(src_newlines, tgt_newlines))

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
            # fst = aligned_segments.src[i]
            # snd = aligned_segments.src[i+1]
            if _to_be_reinserted(i) and _to_be_reinserted(i+1):
                aligned_segments.join_adjacent_segments(i)
            else:
                i += 1

        for i, seg in enumerate(aligned_segments.src):
            if not _to_be_reinserted(i):
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
                    index = max(aligned_segments.alignment.get_src(i-1)) + 1
                    aligned_segments.insert_segment(index, seg)
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
                    max_tgt_indices_left = max(tgt_indices_left) if tgt_indices_left else 0
                    min_tgt_indices_right = min(tgt_indices_right) if tgt_indices_right else len(aligned_segments.tgt)
                    if max_tgt_indices_left <= min_tgt_indices_right:
                        # simple case
                        index = max_tgt_indices_left
                        aligned_segments.insert_segment(index, seg)
                    else:
                        logger.error("DID NOT FIND PLACE TO INSERT SEGMENT")
                        # TODO: implement a more sophisticated way to insert the segment
                        index = max(tgt_indices_left) + 1
                        aligned_segments.insert_segment(index, seg)
                        # aligned_segments.insert_segment(len(aligned_segments.tgt), seg)
                    # for j in range(0, len(aligned_segments.tgt)):
                    #     errors = 


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

        for i, seg in enumerate(aligned_segments.src):
            if isinstance(seg, PairedTagSegment):
                if seg.opening_tag:
                    tag_stack.append(i)
                    unique_opening_tags[i] = (i, seg)
                else:
                    tag = tag_stack.pop()
                    unique_closing_tags[tag] = (i, seg)
            else:
                tgt_indices = aligned_segments.alignment.get_src(i)
                if tgt_indices != []:
                    for tgt_index in tgt_indices:
                        for tag in tag_stack:
                            tag_to_tgt_indices[tag].add(tgt_index)
        if tag_stack:
            raise ValueError(f"tag_stack is not empty: {tag_stack}")

        assert set(unique_opening_tags.keys()) == set(unique_closing_tags.keys())
        
        for tag in unique_opening_tags.keys():
            tagged_indices = tag_to_tgt_indices[tag]
            if not tagged_indices:
                continue
            min_index = min(tagged_indices)
            max_index = max(tagged_indices)
            opening_src_index, opening_tag = unique_opening_tags[tag]
            assert opening_src_index == tag
            closing_src_index, closing_tag = unique_closing_tags[tag]
            assert min_index <= max_index
            aligned_segments.insert_segment(min_index, opening_tag)
            aligned_segments.insert_segment(max_index+2, closing_tag)
            aligned_segments.alignment.mapping.append((opening_src_index, min_index))
            aligned_segments.alignment.mapping.append((closing_src_index, max_index+2))
            # fix indices after insertion
            for tag_2 in unique_opening_tags.keys():
                fixed_indices: Set[int] = set()
                for i in tag_to_tgt_indices[tag_2]:
                    if i > max_index:
                        fixed_indices.add(i+2)
                    elif i >= min_index:
                        fixed_indices.add(i+1)
                    else:
                        fixed_indices.add(i)
                tag_to_tgt_indices[tag_2] = fixed_indices
                    

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
        timer_start = perf_counter()
        # remove non-breakable spaces
        src = src.replace("\xa0", " ")
        src_segments = SegmentedText.from_string(src)
        src_segments = src_segments.tokenize(self.tokenizer)

        src_for_translation, src_segments_to_src_for_translation = src_segments.translation_view()

        src_segments_to_src_for_translation.debug_print()

        logger.info("TRANSLATION")
        timer = perf_counter()
        src_sentences, tgt_sentences = self.translator.translate(str(src_for_translation))
        logger.info(f"Translation took {perf_counter() - timer:.2f} sec")
        # print()
        # print(":: src sentences")
        src_sentences_segments = SegmentedText.from_sentences(src_sentences)
        src_sentences_segments = src_sentences_segments.tokenize(self.tokenizer)
        # prepare source sentences for word alignment
        src_tokens, src_sentences_to_src_tokens = src_sentences_segments.alignment_view()

        # recover the sentence segmentation from src_sentences
        src_for_translation_to_src_sentences = AlignedSegments(src_for_translation, src_sentences_segments)
        # src_for_translation_to_src_sentences.debug_print()
        src_for_translation_to_src_sentences.recover_alignment()
        # src_for_translation_to_src_sentences.debug_print()

        # print(":: tgt sentences")
        tgt_sentences_segments = SegmentedText.from_sentences(tgt_sentences)
        tgt_sentences_segments = tgt_sentences_segments.tokenize(self.tokenizer)
        # prepare target sentences for word alignment
        tgt_tokens, tgt_sentences_to_tgt_tokens = tgt_sentences_segments.alignment_view()
        tgt_tokens_to_tgt_sentences = tgt_sentences_to_tgt_tokens.swap_sides()

        logger.info("ALIGNMENT")
        timer = perf_counter()
        src_tokens_to_tgt_tokens_alignment = self.align_segments(src_tokens, tgt_tokens)
        logger.info(f"Alignment took {perf_counter() - timer:.2f} seconds")
        src_tokens_to_tgt_tokens_alignment.recover_newline_alignment()

        # and now, mother of all compositions
        src_segments_to_tgt_sentences = \
            src_segments_to_src_for_translation \
            .compose(src_for_translation_to_src_sentences) \
            .compose(src_sentences_to_src_tokens) \
            .compose(src_tokens_to_tgt_tokens_alignment) \
            .compose(tgt_tokens_to_tgt_sentences)

        print()
        print(":: final alignment before reinserting tags:")
        src_segments_to_tgt_sentences.debug_print()

        print()
        print(":: reinsert paired tags")
        TagReinserter.reinsert_tags(src_segments_to_tgt_sentences)
        src_segments_to_tgt_sentences.debug_print()

        print()
        print(":: reinsert missing segments")
        TagReinserter.reinsert_segments(src_segments_to_tgt_sentences)
        src_segments_to_tgt_sentences.debug_print()

        logger.info(f"Total time {perf_counter() - timer_start:.2f} seconds")
        return str(src_segments_to_tgt_sentences.tgt)

from sentence_splitter import SentenceSplitter
import requests
class LindatTranslator:
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
        data = {
                "src": src_lang,
                "tgt": tgt_lang,
                "input_text": input_text,
        }
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
        print("LINDAT TRANSLATOR HERE")
        print("input to translator:")
        print(repr(input_text))
        print("====")
        src_sentences = _sentence_split(input_text)
        print(src_sentences)
        print("====")
        print()
        tgt_sentences = requests.post(url, headers=headers, data=data).json()
        assert len(src_sentences) == len(tgt_sentences)
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
        return src_sentences, tgt_sentences

import sys
class LindatAligner:
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

class RegexTokenizer:
    def __init__(self):
        ACCENT = chr(769)
        self.WORD_TOKENIZATION_RULES = re.compile(r"""
        [\w""" + ACCENT + """]+://(?:[a-zA-Z]|[0-9]|[$-_@.&+])+
        |[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+.[a-zA-Z0-9-.]+
        |[0-9]+-[а-яА-ЯіїІЇ'’`""" + ACCENT + """]+
        |[+-]?[0-9](?:[0-9,.-]*[0-9])?
        |[\w""" + ACCENT + """](?:[\w'’`-""" + ACCENT + """]?[\w""" + ACCENT + """]+)*
        |[\w""" + ACCENT + """].(?:\[\w""" + ACCENT + """].)+[\w""" + ACCENT + """]?
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
