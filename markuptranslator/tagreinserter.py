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
            # if isinstance(segment, PairedTagSegment):
                # TODO: log this only when the PairedTag contained something
                # logger.warning(f"Found unaligned PairedTagSegment {segment} on index {i}!")
            # reinsert unaligned tags
            if isinstance(segment, TagSegment):
                return True
            # reinsert whitespace if it is not a simple space and it is not  newline
            if isinstance(segment, WhitespaceSegment) and str(segment) != " " and str(segment) != "\n":
                return True
            return False

        rightmost_alignment = aligned_segments.rightmost_alignment_by_src()
        leftmost_alignment = aligned_segments.leftmost_alignment_by_src()

        to_insert = defaultdict(list)

        line_num = 1
        for index, seg in enumerate(aligned_segments.src):
            if str(seg) == "\n":
                line_num += 1
            if not _to_be_reinserted(index):
                # this segment from src is aligned to a segment in tgt
                # therefore it does not need to be reinserted (it's already in tgt)
                continue
            else:
                rightmost = rightmost_alignment[index]
                leftmost = leftmost_alignment[index]
                if rightmost < leftmost:
                    logger.info(f"simple case for {index}-{seg.debug_str}")
                    # reinsert_index = rightmost+1
                    reinsert_index = leftmost

                    # print(aligned_segments.rightmost_alignment_by_src())
                    # print(aligned_segments.leftmost_alignment_by_src())
                else:
                    # TODO: find a better reinsertion reinsert_index in this case
                    logger.error(f"line {line_num}: there is no non-crossing placement for {index}-{seg.debug_str}")
                    reinsert_index = leftmost
                    # aligned_segments.debug_print()
                    # print(rightmost_alignment)
                    # print(leftmost_alignment)
                    # crossings = sum()
                to_insert[reinsert_index].append(seg)
        
        logger.info(f"now reinserting segments")
        num_inserted = 0
        for reinsert_index in sorted(to_insert.keys()):
            for seg in to_insert[reinsert_index]:
                aligned_segments.insert_segment(reinsert_index + num_inserted, seg)
                aligned_segments.alignment.add(seg, seg)
                num_inserted += 1
        logger.info(f"done reinserting {num_inserted} segments")

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

        tgt_index_lookup = {tgt: i for i, tgt in enumerate(aligned_segments.tgt)}

        def _find_line_boundaries(segments: SegmentedText):
            line_boundaries = [i for i, seg in enumerate(segments) if str(seg) == "\n"]
            line_boundaries = [-1] + line_boundaries + [len(segments)]
            return line_boundaries
        src_line_boundaries = _find_line_boundaries(aligned_segments.src)
        tgt_line_boundaries = _find_line_boundaries(aligned_segments.tgt)
        assert len(src_line_boundaries) == len(tgt_line_boundaries)
        
        line = 0
        for src_index, seg in enumerate(aligned_segments.src):
            if str(seg) == "\n":
                line += 1
                if tag_stack:
                    raise ValueError(f"Paired tag is not closed in the source text on line {line}.")
            if isinstance(seg, PairedTagSegment):
                if seg.opening_tag:
                    tag_stack.append(src_index)
                    unique_opening_tags[src_index] = (src_index, seg)
                else:
                    tag_src_index = tag_stack.pop()
                    unique_closing_tags[tag_src_index] = (src_index, seg)
            else:
                tgt_segments = aligned_segments.alignment.get(seg)
                if len(tgt_segments) > 0:
                    for tgt_segment in tgt_segments:
                        for tag_src_index in tag_stack:
                            tag_to_tgt_indices[tag_src_index].add(tgt_index_lookup[tgt_segment])

        if tag_stack:
            raise ValueError(f"Paired tag is not closed in the source text.")

        assert set(unique_opening_tags.keys()) == set(unique_closing_tags.keys())

        to_insert = defaultdict(list)

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
            line_bound_index = bisect_left(src_line_boundaries, tag_src_index)
            left_line_bound = src_line_boundaries[line_bound_index-1]+1
            right_line_bound = src_line_boundaries[line_bound_index]
            assert left_line_bound <= tag_src_index and tag_src_index < right_line_bound

            # find where the text begins and ends in the current line
            text_src_indices = {i for i, seg in list(enumerate(aligned_segments.src))[left_line_bound:right_line_bound] if isinstance(seg, TextSegment)}
            first_text_src_index = min(text_src_indices)
            last_text_src_index = max(text_src_indices)

            # if the tag spans the entire line, then we make it span the entire line in the target
            if opening_src_index <= first_text_src_index and closing_src_index >= last_text_src_index:
                logger.info(f"Found a tag that spans the entire line {line_bound_index} in the source.")
                left_tgt_line_bound = tgt_line_boundaries[line_bound_index-1]+1
                right_tgt_line_bound = tgt_line_boundaries[line_bound_index]
                text_tgt_indices = {i for i, seg in list(enumerate(aligned_segments.tgt))[left_tgt_line_bound:right_tgt_line_bound] if isinstance(seg, TextSegment)}
                min_tgt_index = min(min_tgt_index, min(text_tgt_indices))
                max_tgt_index = max(max(text_tgt_indices), max_tgt_index)

            to_insert[min_tgt_index].append(opening_tag)
            # we prepend the closing tag so that it matches the order of the opening tags
            to_insert[max_tgt_index+1].insert(0, closing_tag)

        logger.info(f"now reinserting paired tags")
        num_inserted = 0
        for reinsert_index in sorted(to_insert.keys()):
            for seg in to_insert[reinsert_index]:
                aligned_segments.insert_segment(reinsert_index + num_inserted, seg)
                aligned_segments.alignment.add(seg, seg)
                num_inserted += 1
        logger.info(f"done reinserting {num_inserted} paired tags")

        return aligned_segments
