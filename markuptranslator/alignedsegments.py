from typing import List, Optional, Self

from markuptranslator.alignment import Alignment
from markuptranslator.segmentedtext import JoinedSegment, Segment, SegmentedText, SentenceSeparator, WhitespaceSegment


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
        self.src = SegmentedText(self.src[:start] + [new_seg] + self.src[end:])
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
