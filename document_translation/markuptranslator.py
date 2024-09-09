
import logging
from time import perf_counter
from typing import List, Tuple

from document_translation.alignedsegments import AlignedSegments
from document_translation.alignment import Alignment
from document_translation.segmentedtext import SegmentedText, SentenceSeparator, TagSegment, TextSegment, WhitespaceSegment
from document_translation.tagreinserter import TagReinserter


logger = logging.getLogger(__name__)

class Translator:
    def translate(self, input_text: str) -> Tuple[List[str], List[str]]:
        raise NotImplementedError

class Aligner:
    def align(self, src_batch: List[List[str]], tgt_batch: List[List[str]]) -> List[List[Tuple[int, int]]]:
        raise NotImplementedError

class Tokenizer:
    def tokenize(self, string: str) -> List[str]:
        raise NotImplementedError

class MarkupTranslator:
    def __init__(self, translator: Translator, aligner: Aligner, tokenizer: Tokenizer):
        self.translator = translator
        self.aligner = aligner
        self.tokenizer = tokenizer
    
    def translator_view(self, segmented_text: SegmentedText) -> Tuple["SegmentedText", Alignment]:
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
        for seg in segmented_text:
            # replace self-closing tags and linebreak tags with spaces because these tags very often create word boundary
            if isinstance(seg, TagSegment) and (seg.tag == "x" or seg.tag == "lb"):
                # TODO (low priority): check if there already is a space and do not add it if it is there
                # TODO (low priority): mark it and remove the space after translation ?
                src_for_translator.append(WhitespaceSegment(" "))
            elif isinstance(seg, TagSegment):
                continue
            elif isinstance(seg, WhitespaceSegment):
                if str(seg) == "\n" or str(seg) == " ":
                    other_seg = seg
                else:
                    # normalize whitespace other than space and newline
                    other_seg = WhitespaceSegment(" ")
                src_for_translator.append(other_seg)
                alignment.add(seg, other_seg)
            else:
                src_for_translator.append(seg)
                alignment.add(seg, seg)
        return src_for_translator, alignment
    
    def aligner_view(self, segmented_text: SegmentedText) -> Tuple["SegmentedText", Alignment]:
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
        for seg in segmented_text:
            if isinstance(seg, TextSegment) or isinstance(seg, SentenceSeparator) or str(seg) == "\n":
                src_for_aligner.append(seg)
                alignment.add(seg, seg)
        return src_for_aligner, alignment

    def align_segments(self, src: SegmentedText, tgt: SegmentedText) -> AlignedSegments:
        src_sentences = list(src.split_sentences())
        tgt_sentences = list(tgt.split_sentences())

        src_batch = [[str(t) for t in sent] for sent in src_sentences]
        tgt_batch = [[str(t) for t in sent] for sent in tgt_sentences]
        
        assert len(src_batch) == len(tgt_batch)
        
        alignments = self.aligner.align(src_batch, tgt_batch)
        merged_alignments = Alignment()
        for src_sentence, tgt_sentence, alignment_sentence in zip(src_sentences, tgt_sentences, alignments):
            for i, j in alignment_sentence:
                src_seg = src_sentence[i]
                tgt_seg = tgt_sentence[j]
                merged_alignments.add(src_seg, tgt_seg)
        return AlignedSegments(src, tgt, merged_alignments)
    
    
    def tokenize_segmented_text(self, segmented_text: SegmentedText, tokenizer: Tokenizer):
        new_segments = SegmentedText()
        for seg in segmented_text:
            if isinstance(seg, TextSegment):
                tokens = tokenizer.tokenize(str(seg))
                if len(tokens) > 1:
                    for tok in tokens:
                        new_segments.append(TextSegment(tok))
                else:
                    new_segments.append(seg)
            else:
                new_segments.append(seg)
        return new_segments
    

    def translate(self, src: str) -> str:
        timer_start = perf_counter()
        # remove non-breakable spaces
        src = src.replace("\xa0", " ")
        src_segments = SegmentedText.from_string(src)
        src_segments = self.tokenize_segmented_text(src_segments, self.tokenizer)

        src_for_translation, src_segments_to_src_for_translation_alignment = self.translator_view(src_segments)
        src_segments_to_src_for_translation = AlignedSegments(src_segments, src_for_translation, src_segments_to_src_for_translation_alignment)

        logger.info("RUN TRANSLATION")
        timer = perf_counter()
        src_sentences, tgt_sentences = self.translator.translate(str(src_for_translation))
        translation_time = perf_counter() - timer
        
        src_sentences = SegmentedText.from_sentences(src_sentences)
        src_sentences = self.tokenize_segmented_text(src_sentences, self.tokenizer)
        # prepare source sentences for word alignment
        src_tokens, src_sentences_to_src_tokens_alignment = self.aligner_view(src_sentences)
        src_sentences_to_src_tokens = AlignedSegments(src_sentences, src_tokens, src_sentences_to_src_tokens_alignment)

        # recover the sentence segmentation from src_sentences
        src_for_translation_to_src_sentences = AlignedSegments(src_for_translation, src_sentences)
        src_for_translation_to_src_sentences.recover_alignment()

        tgt_sentences = SegmentedText.from_sentences(tgt_sentences)
        tgt_sentences = self.tokenize_segmented_text(tgt_sentences, self.tokenizer)

        # prepare target sentences for word alignment
        tgt_tokens, tgt_sentences_to_tgt_tokens_alignment = self.aligner_view(tgt_sentences)
        tgt_sentences_to_tgt_tokens = AlignedSegments(tgt_sentences, tgt_tokens, tgt_sentences_to_tgt_tokens_alignment)
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

        logger.info(":: infer_whitespace_alignment")
        src_for_translation_to_tgt_sentences.infer_whitespace_alignment()

        src_segments_to_tgt_sentences = \
            src_segments_to_src_for_translation \
            .compose(src_for_translation_to_tgt_sentences) \
        
        logger.info("\n:: final alignment before reinserting tags:")
        logger.debug(src_segments_to_tgt_sentences.debug_print())

        logger.info("\n:: reinsert paired tags")
        TagReinserter.reinsert_tags(src_segments_to_tgt_sentences)
        logger.debug(src_segments_to_tgt_sentences.debug_print())

        logger.info("\n:: reinsert aligned whitespace")
        TagReinserter.reinsert_whitespace(src_segments_to_tgt_sentences)
        logger.debug(src_segments_to_tgt_sentences.debug_print())

        logger.info("\n:: reinsert missing segments")
        TagReinserter.reinsert_segments(src_segments_to_tgt_sentences)
        logger.debug(src_segments_to_tgt_sentences.debug_print())

        logger.info(f"Translation took {translation_time:.2f} sec")
        logger.info(f"Alignment took {alignment_time:.2f} seconds")
        total = perf_counter() - timer_start
        logger.info(f"Total time {total:.2f} seconds")
        logger.info(f"Total without requests {(total - translation_time - alignment_time):.2f} seconds")
        return str(src_segments_to_tgt_sentences.tgt)
