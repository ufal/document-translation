import re
from typing import Iterable, Iterator, List, Optional

from termcolor import colored

class Segment(object):
    def __init__(self, string: str):
        self.string = string
    def debug_color(self, string: str) -> str:
        raise NotImplementedError
    @property
    def debug_str(self) -> str:
        return self.debug_color(self.string)
    def debug_len(self) -> int:
        return len(self.string)
    def __str__(self) -> str:
        return self.string
    def __repr__(self) -> str:
        return repr(self.string)
    def __len__(self) -> int:
        return len(self.string)

class TextSegment(Segment):
    def debug_color(self, string: str) -> str:
        return colored(string, "black", "on_white")

class TagSegment(Segment):
    def __init__(self, string: str):
        super().__init__(string)
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
    @property
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
    def __init__(self):
        super().__init__("")
    def debug_color(self, string: str) -> str:
        return colored(string, "black", "on_red")
    @property
    def debug_str(self):
        return self.debug_color("||")
    def debug_len(self) -> int:
        return 2

class SegmentedText(List[Segment]):
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
        return ''.join(str(x) for x in self)

    def replace(self, old: Segment, new: Segment) -> None:
        i = self.index(old)
        self[i] = new
        try:
            self.index(old, i)
        except:
            pass
        else:
            raise ValueError("Found duplicate segment in SegmentedText")

    @property
    def debug_str(self) -> str:
        return ''.join(x.debug_str for x in self)

    def debug_print(self) -> None:
        print(self.debug_str)
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

    def split_sentences(self) -> Iterator["SegmentedText"]:
        i = 0
        for j, seg in enumerate(self):
            if isinstance(seg, SentenceSeparator):
                # TODO (low priority): why self[i:j] does not return SegmentedText right away?
                yield SegmentedText(self[i:j])
                i = j + 1
        yield SegmentedText(self[i:])
