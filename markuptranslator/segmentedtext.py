import re
from typing import Iterable, Iterator, List, Optional, Self, Tuple

from termcolor import colored

from markuptranslator.alignment import Alignment

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

    def translator_view(self) -> Tuple["SegmentedText", Alignment]:
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
        return src_for_translator, alignment
    
    def aligner_view(self) -> Tuple["SegmentedText", Alignment]:
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
        return src_for_aligner, alignment

    def split_sentences(self) -> Iterator["SegmentedText"]:
        i = 0
        for j, seg in enumerate(self):
            if isinstance(seg, SentenceSeparator):
                # TODO (low priority): why self[i:j] does not return SegmentedText right away?
                yield SegmentedText(self[i:j])
                i = j + 1
        yield SegmentedText(self[i:])
