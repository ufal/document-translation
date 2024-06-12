
import logging
from time import perf_counter
from typing import List, Tuple

from markuptranslator.alignedsegments import AlignedSegments
from markuptranslator.alignment import Alignment
from markuptranslator.segmentedtext import SegmentedText, SentenceSeparator, TextSegment
from markuptranslator.tagreinserter import TagReinserter


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
            aligned_segments += AlignedSegments(src_sentence_segments, tgt_sentence_segments, Alignment(alignment))
            first = False

        return aligned_segments
    
    
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

        src_for_translation, src_segments_to_src_for_translation_alignment = src_segments.translator_view()
        src_segments_to_src_for_translation = AlignedSegments(src_segments, src_for_translation, src_segments_to_src_for_translation_alignment)

        # src_segments_to_src_for_translation.debug_print()

        logger.info("RUN TRANSLATION")
        timer = perf_counter()
        src_sentences, tgt_sentences = self.translator.translate(str(src_for_translation))
        translation_time = perf_counter() - timer
        
        # print()
        # print(":: src sentences")
        src_sentences = SegmentedText.from_sentences(src_sentences)
        src_sentences = self.tokenize_segmented_text(src_sentences, self.tokenizer)
        # prepare source sentences for word alignment
        src_tokens, src_sentences_to_src_tokens_alignment = src_sentences.aligner_view()
        src_sentences_to_src_tokens = AlignedSegments(src_sentences, src_tokens, src_sentences_to_src_tokens_alignment)

        # recover the sentence segmentation from src_sentences
        src_for_translation_to_src_sentences = AlignedSegments(src_for_translation, src_sentences)
        src_for_translation_to_src_sentences.recover_alignment()

        # print(":: tgt sentences")
        tgt_sentences = SegmentedText.from_sentences(tgt_sentences)
        tgt_sentences = self.tokenize_segmented_text(tgt_sentences, self.tokenizer)
        # prepare target sentences for word alignment
        tgt_tokens, tgt_sentences_to_tgt_tokens_alignment = tgt_sentences.aligner_view()
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
