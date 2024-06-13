from typing import Iterable, List, Optional, Self, Tuple

from markuptranslator.alignment import Alignment
from markuptranslator.segmentedtext import Segment, SegmentedText, SentenceSeparator, WhitespaceSegment


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

    def alignment_from_iterable(self, alignment: Iterable[Tuple[int, int]]) -> None:
        alignment_segments = [(self.src[i], self.tgt[j]) for i, j in alignment]
        self.alignment.update_from_iterable(alignment_segments)

    def insert_segment(self, index: int, segment: Segment) -> None:
        self.tgt.insert(index, segment)
    
    def remove_segment(self, index: int) -> None:
        self.tgt.pop(index)

    def tgts_to_indices(self, tgts: Iterable[Segment]) -> List[int]:
        # TODO (low priority): this could be optimized
        return [self.tgt.index(tgt) for tgt in tgts]

    def __str__(self) -> str:
        return f"AlignedSegments({self.src}, {self.tgt}, {self.alignment})"
    
    def __add__(self, other: Self):
        # TODO (low priority): (self.src + other.src) should return SegmentedText right away
        src = SegmentedText(self.src + other.src)
        tgt = SegmentedText(self.tgt + other.tgt)
        alignment = self.alignment + other.alignment
        return AlignedSegments(src, tgt, alignment)

    def debug_print(self) -> None:
        self.src.debug_print()
        self.tgt.debug_print()
        if len(self.src) < 200:
            print(self.alignment)
            print(([(self.src.index(src), self.tgt.index(tgt)) for src, tgt in self.alignment.to_list()]))
    
    def recover_alignment(self) -> None:
        # greedily recover the alignment based on segment equality
        # assume that tgt contains extra elements and src == (tgt - extra)
        assert self.alignment.is_empty()
        src_iter = iter(self.src)
        for seg_tgt in self.tgt:
            # skip sentence separators
            if isinstance(seg_tgt, SentenceSeparator):
                continue

            seg_tgt_str = str(seg_tgt)
            while True:
                seg_src = next(src_iter)
                if str(seg_src) == seg_tgt_str:
                    self.alignment.add(seg_src, seg_tgt)
                    break
                if seg_tgt_str.startswith(str(seg_src)):
                    self.alignment.add(seg_src, seg_tgt)
                    seg_tgt_str = seg_tgt_str[len(seg_src):]
    
        try:
            next(src_iter)
        except StopIteration:
            pass
        else:
            assert False

    def recover_newline_alignment(self) -> None:
        src_newlines = [nl for nl in self.src if str(nl) == "\n"]
        tgt_newlines = [nl for nl in self.tgt if str(nl) == "\n"]
        assert len(src_newlines) == len(tgt_newlines)
        self.alignment.update_from_iterable(zip(src_newlines, tgt_newlines))

    def rightmost_alignment_by_src(self) -> List[int]:
        rightmost_alignment: List[int] = []
        current = -1
        for seg in self.src:
            if self.alignment.is_src_aligned(seg):
                tgt_indices = [self.tgt.index(tgt) for tgt in self.alignment.get(seg)]
                current = max(current, *tgt_indices)
            rightmost_alignment.append(current)
        return rightmost_alignment

    def leftmost_alignment_by_src(self) -> List[int]:
        leftmost_alignment: List[int] = []
        current = len(self.tgt)
        for seg in reversed(self.src):
            if self.alignment.is_src_aligned(seg):
                tgt_indices = [self.tgt.index(tgt) for tgt in self.alignment.get(seg)]
                current = min(current, *tgt_indices)
            leftmost_alignment.append(current)
        return list(reversed(leftmost_alignment))

    def infer_whitespace_alignment(self) -> None:
        """
        find whitespace alignments that do not "cross" any existing alignments
        for example:
        we have alignments (1,2), (3, 6)
        can we add (2, 3)? yes because (2, 3) fits in between (1, 2) and (3, 6)
        can we add (2, 0)? No, because that would "cross" the alignment (1, 2)
        """
        rightmost_alignment_by_src = self.rightmost_alignment_by_src()
        leftmost_alignment_by_src = self.leftmost_alignment_by_src()
        for i, seg_src in enumerate(self.src):
            if isinstance(seg_src, WhitespaceSegment) and not self.alignment.is_src_aligned(seg_src):
                # segment is whitespace and is not aligned to anything in target
                # find the first whitespace in target that we can align this whitespace 
                # without crossing any existing alignments
                for j in range(rightmost_alignment_by_src[i]+1, leftmost_alignment_by_src[i]):
                    # check if this whitespace can be aligned
                    seg_tgt = self.tgt[j]
                    if isinstance(seg_tgt, WhitespaceSegment) and not self.alignment.is_tgt_aligned(seg_tgt):
                        self.alignment.add(seg_src, seg_tgt)
                        break

    def swap_sides(self) -> "AlignedSegments":
        return AlignedSegments(self.tgt, self.src, self.alignment.swap())
    
    def compose(self, other: Self) -> "AlignedSegments":
        assert str(self.tgt) == str(other.src)
        new_alignment = self.alignment.compose(other.alignment)
        return AlignedSegments(self.src, other.tgt, new_alignment)
