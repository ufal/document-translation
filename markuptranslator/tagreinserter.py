from bisect import bisect_left
from collections import defaultdict
import logging
from typing import Dict, List, Set, Tuple
from markuptranslator.alignedsegments import AlignedSegments
from markuptranslator.segmentedtext import PairedTagSegment, SegmentedText, TagSegment, TextSegment, WhitespaceSegment

logger = logging.getLogger(__name__)


class TagReinserter:
    @staticmethod
    def reinsert_whitespace(aligned_segments: AlignedSegments) -> AlignedSegments:
        """
        Reinserts whitespace segments from `src` that are aligned to segment in `tgt` 
        but the whitespace has been normalized as a single space.
        """
        for src_seg in aligned_segments.src:
            tgt_seg_set = aligned_segments.alignment.get(src_seg)
            if isinstance(src_seg, WhitespaceSegment) and len(tgt_seg_set) == 1:
                # replace the segment
                tgt_seg = next(iter(tgt_seg_set))
                assert isinstance(tgt_seg, WhitespaceSegment)
                aligned_segments.alignment.remove(src_seg, tgt_seg)
                aligned_segments.tgt.replace(tgt_seg, src_seg)
                aligned_segments.alignment.add(src_seg, src_seg)

        return aligned_segments

    @staticmethod
    def reinsert_segments(aligned_segments: AlignedSegments) -> AlignedSegments:
        """
        Reinserts all segments from `src` that are not aligned to any segment in `tgt`.
        """
        def _to_be_reinserted(i: int) -> bool:
            segment = aligned_segments.src[i]
            # joined segment is a helper method for reinsert_segment and we want to reinsert it always
            # if isinstance(segment, JoinedSegment):
            #     return True
            # if the segment from `src` is aligned already with something in `tgt`, it should not be reinserted (as it is already there)
            if aligned_segments.alignment.is_src_aligned(segment):
                return False
            if isinstance(segment, PairedTagSegment):
                # TODO: log this only when the PairedTag contained something
                logger.warning(f"Found unaligned PairedTagSegment {segment} on index {i}!")
            # reinsert unaligned tags
            if isinstance(segment, TagSegment):
                return True
            # reinsert whitespace if it is not a simple space and it is not  newline
            if isinstance(segment, WhitespaceSegment) and str(segment) != " " and str(segment) != "\n":
                return True
            return False
        # simplify source segments - join the adjacent reinserted segments together
        # i = 0
        # old_src = str(aligned_segments.src)
        # while i < len(aligned_segments.src) - 1:
        #     if _to_be_reinserted(i):
        #         j = i + 1
        #         while j < len(aligned_segments.src) and _to_be_reinserted(j):
        #             j += 1
        #         if j > i + 1:
        #             aligned_segments.merge_segment_span(i, j)
        #         i += 1
        #     else:
        #         i += 1
        # assert str(aligned_segments.src) == old_src

        # TODO: hide this in Alignment
        # rightmost_alignment_by_src = [-1]*len(aligned_segments.src)
        # leftmost_alignment_by_src = [len(aligned_segments.tgt)]*len(aligned_segments.src)
        # for i, j in aligned_segments.alignment.mapping:
        #     # store minimum target index for each source
        #     if rightmost_alignment_by_src[i] < j:
        #         rightmost_alignment_by_src[i] = j
        #     # store maximum target index for each source
        #     if leftmost_alignment_by_src[i] > j:
        #         leftmost_alignment_by_src[i] = j
        # # fill missing values with the nearest previous alignment
        # current = -1
        # for i, j in enumerate(rightmost_alignment_by_src):
        #     if j == -1:
        #         rightmost_alignment_by_src[i] = current
        #     else:
        #         current = j
        # # fill missing values with the nearset next alignment
        # current = len(aligned_segments.tgt)
        # for i, j in reversed(list(enumerate(leftmost_alignment_by_src))):
        #     if j == len(aligned_segments.tgt):
        #         leftmost_alignment_by_src[i] = current
        #     else:
        #         current = j

        line_num = 0
        maximum_aligned_tgt = -1
        for index, seg in enumerate(aligned_segments.src):
            aligned_tgts = aligned_segments.alignment.get(seg)
            if aligned_tgts:
                aligned_tgts = aligned_segments.tgts_to_indices(aligned_tgts)
                maximum_aligned_tgt = max(maximum_aligned_tgt, max(aligned_tgts))
            if str(seg) == "\n":
                line_num += 1
            if not _to_be_reinserted(index):
                # this segment from src is aligned to a segment in tgt
                # therefore it does not need to be reinserted (it's already in tgt)
                continue
            else:
                # if rightmost_alignment_by_src[i] < leftmost_alignment_by_src[i]:
                #     logger.info("simple case")
                #     index = rightmost_alignment_by_src[i]+1
                # else:
                #     # TODO: find a better reinsertion index in this case
                #     logger.error(f"line {line_num}: there is no non-crossing placement for {seg.debug_str}")
                #     index = leftmost_alignment_by_src[i]
                index = maximum_aligned_tgt + 1
                aligned_segments.insert_segment(index, seg)
                aligned_segments.alignment.add(seg, seg)
                maximum_aligned_tgt += 1
                # TODO: the alignments are getting ugly and I need to rewrite it
                # rightmost_alignment_by_src = [k+1 if k >= index else k for k in rightmost_alignment_by_src]
                # old = rightmost_alignment_by_src[i]
                # rightmost_alignment_by_src[i] = max(rightmost_alignment_by_src[i], index)
                # # fill missing values with the nearest previous alignment
                # current = rightmost_alignment_by_src[i]
                # for i, j in enumerate(rightmost_alignment_by_src):
                #     if j == old:
                #         rightmost_alignment_by_src[i] = current
                #     if j > current:
                #         break
                # leftmost_alignment_by_src = [k+1 if k >= index else k for k in leftmost_alignment_by_src]
                # old = leftmost_alignment_by_src[i]
                # leftmost_alignment_by_src[i] = min(leftmost_alignment_by_src[i], index)
                # current = leftmost_alignment_by_src[i]
                # for i, j in reversed(list(enumerate(leftmost_alignment_by_src))):
                #     if j == old:
                #         rightmost_alignment_by_src[i] = current
                #     if j < current:
                #         break

        return aligned_segments

    # @staticmethod
    # def reinsert_tags(aligned_segments: AlignedSegments) -> AlignedSegments:
    #     """
    #     We have two sequences of segments.
    #     The segments are aligned - some segments in `src` are aligned to some other segments in `tgt`.
    #         - one segment in `src` may be aligned to multiple segments in `tgt` and vice versa
    #     Inside the `src` segments, there may be tags.
    #     A (B C) D ((E) F) G
    #     x x A x C x D x x E

    #     Segments that are not aligned are free to be tagged or untagged.
    #     Segments in `src` that are tagged should be tagged in `tgt`.
    #     """
    #     tag_stack: List[int] = []
    #     unique_opening_tags: Dict[int, Tuple[int, PairedTagSegment]] = dict()
    #     unique_closing_tags: Dict[int, Tuple[int, PairedTagSegment]] = dict()
    #     tag_to_tgt_indices: defaultdict[int, Set[int]] = defaultdict(set)

    #     def _find_line_boundaries(segments: SegmentedText):
    #         line_boundaries = [i for i, seg in enumerate(segments) if seg == "\n"]
    #         line_boundaries = [-1] + line_boundaries + [len(segments)]
    #         return line_boundaries
    #     line_boundaries = _find_line_boundaries(aligned_segments.src)
    #     tgt_line_boundaries = _find_line_boundaries(aligned_segments.tgt)
    #     assert len(line_boundaries) == len(tgt_line_boundaries)

    #     for src_index, seg in enumerate(aligned_segments.src):
    #         if seg == "\n" and tag_stack:
    #             line = bisect_left(line_boundaries, src_index)
    #             raise ValueError(f"Paired tag is not closed in the source text on line {line}.")
    #         if isinstance(seg, PairedTagSegment):
    #             if seg.opening_tag:
    #                 tag_stack.append(src_index)
    #                 unique_opening_tags[src_index] = (src_index, seg)
    #             else:
    #                 tag_src_index = tag_stack.pop()
    #                 unique_closing_tags[tag_src_index] = (src_index, seg)
    #         else:
    #             tgt_indices = aligned_segments.alignment.get_src(src_index)
    #             if tgt_indices != []:
    #                 for tgt_index in tgt_indices:
    #                     for tag_src_index in tag_stack:
    #                         tag_to_tgt_indices[tag_src_index].add(tgt_index)
    #     if tag_stack:
    #         raise ValueError(f"Paired tag is not closed in the source text.")

    #     assert set(unique_opening_tags.keys()) == set(unique_closing_tags.keys())

    #     for tag_src_index in unique_opening_tags.keys():
    #         tagged_tgt_indices = tag_to_tgt_indices[tag_src_index]
    #         if not tagged_tgt_indices:
    #             continue
    #         min_tgt_index = min(tagged_tgt_indices)
    #         max_tgt_index = max(tagged_tgt_indices)

    #         opening_src_index, opening_tag = unique_opening_tags[tag_src_index]
    #         assert opening_src_index == tag_src_index
    #         closing_src_index, closing_tag = unique_closing_tags[tag_src_index]
    #         assert min_tgt_index <= max_tgt_index

    #         # find the current line
    #         line_bound_index = bisect_left(line_boundaries, tag_src_index)
    #         left_line_bound = line_boundaries[line_bound_index-1]+1
    #         right_line_bound = line_boundaries[line_bound_index]
    #         assert left_line_bound <= tag_src_index and tag_src_index < right_line_bound

    #         # find where the text begins and ends in the current line
    #         text_src_indices = {i for i, seg in list(enumerate(aligned_segments.src))[left_line_bound:right_line_bound] if isinstance(seg, TextSegment)}
    #         seg = aligned_segments.src[tag_src_index]
    #         first_text_src_index = min(text_src_indices)
    #         last_text_src_index = max(text_src_indices)

    #         if opening_src_index <= first_text_src_index and closing_src_index >= last_text_src_index:
    #             logger.info(f"Found a tag that spans the entire line {line_bound_index} in the source.")
    #             left_tgt_line_bound = tgt_line_boundaries[line_bound_index-1]+1
    #             right_tgt_line_bound = tgt_line_boundaries[line_bound_index]
    #             text_tgt_indices = {i for i, seg in list(enumerate(aligned_segments.tgt))[left_tgt_line_bound:right_tgt_line_bound] if isinstance(seg, TextSegment)}
    #             min_tgt_index = min(min_tgt_index, min(text_tgt_indices))
    #             max_tgt_index = max(max(text_tgt_indices), max_tgt_index)

    #         aligned_segments.insert_segment(min_tgt_index, opening_tag)
    #         aligned_segments.insert_segment(max_tgt_index+2, closing_tag)
    #         aligned_segments.alignment.add((opening_src_index, min_tgt_index))
    #         aligned_segments.alignment.add((closing_src_index, max_tgt_index+2))
    #         # fix indices after insertion
    #         for tag_2 in unique_opening_tags.keys():
    #             fixed_indices: Set[int] = set()
    #             for src_index in tag_to_tgt_indices[tag_2]:
    #                 if src_index > max_tgt_index:
    #                     fixed_indices.add(src_index+2)
    #                 elif src_index >= min_tgt_index:
    #                     fixed_indices.add(src_index+1)
    #                 else:
    #                     fixed_indices.add(src_index)
    #             tag_to_tgt_indices[tag_2] = fixed_indices
            
    #         # update target line boundaries
    #         tgt_line_boundaries = _find_line_boundaries(aligned_segments.tgt)

    #     return aligned_segments
